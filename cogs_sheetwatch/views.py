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

        await self.cog.action_post_diffs(interaction.guild_id, self.incident_id)
        await interaction.followup.send("Posted diffs to the mod channel.", ephemeral=True)
