"""
Data access layer for sheets/incidents/audit (PyMongo-backed).

Responsibilities:
1) sheets collection:
   - Upsert discovered sheets from channel messages (doc_id + owner + url + source msg)
   - Store approved baseline snapshots (per-section text+hash + global hash)
   - Store latest observed hashes (latest check)
   - Maintain quarantine state:
       - status = quarantined
       - incident_id pointer
       - repeats counter if it keeps changing while quarantined

2) sheet_incidents collection:
   - Create a single “open incident” when a change is detected
   - Store which sections changed + hashes + diffs
   - Store the Discord mod message IDs (so the bot can edit the embed)

3) sheet_audit collection:
   - Append-only log for forensics:
       - approved / approved_update
       - incident_opened
       - incident_rejected / dismissed / approved / reverted
       - errors

Implementation notes:
- PyMongo is synchronous, so ALL operations are run via asyncio.to_thread
  to avoid blocking the bot.
- iter_approved_sheets returns a *materialized list* (not a live cursor),
  preventing sync cursors from being held across await points.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Iterable
from bson import ObjectId

def now_utc() -> datetime:
    return datetime.now(timezone.utc)

class SheetRepo:
    """
    Sync PyMongo wrapped in asyncio.to_thread so discord.py stays responsive.
    """
    def __init__(self, db):
        self.sheets = db["sheetwatch_sheets"]
        self.incidents = db["sheetwatch_incidents"]
        self.audit = db["sheetwatch_audit"]

        # Optional: ensure helpful indexes exist (safe to call repeatedly)
        # If you already manage indexes elsewhere, you can remove this.
        asyncio.get_event_loop().create_task(self._ensure_indexes())

    async def _ensure_indexes(self):
        def _do():
            self.sheets.create_index([("guild_id", 1)])
            self.sheets.create_index([("guild_id", 1), ("status", 1)])
            self.sheets.create_index([("guild_id", 1), ("owner_user_id", 1)])
            self.incidents.create_index([("guild_id", 1), ("doc_id", 1), ("status", 1)])
            self.audit.create_index([("guild_id", 1), ("doc_id", 1), ("at", -1)])
        await asyncio.to_thread(_do)

    # ---- sheets ----

    async def upsert_sheet(self, *, doc_id: str, guild_id: int, owner_user_id: int, url: str,
                           source_channel_id: int, source_message_id: int) -> bool:
        def _do():
            result = self.sheets.update_one(
                {"_id": doc_id},
                {
                    "$set": {
                        "guild_id": str(guild_id),
                        "owner_user_id": str(owner_user_id),
                        "url": url,
                        "source_channel_id": str(source_channel_id),
                        "source_message_id": str(source_message_id),
                        "updated_at": now_utc(),
                    },
                    "$setOnInsert": {
                        "is_used": False,
                        "created_at": now_utc()
                    }
                },
                upsert=True
            )
            return result.upserted_id is not None
        return await asyncio.to_thread(_do)

    async def get_sheet(self, doc_id: str) -> Optional[Dict[str, Any]]:
        return await asyncio.to_thread(lambda: self.sheets.find_one({"_id": doc_id}))

    async def iter_approved_sheets(self, guild_id: int) -> Iterable[Dict[str, Any]]:
        """
        Returns a fully materialized list to avoid holding a sync cursor across awaits.
        """
        def _do():
            return list(self.sheets.find({"guild_id": str(guild_id), "approved": {"$exists": True}}))
        return await asyncio.to_thread(_do)

    async def set_latest(self, doc_id: str, current: Dict[str, Any]) -> None:
        def _do():
            self.sheets.update_one(
                {"_id": doc_id},
                {"$set": {
                    "latest": {"checked_at": now_utc(), **current},
                    "last_error": None,
                }}
            )
        await asyncio.to_thread(_do)

    async def set_error(self, doc_id: str, message: str) -> None:
        def _do():
            self.sheets.update_one(
                {"_id": doc_id},
                {"$set": {
                    "status": "error",
                    "last_error": {"message": message, "at": now_utc()},
                }}
            )
        await asyncio.to_thread(_do)

    async def approve_baseline(self, guild_id: int, doc_id: str, approved_by: int, snapshot: Dict[str, Any]) -> None:
        def _do():
            self.sheets.update_one(
                {"_id": doc_id},
                {"$set": {
                    "guild_id": str(guild_id),
                    "approved": {
                        "at": now_utc(),
                        "by_user_id": str(approved_by),
                        **snapshot
                    },
                    "status": "ok",
                    "quarantine": None,
                    "last_error": None,
                }},
                upsert=True
            )
        await asyncio.to_thread(_do)

    async def set_quarantine(self, doc_id: str, incident_id: str, current_global_hash: str) -> None:
        def _do():
            self.sheets.update_one(
                {"_id": doc_id},
                {"$set": {
                    "status": "quarantined",
                    "quarantine": {
                        "active": True,
                        "incident_id": incident_id,
                        "since": now_utc(),
                        "last_seen_global_hash": current_global_hash,
                        "last_checked_at": now_utc(),
                        "repeats": 0,
                    }
                }}
            )
        await asyncio.to_thread(_do)

    async def update_quarantine_repeat(self, doc_id: str, current_global_hash: str) -> None:
        def _do():
            sheet = self.sheets.find_one({"_id": doc_id}, projection={"quarantine": 1})
            q = (sheet or {}).get("quarantine") or {}
            repeats = int(q.get("repeats", 0))
            last_seen = q.get("last_seen_global_hash")
            if last_seen != current_global_hash:
                repeats += 1

            self.sheets.update_one(
                {"_id": doc_id},
                {"$set": {
                    "quarantine.last_seen_global_hash": current_global_hash,
                    "quarantine.last_checked_at": now_utc(),
                    "quarantine.repeats": repeats,
                }}
            )
        await asyncio.to_thread(_do)

    async def clear_quarantine(self, doc_id: str) -> None:
        def _do():
            self.sheets.update_one(
                {"_id": doc_id},
                {"$set": {"status": "ok", "quarantine": None}}
            )
        await asyncio.to_thread(_do)

    async def count_unused_sheets_for_user(self, guild_id: int, owner_user_id: int) -> int:
        def _do() -> int:
            # {is_used: {$ne: true}} includes both `is_used: false` and docs where the field is missing
            return self.sheets.count_documents({
                "guild_id": str(guild_id),
                "owner_user_id": str(owner_user_id),
                "is_used": {"$ne": True}
            })
        return await asyncio.to_thread(_do)

    async def get_all_unused_sheets_for_user(self, guild_id: int, owner_user_id: int) -> list[dict]:
        def _do() -> list[dict]:
            return list(self.sheets.find({
                "guild_id": str(guild_id),
                "owner_user_id": str(owner_user_id),
                "is_used": {"$ne": True}
            }))
        return await asyncio.to_thread(_do)

    async def get_all_used_sheets_for_user(self, guild_id: int, owner_user_id: int) -> list[dict]:
        def _do() -> list[dict]:
            return list(self.sheets.find({
                "guild_id": str(guild_id),
                "owner_user_id": str(owner_user_id),
                "is_used": True
            }))
        return await asyncio.to_thread(_do)

    async def set_sheet_used_status(self, doc_id: str, *, is_used: bool) -> None:
        def _do():
            self.sheets.update_one(
                {"_id": doc_id},
                {"$set": {"is_used": is_used}}
            )
        await asyncio.to_thread(_do)

    # ---- incidents ----

    async def create_incident(self, incident_doc: Dict[str, Any]) -> str:
        def _do():
            res = self.incidents.insert_one(incident_doc)
            return str(res.inserted_id)
        return await asyncio.to_thread(_do)

    async def get_incident(self, incident_id: str) -> Optional[Dict[str, Any]]:
        def _do():
            return self.incidents.find_one({"_id": ObjectId(incident_id)})
        return await asyncio.to_thread(_do)

    async def find_open_incident(self, guild_id: int, doc_id: str) -> Optional[Dict[str, Any]]:
        def _do():
            return self.incidents.find_one({
                "guild_id": str(guild_id), 
                "doc_id": doc_id, 
                "status": "open"
                }, sort=[("_id", -1)]
            )
        return await asyncio.to_thread(_do)

    async def find_open_incident_id(self, guild_id: int, doc_id: str) -> Optional[str]:
        inc = await self.find_open_incident(guild_id, doc_id)
        return str(inc["_id"]) if inc else None

    async def update_incident_content(
        self,
        incident_id: str,
        *,
        changed_keys: list[str] | None = None,
        changed_sections: list[str] | None = None,
        diffs: dict | None = None,
        from_hashes: dict | None = None,
        to_hashes: dict | None = None,
    ) -> None:
        def _do():
            update = {"updated_at": now_utc()}
            if changed_keys is not None:
                update["changed_keys"] = changed_keys
            if changed_sections is not None:
                update["changed_sections"] = changed_sections
            if diffs is not None:
                update["diffs"] = diffs
            if from_hashes is not None:
                update["from_hashes"] = from_hashes
            if to_hashes is not None:
                update["to_hashes"] = to_hashes

            self.incidents.update_one(
                {"_id": ObjectId(incident_id)},
                {"$set": update}
            )
        await asyncio.to_thread(_do)

    async def attach_mod_message(self, incident_id: str, channel_id: int, message_id: int) -> None:
        def _do():
            self.incidents.update_one(
                {"_id": ObjectId(incident_id)},
                {"$set": {"mod_message": {"channel_id": str(channel_id), "message_id": str(message_id)}}}
            )
        await asyncio.to_thread(_do)

    async def resolve_incident(self, incident_id: str, status: str, resolved_by: int, note: str | None = None) -> None:
        def _do():
            self.incidents.update_one(
                {"_id": ObjectId(incident_id)},
                {"$set": {
                    "status": status,
                    "resolved_at": now_utc(),
                    "resolved_by_user_id": str(resolved_by),
                    "resolution_note": note,
                }}
            )
        await asyncio.to_thread(_do)

    # ---- audit ----

    async def add_audit(self, guild_id: int, doc_id: str, owner_user_id: str | None, kind: str, details: Dict[str, Any]) -> None:
        def _do():
            self.audit.insert_one({
                "guild_id": str(guild_id),
                "doc_id": doc_id,
                "owner_user_id": owner_user_id,
                "at": now_utc(),
                "kind": kind,
                "details": details,
            })
        await asyncio.to_thread(_do)
