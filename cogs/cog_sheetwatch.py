"""
SheetWatchCog: the orchestration layer for the sheet integrity system.

Responsibilities:
- Auto-discovery:
    - Passive: on_message reads tracked channels and upserts doc_id/owner/url into Mongo
        - Fetch doc, normalize, parse sections, hash, store as approved baseline
    - Active: periodic rescan of recent history to catch missed messages while offline
    
- Periodic checking (check_loop):
    - For each approved sheet:
        - Fetch current doc text via export endpoint
        - Normalize + parse into sections
        - Compare hashes against approved baseline
        - If changed:
            - If not quarantined -> open incident + quarantine + post mod message with buttons
            - If quarantined -> do NOT spam; update repeats if content changed again
        - If reverted to baseline:
            - Clear quarantine
            - Optionally resolve open incident as “reverted”

- Incident handling:
    - Build mod embed (who, doc link, status, changed sections, quarantine repeats)
    - Send mod message with IncidentView and record message IDs in Mongo
    - Refresh/edit the mod message when incident state changes

- Mod actions invoked by buttons:
    - action_approve / action_reject / action_dismiss / action_recheck / action_post_diffs

- Admin configuration commands (prefix f.):
    - f.sheet setmod #channel
    - f.sheet settracked #ch1 #ch2 ...
    - f.sheet rescan
    - f.sheet audit <doc_url>

Notes:
- Uses bot.db (PyMongo) and bot.session (aiohttp) from your existing GrailBot.
- All Mongo operations go through SheetRepo/GuildConfigRepo (which use asyncio.to_thread).
"""

from __future__ import annotations

import io
import discord
from discord.ext import commands, tasks
from discord.raw_models import RawMessageUpdateEvent


from cogs_sheetwatch.config_repo import GuildConfigRepo
from cogs_sheetwatch.repo import SheetRepo
from cogs_sheetwatch.gdocs import GoogleDocsFetcher
from cogs_sheetwatch.processing import (
    extract_doc_id, extract_doc_url,
    normalize_text, parse_sections,
    hash_sections, sections_to_texts,
    global_hash, diff_words,
    extract_pairs_from_message
)
from cogs_sheetwatch.views import IncidentView


import asyncio
from pathlib import Path
async def _dump_debug(doc_id: str, raw: str):
    path = Path("debug_sheets")
    path.mkdir(exist_ok=True)

    formatted = normalize_text(raw)

    file_path = path / f"{doc_id}.txt"
    await asyncio.to_thread(file_path.write_text, formatted, encoding="utf-8")


class SheetWatchCog(commands.Cog):
    """
    Google Doc character sheet anti-tamper system:
    - auto-discovery from tracked channels
    - approve baseline
    - periodic checks
    - incident + quarantine
    - mod actions via buttons
    """

    def __init__(self, bot: commands.Bot):
        import asyncio

        self.bot = bot
        self.cfg_repo = GuildConfigRepo(bot.db)     # PyMongo DB handle
        self.repo = SheetRepo(bot.db)              # PyMongo DB handle
        self.gdocs = GoogleDocsFetcher(bot.session)
        
        # for enqueuing new sheets that do not have an approved baseline yet
        # this is to prevent editing a message with 10 embeds throttling gdoc api
        self.baseline_queue: asyncio.Queue[str] = asyncio.Queue()
        self.baseline_inflight: set[str] = set()  # in-memory dedupe
        self.baseline_worker.start()

        self._initial_check_done = False
        self.check_loop.start()

    def cog_unload(self):
        self.check_loop.cancel()
        self.baseline_worker.cancel()

    @commands.Cog.listener()
    async def on_ready(self):
        """Perform one check loop on startup."""
        if not self._initial_check_done:
            self._initial_check_done = True
            await self.check_loop()

    # -----------------------------
    # Discovery
    # -----------------------------

    async def discover_from_message(self, msg: discord.Message) -> None:
        if not msg.guild:
            return
        if msg.author.bot and msg.webhook_id is None:
            return

        cfg = await self.cfg_repo.get(msg.guild.id)
        tracked = set(cfg.get("tracked_channel_ids", []))
        if str(msg.channel.id) not in tracked:
            return
        
        # If message contains embeds, extract user/url pairs
        pairs = extract_pairs_from_message(msg)

        # If message content includes real mentions, Discord may also populate msg.mentions;
        # we intentionally prefer per-embed parsing above.
        for owner_id, doc_id, doc_url in pairs:
            await self.repo.upsert_sheet(
                doc_id=doc_id,
                guild_id=msg.guild.id,
                owner_user_id=owner_id,
                url=doc_url,
                source_channel_id=msg.channel.id,
                source_message_id=msg.id
            )

            # Enqueue baseline creation if needed (per doc_id)
            sheet = await self.repo.get_sheet(doc_id)
            if sheet and not sheet.get("approved"):
                # enqueue once (dedupe)
                if doc_id not in self.baseline_inflight:
                    self.baseline_inflight.add(doc_id)
                    await self.baseline_queue.put(doc_id)

    # Listen for new messages
    @commands.Cog.listener()
    async def on_message(self, msg: discord.Message):
        await self.discover_from_message(msg)

    # Listen for updated messages
    @commands.Cog.listener()
    async def on_raw_message_edit(self, payload: RawMessageUpdateEvent):
        # Ignore DMs / no guild
        if payload.guild_id is None:
            return

        # Check tracked channel gate FIRST (cheap)
        cfg = await self.cfg_repo.get(payload.guild_id)
        tracked = {str(x) for x in cfg.get("tracked_channel_ids", [])}
        if str(payload.channel_id) not in tracked:
            return

        # Fetch the full message (this gives you content + embeds reliably)
        guild = self.bot.get_guild(payload.guild_id)
        if not guild:
            return

        channel = guild.get_channel(payload.channel_id)
        if not isinstance(channel, discord.TextChannel):
            return

        try:
            msg = await channel.fetch_message(payload.message_id)
        except discord.NotFound:
            return
        except discord.Forbidden:
            return
        except discord.HTTPException:
            return

        # Now run your normal discovery on the real message
        await self.discover_from_message(msg)


    async def active_rescan(self, guild: discord.Guild) -> None:
        cfg = await self.cfg_repo.get(guild.id)
        tracked_ids = [int(x) for x in cfg.get("tracked_channel_ids", [])]
        limit = int(cfg.get("history_scan_limit", 200))

        for ch_id in tracked_ids:
            ch = guild.get_channel(ch_id)
            if not isinstance(ch, discord.TextChannel):
                continue
            async for msg in ch.history(limit=limit):
                await self.discover_from_message(msg)

    # -----------------------------
    # Snapshot + compare
    # -----------------------------
    
    async def build_snapshot(self, doc_id: str, max_diff_chars: int) -> dict:
        raw, fmt = await self.gdocs.fetch_best(doc_id)

        # TEMP DEBUG: dump raw export to disk for parser tuning
        await _dump_debug(doc_id, raw)

        # Detect non-public docs (Google sign-in page) early
        if "accounts.google.com" in raw.lower() and "sign in" in raw.lower():
            raise RuntimeError("Doc export returned a sign-in page. Is the doc public view?")

        normalized = normalize_text(raw)

        # Dynamic: {key: {"title": "...", "text": "..."}}
        sections = parse_sections(normalized)
        sections_txt = sections_to_texts(sections)  # {key: text}
        sections_hash = hash_sections(sections_txt)

        return {
            "sections": {
                k: {
                    "title": sections[k].get("title", k),
                    "hash": sections_hash[k],
                    "text": sections_txt[k],
                }
                for k in sections_txt
            },
            "global_hash": global_hash(sections_hash),
        }


    async def compare_against_approved(self, sheet: dict, max_diff_chars: int) -> tuple[bool, dict]:
        doc_id = sheet["_id"]
        approved = sheet.get("approved")
        if not approved:
            return False, {"reason": "not_approved"}

        raw, fmt = await self.gdocs.fetch_best(doc_id)
        if "accounts.google.com" in raw.lower() and "sign in" in raw.lower():
            raise RuntimeError("Doc export returned a sign-in page. Is the doc public view?")

        normalized = normalize_text(raw)

        # Current dynamic sections
        current_sections = parse_sections(normalized)           # {key: {"title","text"}}
        current_txt = sections_to_texts(current_sections)       # {key: text}
        current_hash = hash_sections(current_txt)               # {key: sha}
        current_global = global_hash(current_hash)

        # Approved snapshot sections (stored in Mongo)
        approved_sections = approved.get("sections", {})        # {key: {"title","hash","text"}}

        approved_keys = set(approved_sections.keys())
        current_keys = set(current_txt.keys())

        added_keys = sorted(current_keys - approved_keys)
        removed_keys = sorted(approved_keys - current_keys)
        common_keys = sorted(approved_keys & current_keys)

        changed_keys: list[str] = []
        changed_sections: list[str] = []   # display labels (human readable)
        diffs: dict[str, str] = {}
        from_hashes: dict[str, str] = {}
        to_hashes: dict[str, str] = {}

        def title_from_current(k: str) -> str:
            return (current_sections.get(k) or {}).get("title") or k

        def title_from_approved(k: str) -> str:
            return (approved_sections.get(k) or {}).get("title") or k

        # A) Added sections => change (Policy A)
        for k in added_keys:
            changed_keys.append(k)
            changed_sections.append(f"[ADDED] {title_from_current(k)}")
            diffs[k] = diff_words("", current_txt.get(k, ""), max_chars=max_diff_chars)

        # B) Removed sections => change (Policy A)
        for k in removed_keys:
            changed_keys.append(k)
            changed_sections.append(f"[REMOVED] {title_from_approved(k)}")
            diffs[k] = diff_words(approved_sections[k].get("text", ""), "", max_chars=max_diff_chars)


        # C) Modified sections
        for k in common_keys:
            if current_hash.get(k) != approved_sections[k].get("hash"):
                changed_keys.append(k)
                changed_sections.append(title_from_approved(k))
                diffs[k] = diff_words(approved_sections[k].get("text",""), current_txt.get(k,""), max_chars=max_diff_chars)

        changed = bool(changed_sections)

        return changed, {
            "changed_keys": changed_keys,
            "changed_sections": changed_sections,
            "diffs": diffs,
            "from_hashes": from_hashes,
            "to_hashes": to_hashes,
            "current": {
                "sections": {k: {"hash": current_hash[k]} for k in current_hash},
                "global_hash": current_global,
            },
            # Optional: can be useful for embeds/UI
            "added_keys": added_keys,
            "removed_keys": removed_keys,
        }


    # -----------------------------
    # Incident embed + mod message
    # -----------------------------

    async def build_incident_embed(self, guild_id: int, incident: dict) -> discord.Embed:
        sheet = await self.repo.get_sheet(incident["doc_id"])
        owner_id = incident.get("owner_user_id")
        owner_mention = f"<@{owner_id}>" if owner_id else "(unknown user)"
        url = (sheet or {}).get("url", "(no url stored)")

        status = incident.get("status", "open").upper()
        changed_sections = incident.get("changed_sections", [])

        e = discord.Embed(
            title="⚠️ Approved character sheet changed",
            description=f"**Owner:** {owner_mention}\n**Doc:** {url}\n**Status:** {status}",
        )
        if changed_sections:
            e.add_field(name="Changed sections", value=", ".join(changed_sections), inline=True)

        if sheet and sheet.get("status") == "quarantined":
            q = sheet.get("quarantine") or {}
            e.add_field(name="Quarantine", value=f"Active: {q.get('active')}\nRepeats: {q.get('repeats', 0)}", inline=True)

        if incident.get("resolved_at"):
            resolved_at_dt = incident["resolved_at"]
            unix_timestamp = int(resolved_at_dt.timestamp())
            e.add_field(name="Resolved at", value=f"<t:{unix_timestamp}:f>", inline=True)
            rb = incident.get("resolved_by_user_id")
            e.add_field(name="Resolved by", value=f"<@{rb}>" if rb else "(unknown)", inline=True)
            if incident.get("resolution_note"):
                e.add_field(name="Note", value=incident["resolution_note"], inline=False)

        return e

    async def send_incident_message(self, guild: discord.Guild, incident_id: str, doc_id: str) -> None:
        cfg = await self.cfg_repo.get(guild.id)
        mod_ch_id = cfg.get("mod_alert_channel_id")
        if not mod_ch_id:
            return

        ch = guild.get_channel(int(mod_ch_id))
        if not isinstance(ch, discord.TextChannel):
            return

        inc = await self.repo.get_incident(incident_id)
        if not inc:
            return

        embed = await self.build_incident_embed(guild.id, inc)
        view = IncidentView(self, incident_id=incident_id, doc_id=doc_id)

        msg = await ch.send(embed=embed, view=view)
        await self.repo.attach_mod_message(incident_id, ch.id, msg.id)

    async def refresh_incident_message(self, guild_id: int, incident_id: str) -> None:
        inc = await self.repo.get_incident(incident_id)
        if not inc:
            return
        mm = inc.get("mod_message")
        if not mm:
            return

        guild = self.bot.get_guild(guild_id)
        if not guild:
            return
        ch = guild.get_channel(int(mm["channel_id"]))
        if not isinstance(ch, discord.TextChannel):
            return

        try:
            msg = await ch.fetch_message(int(mm["message_id"]))
        except Exception:
            return

        embed = await self.build_incident_embed(guild_id, inc)
        status = inc.get("status", "open")
        view = None
        if status in ("open", "rejected"):
            view = IncidentView(
                self,
                incident_id=incident_id,
                doc_id=inc["doc_id"],
                incident_status=status
            )
        await msg.edit(embed=embed, view=view)

    # -----------------------------
    # Incident opening
    # -----------------------------

    async def open_incident(self, guild: discord.Guild, sheet: dict, info: dict) -> str:
        # Safety guard: avoid duplicate incidents
        existing = await self.repo.find_open_incident(guild.id, sheet["_id"])
        if existing:
            # Already alerted mods; don't create another.
            return

        inc_doc = {
            "guild_id": str(guild.id),
            "doc_id": sheet["_id"],
            "owner_user_id": sheet.get("owner_user_id"),
            "opened_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc),
            "status": "open",
            "changed_sections": info["changed_sections"],   # display
            "changed_keys": info["changed_keys"],           # keys
            "diffs": info["diffs"],                         # keyed by keys
            "from_hashes": info["from_hashes"],
            "to_hashes": info["to_hashes"],
            "source": {
                "channel_id": sheet.get("source_channel_id"),
                "message_id": sheet.get("source_message_id"),
            }
        }

        incident_id = await self.repo.create_incident(inc_doc)
        await self.repo.set_quarantine(sheet["_id"], incident_id, info["current"]["global_hash"])

        await self.repo.add_audit(
            guild.id, sheet["_id"], sheet.get("owner_user_id"),
            "incident_opened",
            {"incident_id": incident_id, "changed_sections": info["changed_sections"]}
        )

        await self.send_incident_message(guild, incident_id, sheet["_id"])
        return incident_id

    # -----------------------------
    # Mod actions
    # -----------------------------

    async def action_approve(self, guild_id: int, doc_id: str, incident_id: str, mod_user_id: int) -> None:
        cfg = await self.cfg_repo.get(guild_id)
        snap = await self.build_snapshot(doc_id, int(cfg["max_diff_chars"]))

        await self.repo.approve_baseline(guild_id, doc_id, mod_user_id, snap)
        await self.repo.resolve_incident(incident_id, "approved", mod_user_id)
        await self.repo.clear_quarantine(doc_id)

        sheet = await self.repo.get_sheet(doc_id)
        await self.repo.add_audit(guild_id, doc_id, (sheet or {}).get("owner_user_id"), "approved_update",
                                  {"incident_id": incident_id, "by": str(mod_user_id)})

        await self.refresh_incident_message(guild_id, incident_id)

    async def action_reject(self, guild_id: int, doc_id: str, incident_id: str, mod_user_id: int) -> None:
        await self.repo.resolve_incident(incident_id, "rejected", mod_user_id, note="Changes not approved.")
        # strict: keep quarantine
        sheet = await self.repo.get_sheet(doc_id)
        await self.repo.add_audit(guild_id, doc_id, (sheet or {}).get("owner_user_id"), "incident_rejected",
                                  {"incident_id": incident_id, "by": str(mod_user_id)})

        await self.refresh_incident_message(guild_id, incident_id)

    async def action_dismiss(self, guild_id: int, doc_id: str, incident_id: str, mod_user_id: int) -> None:
        await self.repo.resolve_incident(incident_id, "dismissed", mod_user_id, note="Dismissed by moderator.")
        await self.repo.clear_quarantine(doc_id)

        sheet = await self.repo.get_sheet(doc_id)
        await self.repo.add_audit(guild_id, doc_id, (sheet or {}).get("owner_user_id"), "incident_dismissed",
                                  {"incident_id": incident_id, "by": str(mod_user_id)})

        await self.refresh_incident_message(guild_id, incident_id)

    async def action_recheck(self, guild_id: int, doc_id: str, incident_id: str) -> bool:
        cfg = await self.cfg_repo.get(guild_id)
        sheet = await self.repo.get_sheet(doc_id)
        if not sheet:
            return False

        changed, info = await self.compare_against_approved(sheet, int(cfg["max_diff_chars"]))
        await self.repo.set_latest(doc_id, info.get("current", {}))

        if changed:
            #  overwrite incident diffs + changed lists to the newest snapshot
            await self.repo.update_incident_content(
                incident_id,
                changed_keys=info.get("changed_keys") or info.get("changed_sections") or [],
                changed_sections=info.get("changed_sections", []),
                diffs=info.get("diffs", {}),
                from_hashes=info.get("from_hashes", {}),
                to_hashes=info.get("to_hashes", {}),
            )

            await self.repo.update_quarantine_repeat(doc_id, info["current"]["global_hash"])
        else:
            await self.repo.resolve_incident(incident_id, "reverted", 0, note="Content matches baseline again.")
            await self.repo.clear_quarantine(doc_id)

        await self.refresh_incident_message(guild_id, incident_id)
        return changed

    async def action_post_diffs(self, guild_id: int, incident_id: str) -> None:
        cfg = await self.cfg_repo.get(guild_id)
        max_sections = int(cfg.get("max_sections_to_post", 6))

        inc = await self.repo.get_incident(incident_id)
        if not inc:
            return

        guild = self.bot.get_guild(guild_id)
        if not guild:
            return

        # Prefer the incident's recorded mod channel, but fall back to configured mod channel
        ch: discord.TextChannel | None = None
        mm = inc.get("mod_message")
        if mm and mm.get("channel_id"):
            maybe = guild.get_channel(int(mm["channel_id"]))
            if isinstance(maybe, discord.TextChannel):
                ch = maybe

        if ch is None:
            mod_ch_id = cfg.get("mod_alert_channel_id")
            if mod_ch_id:
                maybe = guild.get_channel(int(mod_ch_id))
                if isinstance(maybe, discord.TextChannel):
                    ch = maybe

        if ch is None:
            return  # nowhere to post

        perms = ch.permissions_for(guild.me)
        if not perms.send_messages:
            return

        diffs = inc.get("diffs", {}) or {}
        if not diffs:
            return

        # Prefer changed_keys if present; otherwise just post available diffs
        keys = inc.get("changed_keys") or list(diffs.keys())
        keys = list(keys)[:max_sections]
        if not keys:
            return

        # Fetch sheet baseline once to get titles (optional)
        sheet = await self.repo.get_sheet(inc.get("doc_id"))
        approved_sections = ((sheet or {}).get("approved") or {}).get("sections", {}) if sheet else {}

        for k in keys:
            d = diffs.get(k, "")
            if not d:
                continue

            title = (approved_sections.get(k) or {}).get("title") or k

            # If we can't attach files, truncate long diffs into a message
            if len(d) < 1800 or not perms.attach_files:
                if len(d) > 1800:
                    d = d[:1800] + "\n... (truncated)"
                await ch.send(f"**{title}**\n```diff\n{d}\n```")
            else:
                fp = discord.File(io.BytesIO(d.encode("utf-8")), filename=f"{inc.get('doc_id','doc')}_{k}_diff.txt")
                await ch.send(content=f"**{title}** (diff attached)", file=fp)

    # -----------------------------
    # Periodic loop (interval from config)
    # -----------------------------

    @tasks.loop(minutes=720)  # 12 hours
    async def check_loop(self):
        """
        Periodically checks approved sheets for unauthorized changes.

        This loop:
        - spreads work over time
        - limits concurrent Google Docs fetches
        - avoids hammering Google or Discord
        """

        import asyncio
        import random

        for guild in self.bot.guilds:
            cfg = await self.cfg_repo.get(guild.id)

            max_diff_chars = int(cfg.get("max_diff_chars", 3500))
            max_concurrent = int(cfg.get("max_concurrent_checks", 4))
            delay_s = float(cfg.get("per_sheet_delay_seconds", 1.0))

            sheets = await self.repo.iter_approved_sheets(guild.id)
            if not sheets:
                continue

            # Shuffle so the same sheets aren’t always checked first
            random.shuffle(sheets)

            sem = asyncio.Semaphore(max_concurrent)

            async def _check_one(sheet: dict):
                """
                Core logic for checking a single sheet.
                No concurrency control here.
                """
                doc_id = sheet["_id"]

                changed, info = await self.compare_against_approved(sheet, max_diff_chars)
                await self.repo.set_latest(doc_id, info.get("current", {}))

                if not changed:
                    # Auto-clear quarantine if reverted
                    if sheet.get("status") == "quarantined":
                        q = sheet.get("quarantine") or {}
                        inc_id = q.get("incident_id")
                        if inc_id:
                            await self.repo.resolve_incident(
                                inc_id,
                                "reverted",
                                0,
                                note="Content matches baseline again."
                            )
                            await self.refresh_incident_message(guild.id, inc_id)

                        await self.repo.clear_quarantine(doc_id)
                    return

                # Changed
                if sheet.get("status") == "quarantined":
                    await self.repo.update_quarantine_repeat(
                        doc_id,
                        info["current"]["global_hash"]
                    )
                    q = sheet.get("quarantine") or {}
                    inc_id = q.get("incident_id")
                    if inc_id:
                        await self.refresh_incident_message(guild.id, inc_id)
                    return

                await self.open_incident(guild, sheet, info)

            async def runner(sheet: dict):
                """
                Wraps _check_one with:
                - concurrency limit (semaphore)
                - error handling
                - pacing delay
                """
                async with sem:
                    try:
                        await _check_one(sheet)
                    except Exception as e:
                        await self.repo.set_error(sheet["_id"], str(e))
                        await self.repo.add_audit(
                            guild.id,
                            sheet["_id"],
                            sheet.get("owner_user_id"),
                            "error",
                            {"message": str(e)}
                        )
                    finally:
                        # Gentle pacing between checks
                        await asyncio.sleep(delay_s)

            # Run all checks with controlled concurrency
            await asyncio.gather(*(runner(s) for s in sheets))

    @check_loop.before_loop
    async def before_check_loop(self):
        await self.bot.wait_until_ready()

    # -----------------------------
    # Baseline worker + queue
    # -----------------------------
    
    @tasks.loop(seconds=30)
    async def baseline_worker(self):
        """
        Processes queued doc_ids to create initial approved baselines.
        Throttled and concurrency-limited by design.
        """
        import asyncio

        for guild in self.bot.guilds:
            cfg = await self.cfg_repo.get(guild.id)
            max_concurrent = int(cfg.get("max_concurrent_checks", 4))
            delay_s = float(cfg.get("per_sheet_delay_seconds", 1.0))

            # Drain up to N items per tick to avoid long blocking runs
            batch = []
            max_per_tick = 10
            while len(batch) < max_per_tick and not self.baseline_queue.empty():
                doc_id = await self.baseline_queue.get()
                batch.append(doc_id)

            if not batch:
                return

            sem = asyncio.Semaphore(max_concurrent)  # small concurrency; very gentle

            async def _do(doc_id: str):
                async with sem:
                    try:
                        sheet = await self.repo.get_sheet(doc_id)
                        if not sheet:
                            return
                        if sheet.get("approved"):
                            return  # someone/something already baselined it

                        # Build snapshot + store as approved baseline (AUTO)
                        cfg = await self.cfg_repo.get(int(sheet["guild_id"]))
                        snap = await self.build_snapshot(doc_id, int(cfg.get("max_diff_chars", 3500)))

                        await self.repo.approve_baseline(
                            int(sheet["guild_id"]),
                            doc_id,
                            approved_by=0,          # 0 = system/auto
                            snapshot=snap
                        )
                        await self.repo.add_audit(
                            int(sheet["guild_id"]),
                            doc_id,
                            sheet.get("owner_user_id"),
                            "baseline_auto_approved",
                            {"source_message_id": sheet.get("source_message_id")}
                        )
                    except Exception as e:
                        await self.repo.set_error(doc_id, str(e))
                    finally:
                        self.baseline_inflight.discard(doc_id)
                        self.baseline_queue.task_done() 

                        # Gentle pacing between baselines
                        await asyncio.sleep(delay_s)

            await asyncio.gather(*(_do(d) for d in batch))

    @baseline_worker.before_loop
    async def before_baseline_worker(self):
        await self.bot.wait_until_ready()

    # -----------------------------
    # Commands (prefix f.)
    # -----------------------------

    @commands.group(name="sheet", invoke_without_command=True)
    @commands.has_permissions(manage_guild=True)
    async def sheet_group(self, ctx: commands.Context):
        cfg = await self.cfg_repo.get(ctx.guild.id)
        await ctx.send(
            "Commands:\n"
            "- `f.sheet setmod #channel`\n"
            "- `f.sheet settracked #ch1 #ch2 ...`\n"
            "- `f.sheet rescan`\n"
            "- `f.sheet audit <google_doc_url>`\n"
            f"\nCurrent:\n"
            f"- Mod channel: {cfg.get('mod_alert_channel_id')}\n"
            f"- Tracked: {cfg.get('tracked_channel_ids')}\n"
            f"- Check interval (min): {cfg.get('check_interval_minutes')}"
        )

    @sheet_group.command(name="setmod")
    @commands.has_permissions(manage_guild=True)
    async def setmod(self, ctx: commands.Context, channel: discord.TextChannel):
        await self.cfg_repo.set_mod_channel(ctx.guild.id, channel.id)
        await ctx.send(f"Mod alert channel set to {channel.mention}")

    @sheet_group.command(name="settracked")
    @commands.has_permissions(manage_guild=True)
    async def settracked(self, ctx: commands.Context, *channels: discord.TextChannel):
        if not channels:
            await ctx.send("Provide one or more channels.")
            return
        await self.cfg_repo.set_tracked_channels(ctx.guild.id, [c.id for c in channels])
        await ctx.send("Tracked channels updated:\n" + "\n".join(c.mention for c in channels))

    @sheet_group.command(name="rescan")
    @commands.has_permissions(manage_guild=True)
    async def rescan(self, ctx: commands.Context):
        await self.active_rescan(ctx.guild)
        await ctx.send("Rescan complete.")

    @sheet_group.command(name="audit")
    @commands.has_permissions(manage_guild=True)
    async def audit(self, ctx: commands.Context, doc_url: str):
        doc_id = extract_doc_id(doc_url)
        if not doc_id:
            await ctx.send("That doesn’t look like a Google Docs document URL.")
            return

        # Direct sync cursor -> list() must be in a thread
        import asyncio

        def _fetch():
            col = self.bot.db["sheet_audit"]
            return list(col.find({"guild_id": str(ctx.guild.id), "doc_id": doc_id}).sort("at", -1).limit(10))

        events = await asyncio.to_thread(_fetch)
        if not events:
            await ctx.send("No audit events found.")
            return

        lines = []
        for e in events:
            t = e["at"].strftime("%Y-%m-%d %H:%M UTC") if "at" in e else "unknown"
            kind = e.get("kind", "unknown")
            details = e.get("details", {})
            extra = f" (incident {details['incident_id']})" if "incident_id" in details else ""
            lines.append(f"- {t}: {kind}{extra}")

        await ctx.send("Recent audit:\n" + "\n".join(lines))



    # -----------------------------
    # Commands (prefix f.) for TESTING/CHECKING
    # -----------------------------
    """
        Manually checks a specific sheet right now.
            - If changed and already quarantined → updates repeats + refreshes message
            - If changed and not quarantined → opens incident
            - If not changed and quarantined → resolves as reverted + clears quarantine
    """
    @sheet_group.command(name="check")
    @commands.has_permissions(manage_guild=True)
    async def manual_check(self, ctx: commands.Context, doc_url: str):
        doc_id = extract_doc_id(doc_url)
        if not doc_id:
            await ctx.send("That doesn’t look like a Google Docs document URL.")
            return

        sheet = await self.repo.get_sheet(doc_id)
        if not sheet or str(sheet.get("guild_id")) != str(ctx.guild.id):
            await ctx.send("I don’t have this sheet recorded for this server yet (or it belongs to another server).")
            return

        cfg = await self.cfg_repo.get(ctx.guild.id)
        max_diff_chars = int(cfg.get("max_diff_chars", 3500))

        try:
            changed, info = await self.compare_against_approved(sheet, max_diff_chars)
            await self.repo.set_latest(doc_id, info.get("current", {}))

            if not changed:
                # If it was quarantined, clear it as reverted
                if sheet.get("status") == "quarantined":
                    q = sheet.get("quarantine") or {}
                    inc_id = q.get("incident_id")
                    if inc_id:
                        await self.repo.resolve_incident(inc_id, "reverted", str(ctx.author.id),
                                                        note="Manual check: content matches baseline again.")
                        await self.refresh_incident_message(ctx.guild.id, inc_id)
                    await self.repo.clear_quarantine(doc_id)
                await ctx.send(f"✅ Manual check: **no changes** detected for `{doc_id}`.")
                return

            # Changed
            if sheet.get("status") == "quarantined":
                await self.repo.update_quarantine_repeat(doc_id, info["current"]["global_hash"])
                q = (await self.repo.get_sheet(doc_id) or {}).get("quarantine") or {}
                await ctx.send(f"⚠️ Manual check: **still changed** (quarantined). Repeats: `{q.get('repeats', 0)}`.")
                inc_id = q.get("incident_id")
                if inc_id:
                    await self.refresh_incident_message(ctx.guild.id, inc_id)
                return

            # Not quarantined: open incident (or reuse if one exists)
            open_inc = await self.repo.find_open_incident(ctx.guild.id, doc_id)
            if open_inc:
                inc_id = str(open_inc["_id"])
                # If somehow not quarantined, set quarantine now
                await self.repo.set_quarantine(doc_id, inc_id, info["current"]["global_hash"])
                await self.refresh_incident_message(ctx.guild.id, inc_id)
                await ctx.send(f"⚠️ Manual check: changes detected. Existing incident refreshed: `{inc_id}`.")
                return

            inc_id = await self.open_incident(ctx.guild, sheet, info)
            await ctx.send(f"⚠️ Manual check: changes detected. Incident opened: `{inc_id}`.")

        except Exception as e:
            await self.repo.set_error(doc_id, str(e))
            await self.repo.add_audit(ctx.guild.id, doc_id, sheet.get("owner_user_id"), "error", {"message": str(e)})
            await ctx.send(f"❌ Manual check failed: `{e}`")

    """
        Same as above but check via doc id directly
    """
    @sheet_group.command(name="checkid")
    @commands.has_permissions(manage_guild=True)
    async def manual_check_id(self, ctx: commands.Context, doc_id: str):
        await self.manual_check(ctx, f"https://docs.google.com/document/d/{doc_id}/edit")

    """
        Prints diffs (reuses your existing diff posting logic) without needing an incident already open.
        It does not quarantine / incident-open unless you want it to.
    """
    @sheet_group.command(name="diff")
    @commands.has_permissions(manage_guild=True)
    async def manual_diff(self, ctx: commands.Context, doc_url: str):
        doc_id = extract_doc_id(doc_url)
        if not doc_id:
            await ctx.send("That doesn’t look like a Google Docs document URL.")
            return

        sheet = await self.repo.get_sheet(doc_id)
        if not sheet or str(sheet.get("guild_id")) != str(ctx.guild.id):
            await ctx.send("I don’t have this sheet recorded for this server yet (or it belongs to another server).")
            return

        cfg = await self.cfg_repo.get(ctx.guild.id)
        max_diff_chars = int(cfg.get("max_diff_chars", 3500))

        changed, info = await self.compare_against_approved(sheet, max_diff_chars)
        if not changed:
            await ctx.send("✅ No diffs — content matches approved baseline.")
            return

        # Post a few diffs directly to the channel
        max_sections = int(cfg.get("max_sections_to_post", 6))
        diffs = info.get("diffs", {})
        changed_sections = info.get("changed_sections", [])[:max_sections]

        await ctx.send(f"⚠️ Diffs for `{doc_id}` (showing up to {max_sections} sections):")
        for sec in changed_sections:
            d = diffs.get(sec, "")
            if not d:
                continue
            if len(d) < 1800:
                await ctx.send(f"**{sec}**\n```diff\n{d}\n```")
            else:
                import io
                fp = discord.File(io.BytesIO(d.encode("utf-8")), filename=f"{doc_id}_{sec}_diff.txt")
                await ctx.send(content=f"**{sec}** (diff attached)", file=fp)

    


async def setup(bot: commands.Bot):
    await bot.add_cog(SheetWatchCog(bot))
