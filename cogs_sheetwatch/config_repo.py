"""
Guild configuration repository (PyMongo-backed) for sheetwatch.

Responsibilities:
- Store and retrieve per-guild settings in Mongo:
    - tracked_channel_ids: channels containing the @mention + doc URL messages
    - mod_alert_channel_id: where incident alerts are posted
    - check_interval_minutes: how often the periodic scan runs
    - history_scan_limit: how far back to scan in tracked channels (for discovery)
    - max_diff_chars: truncation limit for diffs stored/posted
    - max_sections_to_post: cap to avoid diff spam

Implementation notes:
- Uses synchronous PyMongo under the hood.
- Wraps all DB work in asyncio.to_thread to avoid blocking Discord’s event loop.
"""

from __future__ import annotations
import asyncio
from typing import Any, Dict, List, Optional

DEFAULTS = {
    "check_interval_minutes": 720,   # 12 hours
    "history_scan_limit": 200,
    "max_diff_chars": 3500,
    "max_sections_to_post": 6,

    "max_concurrent_checks": 4,      # throttle
    "per_sheet_delay_seconds": 1.0,
}

class GuildConfigRepo:
    """
    Uses synchronous PyMongo under the hood, wrapped with asyncio.to_thread.
    """
    def __init__(self, db):
        self.col = db["guild_config"]

    async def get(self, guild_id: int) -> Dict[str, Any]:
        def _get():
            cfg = self.col.find_one({"guild_id": str(guild_id)})
            if not cfg:
                cfg = {
                    "guild_id": str(guild_id),
                    "tracked_channel_ids": [],
                    "mod_alert_channel_id": None,
                    **DEFAULTS
                }
                self.col.insert_one(cfg)
            # backfill defaults
            patch = {}
            for k, v in DEFAULTS.items():
                if k not in cfg:
                    cfg[k] = v
                    patch[k] = v
            if patch:
                self.col.update_one({"guild_id": str(guild_id)}, {"$set": patch}, upsert=True)
            return cfg

        return await asyncio.to_thread(_get)

    async def set_mod_channel(self, guild_id: int, channel_id: int) -> None:
        def _set():
            self.col.update_one(
                {"guild_id": str(guild_id)},
                {"$set": {"mod_alert_channel_id": str(channel_id)}},
                upsert=True
            )
        await asyncio.to_thread(_set)

    async def set_tracked_channels(self, guild_id: int, channel_ids: List[int]) -> None:
        def _set():
            self.col.update_one(
                {"guild_id": str(guild_id)},
                {"$set": {"tracked_channel_ids": [str(x) for x in channel_ids]}},
                upsert=True
            )
        await asyncio.to_thread(_set)

    async def set_mod_roles(self, guild_id: int, role_ids: List[int]) -> None:
        def _set():
            self.col.update_one(
                {"guild_id": str(guild_id)},
                {"$set": {"mod_role_ids": [str(x) for x in role_ids]}},
                upsert=True
            )
        await asyncio.to_thread(_set)
