from __future__ import annotations

import asyncio
from typing import Any

import discord
from discord.ext import commands

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


def is_admin_member(member: discord.abc.User) -> bool:
    perms = getattr(member, "guild_permissions", None)
    return bool(perms and (perms.manage_guild or perms.administrator))


def clean_optional(value: str | None) -> str | None:
    value = (value or "").strip()
    return value or None


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
            self.add_text("source_url", "Google docs URL", c.get("source_url"), max_length=300)

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
    def __init__(self, cog: "CardmakerCog", character: dict[str, Any], *, is_admin: bool):
        super().__init__(timeout=300)
        self.cog = cog
        self.character = character
        self.is_admin = is_admin
        if not is_admin:
            self.remove_item(self.sync_tags)
            self.remove_item(self.admin_fields)
            self.remove_item(self.delete_card)

    async def _open_modal(self, interaction: discord.Interaction, mode: str):
        await interaction.response.send_modal(CardEditModal(self.cog, self.character, mode, is_admin=self.is_admin))

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

    @discord.ui.button(label="Custom Background", style=discord.ButtonStyle.secondary, row=1)
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

    @discord.ui.button(label="Sync Tags", style=discord.ButtonStyle.danger, row=1)
    async def sync_tags(self, interaction: discord.Interaction, _: discord.ui.Button):
        if not is_admin_member(interaction.user):
            await interaction.response.send_message("Only admins can sync tags manually.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True, thinking=True)
        if not isinstance(interaction.channel, discord.Thread):
            await interaction.followup.send("This only works in a card thread.", ephemeral=True)
            return
        await self.cog.sync_status_from_thread(interaction.channel, actor_id=interaction.user.id, allow_type_sync=True)
        await interaction.followup.send("Tags synced.", ephemeral=True)

    @discord.ui.button(label="Admin Fields", style=discord.ButtonStyle.danger, row=1)
    async def admin_fields(self, interaction: discord.Interaction, _: discord.ui.Button):
        if not is_admin_member(interaction.user):
            await interaction.response.send_message("Only admins can edit admin fields.", ephemeral=True)
            return
        await self._open_modal(interaction, "admin")

    @discord.ui.button(label="Delete Card", style=discord.ButtonStyle.danger, row=1)
    async def delete_card(self, interaction: discord.Interaction, _: discord.ui.Button):
        if not is_admin_member(interaction.user):
            await interaction.response.send_message("Only admins can delete cards.", ephemeral=True)
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
        if not is_admin_member(interaction.user):
            await interaction.response.send_message("Only admins can delete cards.", ephemeral=True)
            return
        if not isinstance(interaction.channel, discord.Thread):
            await interaction.response.send_message("This only works in a card thread.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True, thinking=True)
        deleted = await self.cog.repo.delete_character(self.character["_id"], interaction.user.id, "deleted_from_card_thread")
        if not deleted:
            await interaction.followup.send("I couldn't find this card anymore.", ephemeral=True)
            return
        await interaction.followup.send("Card moved to `cardmaker_deleted`. Deleting this thread now.", ephemeral=True)
        try:
            await interaction.channel.delete(reason=f"Card deleted by {interaction.user} ({interaction.user.id})")
        except discord.HTTPException as exc:
            await self.cog.repo.add_audit(self.character["_id"], interaction.user.id, "card_thread_delete_failed", {"error": str(exc)})
            await interaction.followup.send(f"The MongoDB document was archived, but thread deletion failed: `{exc}`", ephemeral=True)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, _: discord.ui.Button):
        await interaction.response.edit_message(content="Delete cancelled.", view=None)


class CardmakerCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.repo = CardmakerRepo(bot.db)
        self.pending_faceclaim_uploads: dict[tuple[int, int], str] = {}
        self.pending_background_uploads: dict[tuple[int, int], str] = {}

    async def delete_message_quietly(self, message: discord.Message):
        try:
            await message.delete()
        except (discord.Forbidden, discord.NotFound, discord.HTTPException):
            pass

    def is_owner_or_admin(self, member: discord.Member | discord.User, character: dict[str, Any]) -> bool:
        return is_admin_member(member) or str(getattr(member, "id", "")) == str(character.get("userid"))

    async def resolve_character_in_thread(self, ctx: commands.Context) -> dict[str, Any] | None:
        if not isinstance(ctx.channel, discord.Thread):
            await ctx.send("Run this inside the card's forum thread.")
            return None
        character = await self.repo.find_by_thread_id(ctx.channel.id)
        if not character:
            await ctx.send("I don't have a card record linked to this thread.")
            return None
        if not self.is_owner_or_admin(ctx.author, character):
            await ctx.send("You can only manage your own card here.")
            return None
        return character

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

    def tag_by_name(self, forum: discord.ForumChannel, name: str) -> discord.ForumTag | None:
        lowered = name.lower()
        for tag in forum.available_tags:
            if tag.name.lower() == lowered:
                return tag
        return None

    def normalized_tags(self, tags: list[discord.ForumTag] | tuple[discord.ForumTag, ...]) -> set[str]:
        return {tag.name.lower() for tag in tags}

    async def admin_thread_tag_actor_id(self, thread: discord.Thread) -> int | None:
        guild = thread.guild
        bot_member = guild.me
        if not bot_member or not bot_member.guild_permissions.view_audit_log:
            return None
        await asyncio.sleep(1)
        try:
            async for entry in guild.audit_logs(limit=5, action=discord.AuditLogAction.thread_update):
                if getattr(entry.target, "id", None) != thread.id or not entry.user:
                    continue
                member = guild.get_member(entry.user.id)
                if member and is_admin_member(member):
                    return member.id
        except discord.HTTPException:
            return None
        return None

    def desired_tags(
        self,
        forum: discord.ForumChannel,
        character: dict[str, Any],
        current_tags: list[discord.ForumTag] | tuple[discord.ForumTag, ...] | None = None,
        preferred_status: str | None = None,
        preferred_looking: str | None = None,
        preferred_type: str | None = None,
        preserve_current_type: bool = False,
    ) -> list[discord.ForumTag]:
        tags: list[discord.ForumTag] = []
        current_names = self.normalized_tags(current_tags or [])
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
        await self.repo.mark_posted(
            character["_id"],
            guild_id=forum.guild.id,
            forum_channel_id=forum.id,
            thread_id=thread.id,
            starter_message_id=getattr(message, "id", None),
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
            await channel.edit(**edit_kwargs)

        msg = await self.fetch_starter_message(channel, character)
        if msg:
            card_file = await self.make_card_file(character, runtime_images=runtime_images)
            await msg.edit(
                content=starter_body(character),
                attachments=[card_file],
                suppress=True,
                allowed_mentions=discord.AllowedMentions(users=True, roles=False, everyone=False),
            )
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
    ):
        character = await self.repo.find_by_thread_id(thread.id)
        if not character:
            return
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
            )
            current_ids = {tag.id for tag in thread.applied_tags}
            desired_ids = {tag.id for tag in desired_tags}
            if current_ids != desired_ids:
                await thread.edit(applied_tags=desired_tags)

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
            return
        updated = await self.repo.update_fields(
            character["_id"],
            updates,
            actor_id,
            "status_synced_from_tags",
        )
        if updated and allow_type_sync and found_type:
            await self.refresh_thread_from_character(thread, updated, actor_id=actor_id)

    @commands.Cog.listener()
    async def on_thread_update(self, before: discord.Thread, after: discord.Thread):
        if before.applied_tags != after.applied_tags:
            before_names = self.normalized_tags(before.applied_tags)
            after_names = self.normalized_tags(after.applied_tags)
            added_statuses = [name for name in ("active", "hiatus", "retired") if name in after_names and name not in before_names]
            added_looking = [name for name in ("looking for rp", "looking for master", "looking for servant") if name in after_names and name not in before_names]
            added_types = [name for name in ("pc", "npc") if name in after_names and name not in before_names]
            preferred_status = added_statuses[-1] if added_statuses else None
            preferred_looking = added_looking[-1] if added_looking else None
            preferred_type = added_types[-1] if added_types else None
            type_actor_id = await self.admin_thread_tag_actor_id(after) if preferred_type else None
            await self.sync_status_from_thread(
                after,
                actor_id=type_actor_id or 0,
                preferred_status=preferred_status,
                preferred_looking=preferred_looking,
                preferred_type=preferred_type,
                allow_type_sync=type_actor_id is not None,
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
        if not self.is_owner_or_admin(message.author, character):
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
            "`f.card postmany <id/url> ...`, `f.card postall`, `f.card channel #forum`, "
            "`f.card minorchannel #forum`, `f.card panel`, `f.card setdesign <design>`"
        )

    @card_group.command(name="channel")
    @commands.has_permissions(manage_guild=True)
    async def set_channel(self, ctx: commands.Context, channel: discord.ForumChannel):
        await self.repo.set_card_channels(ctx.guild.id, full_channel_id=channel.id)
        await ctx.send(f"Full-character card forum set to {channel.mention}.")

    @card_group.command(name="minorchannel")
    @commands.has_permissions(manage_guild=True)
    async def set_minor_channel(self, ctx: commands.Context, channel: discord.ForumChannel):
        await self.repo.set_card_channels(ctx.guild.id, minor_channel_id=channel.id)
        await ctx.send(f"Minor-character card forum set to {channel.mention}.")

    @card_group.command(name="create")
    @commands.has_permissions(manage_guild=True)
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
            default_design = cfg.get("cardmaker_default_design") or "card2"
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
            await self.repo.add_audit(character["_id"], ctx.author.id, "post_existing_thread_linked", {"thread_id": thread_id})
            await ctx.send(f"`{character.get('name')}` is already posted: <#{thread_id}>")
            return False
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
    @commands.has_permissions(manage_guild=True)
    async def post(self, ctx: commands.Context, *, ref: str):
        character, matches = await self.repo.find_one_by_reference(ref)
        if not character:
            if matches:
                lines = "\n".join(f"- `{m['_id']}`: {m.get('name')}" for m in matches[:10])
                await ctx.send("That reference matches multiple characters. Use the exact character ID:\n" + lines)
            else:
                await ctx.send("No cardmaker character found for that reference.")
            return
        await self.post_character(ctx, character)

    @card_group.command(name="postmany")
    @commands.has_permissions(manage_guild=True)
    async def postmany(self, ctx: commands.Context, *refs: str):
        if not refs:
            await ctx.send("Provide one or more character IDs, doc IDs, or doc URLs.")
            return
        successes = 0
        failures: list[str] = []
        for ref in refs:
            character, matches = await self.repo.find_one_by_reference(ref)
            if not character:
                failures.append(f"{ref}: not found or ambiguous")
                continue
            if await self.post_character(ctx, character):
                successes += 1
            await asyncio.sleep(1)
        await ctx.send(f"Postmany complete. Attempted: {len(refs)}. Found: {successes}. Failures: {len(failures)}")

    @card_group.command(name="postall")
    @commands.has_permissions(manage_guild=True)
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

    @card_group.command(name="panel")
    async def panel(self, ctx: commands.Context):
        character = await self.resolve_character_in_thread(ctx)
        if not character:
            return
        view = CardPanelView(self, character, is_admin=is_admin_member(ctx.author))
        try:
            await ctx.message.delete()
        except (discord.Forbidden, discord.HTTPException):
            pass
        await ctx.send("Card controls", view=view, delete_after=300)

    @card_group.command(name="setdesign")
    async def setdesign(self, ctx: commands.Context, design: str):
        character = await self.resolve_character_in_thread(ctx)
        if not character:
            return
        if not is_admin_member(ctx.author):
            await ctx.send("Only admins can change the card design.")
            return
        updated = await self.repo.update_fields(
            character["_id"],
            {"card.default_design": design},
            ctx.author.id,
            "card_design_changed",
        )
        if updated:
            await self.refresh_thread_from_character(ctx.channel, updated, actor_id=ctx.author.id)
            try:
                await ctx.message.delete()
            except (discord.Forbidden, discord.HTTPException):
                pass
            await ctx.send(f"Design changed to `{design}` and card rerendered.", delete_after=20)

    @card_group.command(name="setdefaultdesign")
    @commands.has_permissions(manage_guild=True)
    async def setdefaultdesign(self, ctx: commands.Context, design: str):
        await self.repo.set_default_design(ctx.guild.id, design)
        await ctx.send(f"Default card design set to `{design}`.")


async def setup(bot: commands.Bot):
    await bot.add_cog(CardmakerCog(bot))
