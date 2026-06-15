from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import discord
from discord import app_commands
from discord.ext import commands

from cogs_cardmaker.card import Defaults
from cogs_cardmaker.repo import CardmakerRepo, build_character_doc, utc_now
from cogs_cardmaker.service import (
    STATUS_TAGS,
    create_template_text,
    design_supports_custom_background_async,
    image_filename,
    load_temporary_background_image_async,
    parse_create_template,
    render_card_bytes_async,
    save_faceclaim_bytes_async,
    starter_body,
    strip_links,
    template_role_for,
    thread_title,
)


STATUS_DISPLAY = {"active": "Active", "hiatus": "Hiatus", "retired": "Retired"}
TYPE_TAGS = {"pc", "npc"}
PLAYER_STATUS_TAGS = {"looking for rp", "looking for master", "looking for servant"}
RESOURCE_EMBED_COLOR = 5814783
TAG_AUDIT_LOOKBACK_SECONDS = 15


def is_admin_member(member: discord.abc.User) -> bool:
    perms = getattr(member, "guild_permissions", None)
    return bool(perms and (perms.manage_guild or perms.administrator))


def clean_optional(value: str | None) -> str | None:
    value = (value or "").strip()
    return value or None


async def is_cardmaker_staff_member(cog: "CardmakerCog", member: discord.Member | discord.User) -> bool:
    if is_admin_member(member):
        return True
    guild = getattr(member, "guild", None)
    if not guild:
        return False
    cfg = await cog.repo.get_config(guild.id)
    approved_role_ids = {str(role_id) for role_id in cfg.get("cardmaker_approved_role_ids") or []}
    if not approved_role_ids:
        return False
    member_role_ids = {str(role.id) for role in getattr(member, "roles", [])}
    return not approved_role_ids.isdisjoint(member_role_ids)


async def cardmaker_staff_check(ctx: commands.Context) -> bool:
    if not ctx.guild:
        return False
    if is_admin_member(ctx.author):
        return True
    cog = ctx.bot.get_cog("CardmakerCog")
    if not isinstance(cog, CardmakerCog):
        return False
    return await is_cardmaker_staff_member(cog, ctx.author)


class CardEditModal(discord.ui.Modal):
    def __init__(self, cog: "CardmakerCog", character: dict[str, Any], mode: str, *, is_admin: bool):
        self.cog = cog
        self.character = character
        self.mode = mode
        self.is_admin = is_admin
        title = {
            "card": "Edit Card",
            "body": "Edit Card Body",
            "design": "Edit Design",
            "admin": "Admin Card Fields",
        }[mode]
        super().__init__(title=title, timeout=300)
        self.inputs: dict[str, discord.ui.TextInput] = {}
        self._build_inputs()

    def add_text(self, key: str, label: str, default: Any = "", *, required: bool = False, long: bool = False, max_length: int = 4000):
        item = discord.ui.TextInput(
            label=label,
            default="" if default is None else str(default),
            required=required,
            style=discord.TextStyle.long if long else discord.TextStyle.short,
            max_length=max_length,
        )
        self.inputs[key] = item
        self.add_item(item)

    def _build_inputs(self):
        c = self.character
        if self.mode == "card":
            self.add_text("name", "Character Name", c.get("name"), required=True, max_length=100)
            self.add_text("role", "Character Role", c.get("role"), required=True, max_length=80)
            if template_role_for(c) == "servant":
                self.add_text("class", "Class", c.get("class"), max_length=80)
                self.add_text("nationality", "Nationality", c.get("nationality"), max_length=100)
            else:
                self.add_text("affiliation", "Affiliation", c.get("affiliation"), max_length=120)
                self.add_text("occupation", "Occupation", c.get("occupation"), max_length=120)
            self.add_text("alignment", "Alignment", c.get("alignment"), max_length=100)
        elif self.mode == "body":
            self.add_text("discord.starter_body", "Original Post", starter_body(c), long=True)
        elif self.mode == "design":
            self.add_text("card.default_design", "Card Design", (c.get("card") or {}).get("default_design"), required=True, max_length=50)
        elif self.mode == "admin":
            self.add_text("username", "Canonical username (NOT display name)", c.get("username"), required=True, max_length=100)
            self.add_text("footer_text", "Footer text (Debut event)", c.get("footer_text"), max_length=200)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)
        if not interaction.guild or not interaction.channel:
            await interaction.followup.send("This only works in a server thread.", ephemeral=True)
            return

        updates: dict[str, Any] = {}
        for key, item in self.inputs.items():
            value = clean_optional(str(item.value))
            if key == "scope" and value:
                value = value.lower()
                if value not in {"full", "minor"}:
                    await interaction.followup.send("Scope must be `full` or `minor`.", ephemeral=True)
                    return
            if key == "type" and value:
                value = value.upper()
                if value not in {"PC", "NPC"}:
                    await interaction.followup.send("Type must be `PC` or `NPC`.", ephemeral=True)
                    return
            if key == "discord.starter_body" and value:
                value = strip_links(value)
            updates[key] = value

        try:
            character = await self.cog.repo.update_fields(self.character["_id"], updates, interaction.user.id, f"card_{self.mode}_edited")
            if not character:
                await interaction.followup.send("I couldn't find this card anymore.", ephemeral=True)
                return
            await self.cog.refresh_thread_from_character(interaction.channel, character, actor_id=interaction.user.id)
            await interaction.followup.send("Card updated.", ephemeral=True)
        except Exception as exc:
            await self.cog.repo.set_last_error(self.character["_id"], str(exc), interaction.user.id)
            await interaction.followup.send(f"Card update failed: `{exc}`", ephemeral=True)


class CardPanelView(discord.ui.View):
    def __init__(
        self,
        cog: "CardmakerCog",
        character: dict[str, Any],
        *,
        is_admin: bool,
        supports_custom_background: bool,
        current_tags: list[discord.ForumTag] | tuple[discord.ForumTag, ...] | None = None,
    ):
        super().__init__(timeout=300)
        self.cog = cog
        self.character = character
        self.is_admin = is_admin
        self.current_tag_names = cog.normalized_tags(current_tags or [])
        self._style_tag_buttons()
        if not supports_custom_background:
            self.remove_item(self.upload_background)
        if not is_admin:
            self.remove_item(self.sync_tags)
            self.remove_item(self.admin_fields)
            self.remove_item(self.delete_card)

    def _style_tag_buttons(self):
        self.active_status.style = self._tag_style("active")
        self.hiatus_status.style = self._tag_style("hiatus")
        self.retired_status.style = self._tag_style("retired")
        self.looking_rp.style = self._tag_style("looking for rp")
        self.looking_master.style = self._tag_style("looking for master")
        self.looking_servant.style = self._tag_style("looking for servant")

    def _tag_style(self, tag_name: str) -> discord.ButtonStyle:
        return discord.ButtonStyle.success if tag_name in self.current_tag_names else discord.ButtonStyle.secondary

    async def _open_modal(self, interaction: discord.Interaction, mode: str):
        await interaction.response.send_modal(CardEditModal(self.cog, self.character, mode, is_admin=self.is_admin))

    async def _refresh_panel(
        self,
        interaction: discord.Interaction,
        character: dict[str, Any],
        applied_tags: list[discord.ForumTag] | tuple[discord.ForumTag, ...] | None,
    ):
        supports_custom_background = await design_supports_custom_background_async(character)
        view = CardPanelView(
            self.cog,
            character,
            is_admin=await is_cardmaker_staff_member(self.cog, interaction.user),
            supports_custom_background=supports_custom_background,
            current_tags=applied_tags,
        )
        await interaction.edit_original_response(content="Card controls", view=view)

    async def _change_status_tag(self, interaction: discord.Interaction, status: str):
        await interaction.response.defer()
        if not isinstance(interaction.channel, discord.Thread):
            await interaction.followup.send("This only works in a card thread.", ephemeral=True)
            return
        character, error = await self.cog.resolve_character_for_channel_user(interaction.channel, interaction.user)
        if error or not character:
            await interaction.followup.send(error or "I couldn't find this card anymore.", ephemeral=True)
            return
        try:
            updated_character, applied_tags = await self.cog.sync_status_from_thread(
                interaction.channel,
                actor_id=interaction.user.id,
                preferred_status=status,
            )
            await self.cog.repo.add_audit(
                character["_id"],
                interaction.user.id,
                "card_tags_updated_from_panel",
                {"thread_id": str(interaction.channel.id), "selection": status},
            )
            await self._refresh_panel(interaction, updated_character or character, applied_tags or interaction.channel.applied_tags)
        except Exception as exc:
            await self.cog.repo.set_last_error(character["_id"], str(exc), interaction.user.id)
            await interaction.followup.send(f"Tag update failed: `{exc}`", ephemeral=True)

    async def _toggle_looking_tag(self, interaction: discord.Interaction, tag_name: str):
        await interaction.response.defer()
        if not isinstance(interaction.channel, discord.Thread):
            await interaction.followup.send("This only works in a card thread.", ephemeral=True)
            return
        character, error = await self.cog.resolve_character_for_channel_user(interaction.channel, interaction.user)
        if error or not character:
            await interaction.followup.send(error or "I couldn't find this card anymore.", ephemeral=True)
            return
        removing = tag_name in self.current_tag_names
        try:
            updated_character, applied_tags = await self.cog.sync_status_from_thread(
                interaction.channel,
                actor_id=interaction.user.id,
                preferred_looking=None if removing else tag_name,
                suppressed_looking_tags={tag_name} if removing else None,
            )
            await self.cog.repo.add_audit(
                character["_id"],
                interaction.user.id,
                "card_tags_updated_from_panel",
                {"thread_id": str(interaction.channel.id), "selection": tag_name, "removed": removing},
            )
            await self._refresh_panel(interaction, updated_character or character, applied_tags or interaction.channel.applied_tags)
        except Exception as exc:
            await self.cog.repo.set_last_error(character["_id"], str(exc), interaction.user.id)
            await interaction.followup.send(f"Tag update failed: `{exc}`", ephemeral=True)

    @discord.ui.button(label="Edit Card", style=discord.ButtonStyle.primary, row=0)
    async def edit_card(self, interaction: discord.Interaction, _: discord.ui.Button):
        await self._open_modal(interaction, "card")

    @discord.ui.button(label="Edit Starter Post", style=discord.ButtonStyle.primary, row=0)
    async def edit_body(self, interaction: discord.Interaction, _: discord.ui.Button):
        await self._open_modal(interaction, "body")

    @discord.ui.button(label="Edit Design", style=discord.ButtonStyle.primary, row=0)
    async def edit_design(self, interaction: discord.Interaction, _: discord.ui.Button):
        await self._open_modal(interaction, "design")

    @discord.ui.button(label="Edit Faceclaim", style=discord.ButtonStyle.primary, row=0)
    async def upload_faceclaim(self, interaction: discord.Interaction, _: discord.ui.Button):
        if not interaction.channel:
            await interaction.response.send_message("This only works in a card thread.", ephemeral=True)
            return
        self.cog.pending_faceclaim_uploads[(interaction.channel.id, interaction.user.id)] = self.character["_id"]
        await interaction.response.send_message(
            "Send the new faceclaim image as your next message in this thread. It will replace the current faceclaim.",
            ephemeral=True,
        )

    @discord.ui.button(label="Custom Background", style=discord.ButtonStyle.success, row=1)
    async def upload_background(self, interaction: discord.Interaction, _: discord.ui.Button):
        if not interaction.channel:
            await interaction.response.send_message("This only works in a card thread.", ephemeral=True)
            return
        if not await design_supports_custom_background_async(self.character):
            await interaction.response.send_message("This card design does not support custom backgrounds.", ephemeral=True)
            return
        self.cog.pending_background_uploads[(interaction.channel.id, interaction.user.id)] = self.character["_id"]
        await interaction.response.send_message(
            "Send the custom background image as your next message in this thread. It will be used once and will not be saved; future card edits will return to the design default background.",
            ephemeral=True,
        )

    @discord.ui.button(label="Edit Tags", style=discord.ButtonStyle.secondary, disabled=True, row=2)
    async def tag_section_label(self, interaction: discord.Interaction, _: discord.ui.Button):
        pass

    @discord.ui.button(label="☀️Active", style=discord.ButtonStyle.secondary, row=3)
    async def active_status(self, interaction: discord.Interaction, _: discord.ui.Button):
        await self._change_status_tag(interaction, "active")

    @discord.ui.button(label="☀️Hiatus", style=discord.ButtonStyle.secondary, row=3)
    async def hiatus_status(self, interaction: discord.Interaction, _: discord.ui.Button):
        await self._change_status_tag(interaction, "hiatus")

    @discord.ui.button(label="☀️Retired", style=discord.ButtonStyle.secondary, row=3)
    async def retired_status(self, interaction: discord.Interaction, _: discord.ui.Button):
        await self._change_status_tag(interaction, "retired")

    @discord.ui.button(label="🎉Looking for RP", style=discord.ButtonStyle.secondary, row=4)
    async def looking_rp(self, interaction: discord.Interaction, _: discord.ui.Button):
        await self._toggle_looking_tag(interaction, "looking for rp")

    @discord.ui.button(label="🔎Looking for Master", style=discord.ButtonStyle.secondary, row=4)
    async def looking_master(self, interaction: discord.Interaction, _: discord.ui.Button):
        await self._toggle_looking_tag(interaction, "looking for master")

    @discord.ui.button(label="🔎Looking for Servant", style=discord.ButtonStyle.secondary, row=4)
    async def looking_servant(self, interaction: discord.Interaction, _: discord.ui.Button):
        await self._toggle_looking_tag(interaction, "looking for servant")

    @discord.ui.button(label="Sync Tags", style=discord.ButtonStyle.danger, row=1)
    async def sync_tags(self, interaction: discord.Interaction, _: discord.ui.Button):
        if not await is_cardmaker_staff_member(self.cog, interaction.user):
            await interaction.response.send_message("Only admins or approved cardmaker roles can sync tags manually.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True, thinking=True)
        if not isinstance(interaction.channel, discord.Thread):
            await interaction.followup.send("This only works in a card thread.", ephemeral=True)
            return
        await self.cog.sync_status_from_thread(interaction.channel, actor_id=interaction.user.id, allow_type_sync=True)
        await interaction.followup.send("Tags synced.", ephemeral=True)

    @discord.ui.button(label="Admin Fields", style=discord.ButtonStyle.danger, row=1)
    async def admin_fields(self, interaction: discord.Interaction, _: discord.ui.Button):
        if not await is_cardmaker_staff_member(self.cog, interaction.user):
            await interaction.response.send_message("Only admins or approved cardmaker roles can edit admin fields.", ephemeral=True)
            return
        await self._open_modal(interaction, "admin")

    @discord.ui.button(label="Delete Card", style=discord.ButtonStyle.danger, row=1)
    async def delete_card(self, interaction: discord.Interaction, _: discord.ui.Button):
        if not await is_cardmaker_staff_member(self.cog, interaction.user):
            await interaction.response.send_message("Only admins or approved cardmaker roles can delete cards.", ephemeral=True)
            return
        await interaction.response.send_message(
            f"Delete `{self.character.get('name')}`? This moves the MongoDB document to `cardmaker_deleted` and deletes this thread.",
            view=DeleteCardConfirmView(self.cog, self.character),
            ephemeral=True,
        )


class DeleteCardConfirmView(discord.ui.View):
    def __init__(self, cog: "CardmakerCog", character: dict[str, Any]):
        super().__init__(timeout=120)
        self.cog = cog
        self.character = character

    @discord.ui.button(label="Confirm Delete", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, _: discord.ui.Button):
        if not await is_cardmaker_staff_member(self.cog, interaction.user):
            await interaction.response.send_message("Only admins or approved cardmaker roles can delete cards.", ephemeral=True)
            return
        if not isinstance(interaction.channel, discord.Thread):
            await interaction.response.send_message("This only works in a card thread.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True, thinking=True)
        character_id = self.character["_id"]
        try:
            deleted = await self.cog.repo.delete_character(character_id, interaction.user.id)
        except Exception as exc:
            await interaction.followup.send(f"Delete failed before the thread was changed: `{exc}`", ephemeral=True)
            return
        if not deleted:
            await interaction.followup.send("I couldn't find this card anymore.", ephemeral=True)
            return
        await interaction.followup.send("Card archived. Deleting this thread now.", ephemeral=True)
        try:
            await interaction.channel.delete(reason=f"Card deleted by {interaction.user} ({interaction.user.id})")
        except discord.NotFound:
            pass
        except discord.HTTPException as exc:
            restored = await self.cog.repo.restore_deleted_character(
                character_id,
                interaction.user.id,
                "card_delete_rolled_back",
                {"error": str(exc)},
            )
            if restored:
                await interaction.followup.send(f"Thread deletion failed, so the MongoDB delete was rolled back: `{exc}`", ephemeral=True)
            else:
                await self.cog.repo.add_audit(character_id, interaction.user.id, "card_delete_rollback_failed", {"error": str(exc)})
                await interaction.followup.send(f"Thread deletion failed, and I could not restore the MongoDB record automatically: `{exc}`", ephemeral=True)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, _: discord.ui.Button):
        await interaction.response.edit_message(content="Delete cancelled.", view=None)


class CardmakerCog(commands.Cog):
    card_app = app_commands.Group(name="card", description="Character card tools")

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.repo = CardmakerRepo(bot.db)
        self.pending_faceclaim_uploads: dict[tuple[int, int], str] = {}
        self.pending_background_uploads: dict[tuple[int, int], str] = {}
        self.pending_bot_tag_edits: set[int] = set()

    async def delete_message_quietly(self, message: discord.Message):
        try:
            await message.delete()
        except (discord.Forbidden, discord.NotFound, discord.HTTPException):
            pass

    async def is_owner_or_staff(self, member: discord.Member | discord.User, character: dict[str, Any]) -> bool:
        return await is_cardmaker_staff_member(self, member) or str(getattr(member, "id", "")) == str(character.get("userid"))

    async def resolve_character_for_channel_user(
        self,
        channel: discord.abc.GuildChannel | discord.abc.PrivateChannel | discord.Thread | None,
        user: discord.Member | discord.User,
    ) -> tuple[dict[str, Any] | None, str | None]:
        if not isinstance(channel, discord.Thread):
            return None, "Run this inside the card's forum thread."
        character = await self.repo.find_by_thread_id(channel.id)
        if not character:
            return None, "I don't have a card record linked to this thread."
        if not await self.is_owner_or_staff(user, character):
            return None, "You can only manage your own card here."
        return character, None

    async def resolve_character_in_thread(self, ctx: commands.Context) -> dict[str, Any] | None:
        character, error = await self.resolve_character_for_channel_user(ctx.channel, ctx.author)
        if error:
            await ctx.send(error)
            return None
        return character

    async def edit_controls_for(
        self,
        channel: discord.abc.GuildChannel | discord.abc.PrivateChannel | discord.Thread | None,
        user: discord.Member | discord.User,
    ) -> tuple[discord.ui.View | None, str | None]:
        character, error = await self.resolve_character_for_channel_user(channel, user)
        if error or not character:
            return None, error
        supports_custom_background = await design_supports_custom_background_async(character)
        view = CardPanelView(
            self,
            character,
            is_admin=await is_cardmaker_staff_member(self, user),
            supports_custom_background=supports_custom_background,
            current_tags=channel.applied_tags if isinstance(channel, discord.Thread) else None,
        )
        return view, None

    async def configured_forum(self, guild: discord.Guild, scope: str) -> discord.ForumChannel | None:
        cfg = await self.repo.get_config(guild.id)
        key = "cardmaker_minor_forum_channel_id" if scope == "minor" else "cardmaker_full_forum_channel_id"
        channel_id = cfg.get(key)
        if not channel_id:
            return None
        channel = guild.get_channel(int(channel_id))
        return channel if isinstance(channel, discord.ForumChannel) else None

    def posted_thread_for_guild(self, character: dict[str, Any], guild_id: int) -> str | None:
        discord_block = character.get("discord") or {}
        for post in discord_block.get("posts") or []:
            if str(post.get("guild_id")) == str(guild_id) and post.get("thread_id"):
                return str(post["thread_id"])
        return None

    async def posted_thread_exists(self, guild: discord.Guild, thread_id: str | int) -> bool:
        thread_id = int(thread_id)
        cached = guild.get_thread(thread_id)
        if cached:
            return True
        channel = await self.bot.fetch_channel(thread_id)
        return isinstance(channel, discord.Thread) and channel.guild.id == guild.id

    def tag_by_name(self, forum: discord.ForumChannel, name: str) -> discord.ForumTag | None:
        lowered = name.lower()
        for tag in forum.available_tags:
            if tag.name.lower() == lowered:
                return tag
        return None

    def normalized_tags(self, tags: list[discord.ForumTag] | tuple[discord.ForumTag, ...]) -> set[str]:
        return {tag.name.lower() for tag in tags}

    async def thread_tag_actor(self, thread: discord.Thread) -> discord.abc.User | None:
        guild = thread.guild
        bot_member = guild.me
        if not bot_member or not bot_member.guild_permissions.view_audit_log:
            return None
        await asyncio.sleep(1)
        now = discord.utils.utcnow()
        try:
            async for entry in guild.audit_logs(limit=8, action=discord.AuditLogAction.thread_update):
                if getattr(entry.target, "id", None) != thread.id or not entry.user:
                    continue
                created_at = getattr(entry, "created_at", None)
                if created_at and abs((now - created_at).total_seconds()) > TAG_AUDIT_LOOKBACK_SECONDS:
                    continue
                return entry.user
        except discord.HTTPException:
            return None
        return None

    async def can_change_card_tags(self, guild: discord.Guild, actor: discord.abc.User | None, character: dict[str, Any]) -> bool:
        if not actor:
            return False
        if self.bot.user and actor.id == self.bot.user.id:
            return True
        if str(actor.id) == str(character.get("userid")):
            return True
        member = guild.get_member(actor.id)
        if not member:
            try:
                member = await guild.fetch_member(actor.id)
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                return False
        return await is_cardmaker_staff_member(self, member)

    async def revert_tag_change(
        self,
        thread: discord.Thread,
        tags: list[discord.ForumTag] | tuple[discord.ForumTag, ...],
        character: dict[str, Any],
        actor: discord.abc.User | None,
        reason: str,
    ) -> None:
        self.pending_bot_tag_edits.add(thread.id)
        try:
            await thread.edit(applied_tags=list(tags))
        except discord.HTTPException as exc:
            self.pending_bot_tag_edits.discard(thread.id)
            await self.repo.add_audit(
                character["_id"],
                getattr(actor, "id", None),
                "card_tag_revert_failed",
                {"thread_id": str(thread.id), "reason": reason, "error": str(exc)},
            )
            return
        await self.repo.add_audit(
            character["_id"],
            getattr(actor, "id", None),
            "card_tag_change_reverted",
            {"thread_id": str(thread.id), "reason": reason},
        )

    def desired_tags(
        self,
        forum: discord.ForumChannel,
        character: dict[str, Any],
        current_tags: list[discord.ForumTag] | tuple[discord.ForumTag, ...] | None = None,
        preferred_status: str | None = None,
        preferred_looking: str | None = None,
        preferred_type: str | None = None,
        preserve_current_type: bool = False,
        suppressed_looking_tags: set[str] | None = None,
    ) -> list[discord.ForumTag]:
        tags: list[discord.ForumTag] = []
        current_names = self.normalized_tags(current_tags or [])
        current_names -= suppressed_looking_tags or set()
        status_name = None

        def add_tag_name(name: str):
            tag = self.tag_by_name(forum, name)
            if tag and tag.id not in {existing.id for existing in tags}:
                tags.append(tag)

        if preferred_looking in PLAYER_STATUS_TAGS:
            if preferred_looking == "looking for rp":
                add_tag_name("Looking for RP")
                if "looking for master" in current_names:
                    add_tag_name("Looking for Master")
                elif "looking for servant" in current_names:
                    add_tag_name("Looking for Servant")
            else:
                if "looking for rp" in current_names:
                    add_tag_name("Looking for RP")
                add_tag_name("Looking for Master" if preferred_looking == "looking for master" else "Looking for Servant")
        elif preferred_status in {"active", "hiatus", "retired"}:
            status_name = STATUS_DISPLAY[preferred_status]
        elif "retired" in current_names:
            status_name = "Retired"
        elif "hiatus" in current_names:
            status_name = "Hiatus"
        else:
            looking_tags = []
            if "looking for rp" in current_names:
                looking_tags.append("Looking for RP")
            if "looking for master" in current_names:
                looking_tags.append("Looking for Master")
            elif "looking for servant" in current_names:
                looking_tags.append("Looking for Servant")

            if looking_tags:
                for name in looking_tags:
                    add_tag_name(name)
            elif "active" in current_names:
                status_name = "Active"
            else:
                admin_status = str((character.get("admin") or {}).get("status") or "active").lower()
                status_name = {"active": "Active", "hiatus": "Hiatus", "retired": "Retired"}.get(admin_status, "Active")

        if status_name:
            add_tag_name(status_name)

        if preferred_type in TYPE_TAGS:
            type_name = preferred_type.upper()
        elif preserve_current_type and "pc" in current_names:
            type_name = "PC"
        elif preserve_current_type and "npc" in current_names:
            type_name = "NPC"
        else:
            type_name = str(character.get("type") or "PC").upper()
        add_tag_name(type_name)
        return tags

    async def make_card_file(self, character: dict[str, Any], runtime_images: dict[str, Any] | None = None) -> discord.File:
        data = await render_card_bytes_async(character, runtime_images=runtime_images)
        return discord.File(data, filename=image_filename(character))

    def make_faceclaim_file(self, character: dict[str, Any]) -> discord.File | None:
        avatar_path = str(character.get("avatar_path") or "").strip()
        if not avatar_path:
            return None
        path = Path(avatar_path)
        if not path.is_absolute():
            path = Defaults.FACECLAIMS_DIR / path
        if not path.exists() or not path.is_file():
            return None
        return discord.File(str(path), filename=path.name)

    def make_resource_embed(self, character: dict[str, Any], attachment_filename: str | None = None) -> discord.Embed:
        embed = discord.Embed(color=RESOURCE_EMBED_COLOR)
        embed.add_field(
            name="Character Sheet",
            value=str(character.get("source_url") or "No character sheet URL on file."),
            inline=False,
        )
        if attachment_filename:
            embed.set_thumbnail(url=f"attachment://{attachment_filename}")
        return embed

    def resource_post_id_for_thread(self, character: dict[str, Any], thread_id: int) -> str | None:
        discord_block = character.get("discord") or {}
        for post in discord_block.get("posts") or []:
            if str(post.get("thread_id")) == str(thread_id):
                resource_id = post.get("resource_message_id")
                return str(resource_id) if resource_id else None
        return None

    async def fetch_resource_message(self, thread: discord.Thread, character: dict[str, Any]) -> discord.Message | None:
        resource_id = self.resource_post_id_for_thread(character, thread.id)
        if not resource_id:
            return None
        try:
            return await thread.fetch_message(int(resource_id))
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            pass
        return None

    async def send_resource_message(self, thread: discord.Thread, character: dict[str, Any]) -> discord.Message:
        faceclaim_file = self.make_faceclaim_file(character)
        embed = self.make_resource_embed(character, faceclaim_file.filename if faceclaim_file else None)
        kwargs: dict[str, Any] = {
            "embed": embed,
            "allowed_mentions": discord.AllowedMentions.none(),
        }
        if faceclaim_file:
            kwargs["file"] = faceclaim_file
        return await thread.send(**kwargs)

    async def refresh_resource_message(self, thread: discord.Thread, character: dict[str, Any], actor_id: int | str | None) -> None:
        faceclaim_file = self.make_faceclaim_file(character)
        embed = self.make_resource_embed(character, faceclaim_file.filename if faceclaim_file else None)
        msg = await self.fetch_resource_message(thread, character)
        if msg:
            await msg.edit(embed=embed, attachments=[faceclaim_file] if faceclaim_file else [])
            return
        kwargs: dict[str, Any] = {
            "embed": embed,
            "allowed_mentions": discord.AllowedMentions.none(),
        }
        if faceclaim_file:
            kwargs["file"] = faceclaim_file
        msg = await thread.send(**kwargs)
        await self.repo.set_resource_message_id(
            character["_id"],
            thread_id=thread.id,
            resource_message_id=msg.id,
            actor_id=actor_id,
        )

    async def create_card_thread(self, forum: discord.ForumChannel, character: dict[str, Any], actor_id: int | str) -> discord.Thread:
        card_file = await self.make_card_file(character)
        result = await forum.create_thread(
            name=thread_title(character),
            content=starter_body(character),
            file=card_file,
            applied_tags=self.desired_tags(forum, character),
            suppress_embeds=True,
            allowed_mentions=discord.AllowedMentions(users=True, roles=False, everyone=False),
        )
        thread = getattr(result, "thread", result)
        message = getattr(result, "message", None)
        resource_message = await self.send_resource_message(thread, character)
        await self.repo.mark_posted(
            character["_id"],
            guild_id=forum.guild.id,
            forum_channel_id=forum.id,
            thread_id=thread.id,
            starter_message_id=getattr(message, "id", None),
            resource_message_id=resource_message.id,
            actor_id=actor_id,
        )
        return thread

    async def fetch_starter_message(self, thread: discord.Thread, character: dict[str, Any]) -> discord.Message | None:
        discord_block = character.get("discord") or {}
        starter_id = None
        for post in discord_block.get("posts") or []:
            if str(post.get("thread_id")) == str(thread.id):
                starter_id = post.get("starter_message_id")
                break
        if not starter_id:
            return None
        try:
            return await thread.fetch_message(int(starter_id))
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            pass
        return None

    async def refresh_thread_from_character(
        self,
        channel: discord.abc.Messageable,
        character: dict[str, Any],
        actor_id: int | str | None,
        runtime_images: dict[str, Any] | None = None,
    ):
        if not isinstance(channel, discord.Thread):
            raise RuntimeError("Card updates must run inside a card thread.")
        desired_name = thread_title(character)
        parent = channel.parent
        desired_tags = None
        if isinstance(parent, discord.ForumChannel):
            desired_tags = self.desired_tags(parent, character, channel.applied_tags)

        edit_kwargs: dict[str, Any] = {}
        if channel.name != desired_name:
            edit_kwargs["name"] = desired_name
        if desired_tags is not None:
            current_ids = {tag.id for tag in channel.applied_tags}
            desired_ids = {tag.id for tag in desired_tags}
            if current_ids != desired_ids:
                edit_kwargs["applied_tags"] = desired_tags
        if edit_kwargs:
            if "applied_tags" in edit_kwargs:
                self.pending_bot_tag_edits.add(channel.id)
            try:
                await channel.edit(**edit_kwargs)
            except Exception:
                if "applied_tags" in edit_kwargs:
                    self.pending_bot_tag_edits.discard(channel.id)
                raise

        msg = await self.fetch_starter_message(channel, character)
        if msg:
            card_file = await self.make_card_file(character, runtime_images=runtime_images)
            await msg.edit(
                content=starter_body(character),
                attachments=[card_file],
                suppress=True,
                allowed_mentions=discord.AllowedMentions(users=True, roles=False, everyone=False),
            )
        await self.refresh_resource_message(channel, character, actor_id)
        await self.repo.update_fields(
            character["_id"],
            {
                "card.last_rendered_at": utc_now(),
                "discord.last_synced_at": utc_now(),
                "discord.last_error": None,
            },
            actor_id,
            "card_updated",
        )

    async def sync_status_from_thread(
        self,
        thread: discord.Thread,
        actor_id: int | str | None = None,
        preferred_status: str | None = None,
        preferred_looking: str | None = None,
        preferred_type: str | None = None,
        allow_type_sync: bool = False,
        suppressed_looking_tags: set[str] | None = None,
    ) -> tuple[dict[str, Any] | None, list[discord.ForumTag] | None]:
        character = await self.repo.find_by_thread_id(thread.id)
        if not character:
            return None, None
        parent = thread.parent
        desired_tags = None
        if isinstance(parent, discord.ForumChannel):
            desired_tags = self.desired_tags(
                parent,
                character,
                thread.applied_tags,
                preferred_status=preferred_status,
                preferred_looking=preferred_looking,
                preferred_type=preferred_type if allow_type_sync else None,
                preserve_current_type=allow_type_sync,
                suppressed_looking_tags=suppressed_looking_tags,
            )
            current_ids = {tag.id for tag in thread.applied_tags}
            desired_ids = {tag.id for tag in desired_tags}
            if current_ids != desired_ids:
                self.pending_bot_tag_edits.add(thread.id)
                try:
                    await thread.edit(applied_tags=desired_tags)
                except Exception:
                    self.pending_bot_tag_edits.discard(thread.id)
                    raise

        found: str | None = None
        tag_names = self.normalized_tags(desired_tags if desired_tags is not None else thread.applied_tags)
        if "retired" in tag_names:
            found = "retired"
        elif "hiatus" in tag_names:
            found = "hiatus"
        elif "active" in tag_names or tag_names.intersection(PLAYER_STATUS_TAGS):
            found = "active"

        found_type = None
        if "pc" in tag_names:
            found_type = "PC"
        elif "npc" in tag_names:
            found_type = "NPC"

        updates: dict[str, Any] = {}
        current = str((character.get("admin") or {}).get("status") or "").lower()
        if found and current != found:
            updates["admin.status"] = found
            updates["admin.status_synced_at"] = utc_now()
        if allow_type_sync and found_type and str(character.get("type") or "").upper() != found_type:
            updates["type"] = found_type
            updates["discord.starter_body"] = None
        if not updates:
            return character, desired_tags
        updated = await self.repo.update_fields(
            character["_id"],
            updates,
            actor_id,
            "status_synced_from_tags",
        )
        if updated and allow_type_sync and found_type:
            await self.refresh_thread_from_character(thread, updated, actor_id=actor_id)
        return updated or character, desired_tags

    @commands.Cog.listener()
    async def on_thread_update(self, before: discord.Thread, after: discord.Thread):
        if before.applied_tags != after.applied_tags:
            if after.id in self.pending_bot_tag_edits:
                self.pending_bot_tag_edits.discard(after.id)
                return
            character = await self.repo.find_by_thread_id(after.id)
            if not character:
                return
            actor = await self.thread_tag_actor(after)
            if not await self.can_change_card_tags(after.guild, actor, character):
                reason = "actor_unknown" if actor is None else "actor_not_owner_or_admin"
                await self.revert_tag_change(after, before.applied_tags, character, actor, reason)
                return
            before_names = self.normalized_tags(before.applied_tags)
            after_names = self.normalized_tags(after.applied_tags)
            added_statuses = [name for name in ("active", "hiatus", "retired") if name in after_names and name not in before_names]
            added_looking = [name for name in ("looking for rp", "looking for master", "looking for servant") if name in after_names and name not in before_names]
            added_types = [name for name in ("pc", "npc") if name in after_names and name not in before_names]
            preferred_status = added_statuses[-1] if added_statuses else None
            preferred_looking = added_looking[-1] if added_looking else None
            preferred_type = added_types[-1] if added_types else None
            await self.sync_status_from_thread(
                after,
                actor_id=actor.id if actor else None,
                preferred_status=preferred_status,
                preferred_looking=preferred_looking,
                preferred_type=preferred_type,
                allow_type_sync=preferred_type is not None,
            )

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild or not isinstance(message.channel, discord.Thread):
            return
        key = (message.channel.id, message.author.id)
        character_id = self.pending_faceclaim_uploads.pop(key, None)
        upload_kind = "faceclaim"
        if not character_id:
            character_id = self.pending_background_uploads.pop(key, None)
            upload_kind = "background"
        if not character_id:
            return
        if not message.attachments:
            if upload_kind == "faceclaim":
                self.pending_faceclaim_uploads[key] = character_id
            else:
                self.pending_background_uploads[key] = character_id
            await self.delete_message_quietly(message)
            return
        character = await self.repo.get_character(character_id)
        if not character:
            await self.delete_message_quietly(message)
            return
        if not await self.is_owner_or_staff(message.author, character):
            await self.delete_message_quietly(message)
            return
        attachment = message.attachments[0]
        try:
            data = await attachment.read()
            if upload_kind == "faceclaim":
                avatar_path = await save_faceclaim_bytes_async(character, data, attachment.filename)
                character = await self.repo.update_fields(
                    character["_id"],
                    {"avatar_path": avatar_path},
                    message.author.id,
                    "faceclaim_replaced",
                )
                if character:
                    await self.refresh_thread_from_character(message.channel, character, actor_id=message.author.id)
            else:
                if not await design_supports_custom_background_async(character):
                    raise ValueError("This card design does not support custom backgrounds.")
                background = await load_temporary_background_image_async(data, attachment.filename)
                await self.refresh_thread_from_character(
                    message.channel,
                    character,
                    actor_id=message.author.id,
                    runtime_images={"background": background},
                )
                await self.repo.add_audit(
                    character["_id"],
                    message.author.id,
                    "temporary_background_rendered",
                    {"filename": attachment.filename},
                )
            await self.delete_message_quietly(message)
        except Exception as exc:
            await self.repo.set_last_error(character_id, str(exc), message.author.id)
            await self.delete_message_quietly(message)

    @commands.group(name="card", invoke_without_command=True)
    async def card_group(self, ctx: commands.Context):
        await ctx.send(
            "Commands: `f.card create`, `f.card post <id/url>`, "
            "`f.card post <id/url> ...`, `f.card postall`, `f.card fullchannel #forum`, "
            "`f.card minorchannel #forum`, `f.card edit`"
        )

    @card_group.command(name="fullchannel")
    @commands.check(cardmaker_staff_check)
    async def set_full_channel(self, ctx: commands.Context, channel: discord.ForumChannel):
        await self.repo.set_card_channels(ctx.guild.id, full_channel_id=channel.id)
        await ctx.send(f"Full-character card forum set to {channel.mention}.")

    @card_group.command(name="minorchannel")
    @commands.check(cardmaker_staff_check)
    async def set_minor_channel(self, ctx: commands.Context, channel: discord.ForumChannel):
        await self.repo.set_card_channels(ctx.guild.id, minor_channel_id=channel.id)
        await ctx.send(f"Minor-character card forum set to {channel.mention}.")

    @card_group.command(name="create")
    @commands.check(cardmaker_staff_check)
    async def create(self, ctx: commands.Context):
        fields = parse_create_template(ctx.message.content)
        if not fields:
            await ctx.send(f"```text\n{create_template_text()}\n```")
            return

        player_text = fields.get("player")
        if not player_text or not ctx.message.mentions:
            await ctx.send("Use `--player: @mention` in the create template.")
            return
        player = ctx.message.mentions[0]
        try:
            cfg = await self.repo.get_config(ctx.guild.id)
            default_design = cfg.get("cardmaker_default_design") or "default-rotw"
            character = build_character_doc(fields, player_user=player, created_by=ctx.author.id, default_design=default_design)
            existing = await self.repo.get_character(character["_id"])
            if existing:
                await ctx.send(f"`{character['_id']}` already exists. Use `f.card post {character['_id']}`.")
                return
            if ctx.message.attachments:
                attachment = ctx.message.attachments[0]
                data = await attachment.read()
                character["avatar_path"] = await save_faceclaim_bytes_async(character, data, attachment.filename)
            character = await self.repo.create_character(character)
            await self.repo.add_audit(character["_id"], ctx.author.id, "card_created", {"fields": fields})
            await ctx.send(f"Created `{character['_id']}`. Posting card...")
            await self.post_character(ctx, character)
        except Exception as exc:
            await ctx.send(f"Create failed: `{exc}`")

    async def post_character(self, ctx: commands.Context, character: dict[str, Any]) -> bool:
        if not ctx.guild:
            await ctx.send("This only works in a server.")
            return False
        thread_id = self.posted_thread_for_guild(character, ctx.guild.id)
        if thread_id:
            try:
                exists = await self.posted_thread_exists(ctx.guild, thread_id)
            except discord.NotFound:
                exists = False
            except (discord.Forbidden, discord.HTTPException) as exc:
                await self.repo.add_audit(
                    character["_id"],
                    ctx.author.id,
                    "post_existing_thread_verify_failed",
                    {"thread_id": thread_id, "error": str(exc)},
                )
                await ctx.send(f"`{character.get('name')}` has a stored thread, but I couldn't verify it: `{exc}`")
                return False

            if exists:
                await self.repo.add_audit(character["_id"], ctx.author.id, "post_existing_thread_linked", {"thread_id": thread_id})
                await ctx.send(f"`{character.get('name')}` is already posted: <#{thread_id}>")
                return False

            updated = await self.repo.remove_post_for_guild(
                character["_id"],
                guild_id=ctx.guild.id,
                thread_id=thread_id,
                actor_id=ctx.author.id,
            )
            if updated:
                character = updated
            await ctx.send(f"`{character.get('name')}` had a stale deleted thread reference. Reposting now.")
        forum = await self.configured_forum(ctx.guild, str(character.get("scope") or "full").lower())
        if not forum:
            await ctx.send("Card forum is not configured for this character scope yet.")
            return False
        try:
            thread = await self.create_card_thread(forum, character, ctx.author.id)
            await ctx.send(f"Posted `{character.get('name')}`: {thread.mention}")
            return True
        except Exception as exc:
            await self.repo.set_last_error(character["_id"], str(exc), ctx.author.id)
            await ctx.send(f"Post failed for `{character.get('name')}`: `{exc}`")
            return False

    @card_group.command(name="post")
    @commands.check(cardmaker_staff_check)
    async def post(self, ctx: commands.Context, *refs: str):
        if not refs:
            await ctx.send("Provide one or more character IDs, doc IDs, or doc URLs.")
            return

        successes = 0
        failures: list[str] = []
        for ref in refs:
            character, matches = await self.repo.find_one_by_reference(ref)
            if not character:
                if matches:
                    lines = ", ".join(f"`{m['_id']}`" for m in matches[:10])
                    failures.append(f"{ref}: ambiguous; use one of {lines}")
                else:
                    failures.append(f"{ref}: not found")
                continue
            if await self.post_character(ctx, character):
                successes += 1
            await asyncio.sleep(1)
        if len(refs) == 1 and failures:
            await ctx.send(f"Post failed: {failures[0]}")
        elif len(refs) > 1:
            await ctx.send(f"Post complete. Attempted: {len(refs)}. Posted: {successes}. Failures: {len(failures)}")
            if failures:
                await ctx.send("Failures:\n" + "\n".join(f"- {failure}" for failure in failures[:10]))

    @card_group.command(name="postall")
    @commands.check(cardmaker_staff_check)
    async def postall(self, ctx: commands.Context):
        characters = await self.repo.list_postable(ctx.guild.id)
        if not characters:
            await ctx.send("No unposted active characters found.")
            return
        await ctx.send(f"Posting {len(characters)} unposted active character(s).")
        posted = 0
        for character in characters:
            if await self.post_character(ctx, character):
                posted += 1
            await asyncio.sleep(1)
        await ctx.send(f"Postall complete. Posted {posted} of {len(characters)} unposted candidate(s).")

    @card_group.command(name="edit", aliases=["panel"])
    async def edit(self, ctx: commands.Context):
        view, error = await self.edit_controls_for(ctx.channel, ctx.author)
        if error or not view:
            await ctx.send(error or "I couldn't open card controls.")
            return
        try:
            await ctx.message.delete()
        except (discord.Forbidden, discord.HTTPException):
            pass
        await ctx.send("Card controls", view=view, delete_after=300)

    @card_app.command(name="edit", description="Open editing controls for this card thread.")
    async def edit_app(self, interaction: discord.Interaction):
        view, error = await self.edit_controls_for(interaction.channel, interaction.user)
        if error or not view:
            await interaction.response.send_message(error or "I couldn't open card controls.", ephemeral=True)
            return
        await interaction.response.send_message("Card controls", view=view, ephemeral=True)

    @card_group.command(name="setdefaultdesign")
    @commands.check(cardmaker_staff_check)
    async def setdefaultdesign(self, ctx: commands.Context, design: str):
        await self.repo.set_default_design(ctx.guild.id, design)
        await ctx.send(f"Default card design set to `{design}`.")

    @card_group.command(name="setapprovedrole")
    @commands.has_permissions(manage_guild=True)
    async def setapprovedrole(self, ctx: commands.Context, *roles: discord.Role):
        if not roles:
            await self.repo.set_approved_role_ids(ctx.guild.id, [])
            await ctx.send("Cardmaker approved roles cleared. Only server admins can use cardmaker staff commands.")
            return
        role_ids = [role.id for role in roles]
        await self.repo.set_approved_role_ids(ctx.guild.id, role_ids)
        await ctx.send("Cardmaker approved roles updated to:\n" + "\n".join(role.mention for role in roles))

    async def cog_command_error(self, ctx: commands.Context, error: commands.CommandError):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("Only server admins can use that setup command.")
            return
        if isinstance(error, commands.CheckFailure):
            await ctx.send("Only server admins or approved cardmaker roles can use that command.")
            return
        raise error


async def setup(bot: commands.Bot):
    await bot.add_cog(CardmakerCog(bot))
