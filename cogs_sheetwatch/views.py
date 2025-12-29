"""
Discord UI (buttons) for incident resolution.

Responsibilities:
- Provide a persistent View attached to the mod alert message with buttons:
    - Approve changes: update baseline to current doc content, clear quarantine
    - Reject changes: keep quarantine (strict mode) until reverted/approved
    - Dismiss: clear quarantine without changing baseline (false positive)
    - Recheck now: run an immediate check and update incident/quarantine state
    - Post diffs: post diff blocks/attachments in the mod channel

Permission model:
- Only users with Manage Server can click actions (guarded in _guard()).

Important:
- This file contains *no Mongo logic* and *no Google fetching*.
  It calls methods on the cog (controller) which does the work.
"""

from __future__ import annotations
import discord
from datetime import datetime, timezone

class IncidentView(discord.ui.View):
    def __init__(self, cog, *, incident_id: str, doc_id: str, incident_status: str):
        super().__init__(timeout=None)
        self.cog = cog
        self.incident_id = incident_id
        self.doc_id = doc_id

        if incident_status == "rejected":
            self.reject.disabled = True

    async def _guard(self, interaction: discord.Interaction) -> bool:
        # Check #1: Admin permission
        if interaction.user.guild_permissions.manage_guild:
            pass  # Admin is always allowed, proceed to status check
        else:
            # Check #2: Moderator role
            cfg = await self.cog.cfg_repo.get(interaction.guild_id)
            mod_role_ids = {int(r) for r in cfg.get("mod_role_ids", [])}

            if not mod_role_ids:  # No roles configured, so only admins
                await interaction.response.send_message("You don’t have permission to do that.", ephemeral=True)
                return False

            author_role_ids = {r.id for r in interaction.user.roles}
            if mod_role_ids.isdisjoint(author_role_ids):  # User has none of the roles
                await interaction.response.send_message("You don’t have permission to do that.", ephemeral=True)
                return False

        # If we get here, the user has permission. Now check incident status.
        inc = await self.cog.repo.get_incident(self.incident_id)
        if not inc or inc.get("status") not in ("open", "rejected"):
            await interaction.response.send_message("This incident is already resolved and cannot be modified.", ephemeral=True)
            return False

        return True

    @discord.ui.button(label="Approve changes", style=discord.ButtonStyle.success)
    async def approve(self, interaction: discord.Interaction, _):
        if not await self._guard(interaction):
            return
        await interaction.response.defer(ephemeral=True)

        await self.cog.action_approve(interaction.guild_id, self.doc_id, self.incident_id, interaction.user.id)
        await interaction.followup.send("Approved. Baseline updated and quarantine cleared.", ephemeral=True)

    @discord.ui.button(label="Reject changes", style=discord.ButtonStyle.danger)
    async def reject(self, interaction: discord.Interaction, _):
        if not await self._guard(interaction):
            return
        await interaction.response.defer(ephemeral=True)

        await self.cog.action_reject(interaction.guild_id, self.doc_id, self.incident_id, interaction.user.id)
        await interaction.followup.send("Rejected. Sheet stays quarantined until reverted or approved.", ephemeral=True)

    @discord.ui.button(label="Dismiss", style=discord.ButtonStyle.secondary)
    async def dismiss(self, interaction: discord.Interaction, _):
        if not await self._guard(interaction):
            return
        await interaction.response.defer(ephemeral=True)

        await self.cog.action_dismiss(interaction.guild_id, self.doc_id, self.incident_id, interaction.user.id)
        await interaction.followup.send("Dismissed. Quarantine cleared; baseline unchanged.", ephemeral=True)

    @discord.ui.button(label="Recheck now", style=discord.ButtonStyle.primary)
    async def recheck(self, interaction: discord.Interaction, _):
        if not await self._guard(interaction):
            return
        await interaction.response.defer(ephemeral=True)

        changed = await self.cog.action_recheck(interaction.guild_id, self.doc_id, self.incident_id)
        await interaction.followup.send(
            "Rechecked: still changed." if changed else "Rechecked: it matches baseline now.",
            ephemeral=True
        )

    @discord.ui.button(label="Post diffs", style=discord.ButtonStyle.secondary)
    async def post_diffs(self, interaction: discord.Interaction, _):
        if not await self._guard(interaction):
            return
        await interaction.response.defer(ephemeral=True)

        await self.cog.action_post_diffs(interaction.guild.id, self.incident_id)
        await interaction.followup.send("Posted diffs to the mod channel.", ephemeral=True)


class UserSheetReviewView(discord.ui.View):
    def __init__(self, cog, *, owner: discord.User, sheets: list[dict], mode: str = 'unused'):
        super().__init__(timeout=3600)  # 1 hour timeout
        self.cog = cog
        self.owner = owner
        self.sheets = sheets
        self.initial_count = len(sheets)
        self.current_index = 0
        self.mode = mode
        self.message = None

    async def on_timeout(self):
        try:
            if self.message:
                for item in self.children:
                    item.disabled = True
                await self.message.edit(content="*This review session has timed out.*", view=self)
        except discord.NotFound:
            pass # Message was deleted

    async def _guard(self, interaction: discord.Interaction) -> bool:
        if not interaction.user.guild_permissions.manage_guild:
            await interaction.response.send_message("You don’t have permission to do that.", ephemeral=True)
            return False
        return True

    def _build_embed(self) -> discord.Embed:
        sheet = self.sheets[self.current_index]
        is_sheet_used = sheet.get('is_used', False)
        status_text = "Used" if is_sheet_used else "Unused"
        
        mode_text = "Unused" if self.mode == "unused" else "Used"
        title = f"Reviewing {mode_text} Sheets for {self.owner.display_name}"

        if self.mode == 'unused':
            current_count = sum(1 for s in self.sheets if not s.get('is_used', False))
            count_text = f"({current_count} Unused)"
        else:
            current_count = sum(1 for s in self.sheets if s.get('is_used', False))
            count_text = f"({current_count} Used)"


        e = discord.Embed(
            title=title,
            description=f"Sheet **{self.current_index + 1} of {self.initial_count}** {count_text}",
            color=discord.Color.green() if is_sheet_used else discord.Color.gold()
        )
        e.add_field(name="Sheet URL", value=sheet.get("url", "(no url)"), inline=False)
        e.add_field(name="Status", value=status_text, inline=True)
        
        last_changed_by = sheet.get("is_used_last_changed_by_user_id")
        last_changed_at = sheet.get("is_used_last_changed_at")

        if last_changed_by and last_changed_at:
            unix_timestamp = int(last_changed_at.timestamp())
            e.add_field(
                name="Last Status Change",
                value=f"By <@{last_changed_by}> at <t:{unix_timestamp}:f>",
                inline=True
            )

        e.set_footer(text=f"Doc ID: {sheet['_id']}")
        return e

    def _update_buttons(self):
        if not self.sheets:
            for item in self.children:
                item.disabled = True
            self.stop()
            return

        self.prev_sheet.disabled = self.current_index == 0
        self.next_sheet.disabled = self.current_index >= len(self.sheets) - 1
        
        # Action buttons
        current_sheet_is_used = self.sheets[self.current_index].get('is_used', False)
        self.set_used.disabled = current_sheet_is_used
        self.set_unused.disabled = not current_sheet_is_used

    async def _update_view(self, interaction: discord.Interaction):
        self._update_buttons()
        embed = self._build_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Previous", style=discord.ButtonStyle.secondary, custom_id="prev_sheet")
    async def prev_sheet(self, interaction: discord.Interaction, _):
        if not await self._guard(interaction): return
        if self.current_index > 0:
            self.current_index -= 1
        await self._update_view(interaction)

    @discord.ui.button(label="Next", style=discord.ButtonStyle.secondary, custom_id="next_sheet")
    async def next_sheet(self, interaction: discord.Interaction, _):
        if not await self._guard(interaction): return
        if self.current_index < len(self.sheets) - 1:
            self.current_index += 1
        await self._update_view(interaction)

    @discord.ui.button(label="Set as Used", style=discord.ButtonStyle.success)
    async def set_used(self, interaction: discord.Interaction, _):
        if not await self._guard(interaction): return

        sheet = self.sheets[self.current_index]
        await self.cog.action_set_sheet_used(
            doc_id=sheet["_id"],
            is_used=True,
            mod_user_id=interaction.user.id,
            interaction=interaction
        )
        # Update local state and redraw
        self.sheets[self.current_index]['is_used'] = True
        self.sheets[self.current_index]['is_used_last_changed_by_user_id'] = str(interaction.user.id)
        self.sheets[self.current_index]['is_used_last_changed_at'] = datetime.now(timezone.utc)
        await self._update_view(interaction)

    @discord.ui.button(label="Set as Unused", style=discord.ButtonStyle.danger)
    async def set_unused(self, interaction: discord.Interaction, _):
        if not await self._guard(interaction): return

        sheet = self.sheets[self.current_index]
        await self.cog.action_set_sheet_used(
            doc_id=sheet["_id"],
            is_used=False,
            mod_user_id=interaction.user.id,
            interaction=interaction
        )
        # Update local state and redraw
        self.sheets[self.current_index]['is_used'] = False
        self.sheets[self.current_index]['is_used_last_changed_by_user_id'] = str(interaction.user.id)
        self.sheets[self.current_index]['is_used_last_changed_at'] = datetime.now(timezone.utc)
        await self._update_view(interaction)


    @discord.ui.button(label="Close Session", style=discord.ButtonStyle.grey)
    async def close_session(self, interaction: discord.Interaction, _):
        if not await self._guard(interaction): return
        
        for item in self.children:
            item.disabled = True
        
        embed = discord.Embed(
            title="Session Closed",
            description="This review session has been manually closed.",
            color=discord.Color.default()
        )
        await interaction.response.edit_message(embed=embed, view=self)
        self.stop()

