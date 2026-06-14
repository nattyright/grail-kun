from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

from pymongo import ReturnDocument

from cogs_cardmaker.service import generated_starter_body, normalize_username, template_role_for


CHARACTER_COLLECTION = "cardmaker_characters"
DELETED_COLLECTION = "cardmaker_deleted"
AUDIT_COLLECTION = "cardmaker_audit"
CONFIG_COLLECTION = "guild_config"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def default_discord_block(character: dict[str, Any] | None = None) -> dict[str, Any]:
    body = generated_starter_body(character or {}) if character else None
    return {
        "starter_body": body,
        "posts": [],
    }


class CardmakerRepo:
    def __init__(self, db):
        self.db = db
        self.characters = db[CHARACTER_COLLECTION]
        self.deleted = db[DELETED_COLLECTION]
        self.audit = db[AUDIT_COLLECTION]
        self.config = db[CONFIG_COLLECTION]
        asyncio.get_event_loop().create_task(self.ensure_indexes())

    async def ensure_indexes(self) -> None:
        def _do():
            self.characters.create_index("source_doc_id")
            self.characters.create_index("source_url")
            self.characters.create_index("safe_name")
            self.characters.create_index("userid")
            self.characters.create_index("username")
            self.characters.create_index("role")
            self.characters.create_index("scope")
            self.characters.create_index("type")
            self.characters.create_index("admin.status")
            self.characters.create_index("discord.posts.guild_id")
            self.deleted.create_index("deletion.at")
            self.deleted.create_index("deletion.by")
            self.deleted.create_index("deletion.original_id")
            self.audit.create_index([("character_id", 1), ("created_at", -1)])
            self.audit.create_index([("actor_id", 1), ("created_at", -1)])
        await asyncio.to_thread(_do)

    def _backfill_doc(self, doc: dict[str, Any] | None) -> dict[str, Any] | None:
        if not doc:
            return None
        changed = False
        if not doc.get("scope"):
            doc["scope"] = "full"
            changed = True
        discord_block = dict(doc.get("discord") or {})
        defaults = default_discord_block(doc)
        legacy_post = None
        if discord_block.get("guild_id") and discord_block.get("thread_id"):
            legacy_post = {
                "guild_id": discord_block.get("guild_id"),
                "forum_channel_id": discord_block.get("forum_channel_id"),
                "thread_id": discord_block.get("thread_id"),
                "starter_message_id": discord_block.get("starter_message_id"),
                "card_message_id": discord_block.get("card_message_id"),
                "post_status": discord_block.get("post_status") or "posted",
                "last_posted_at": discord_block.get("last_posted_at"),
                "last_synced_at": discord_block.get("last_synced_at"),
                "last_error": discord_block.get("last_error"),
            }
        for key, value in defaults.items():
            if key not in discord_block:
                discord_block[key] = value
                changed = True
        if legacy_post and not discord_block.get("posts"):
            discord_block["posts"] = [legacy_post]
            changed = True
        for key in [
            "guild_id",
            "forum_channel_id",
            "thread_id",
            "starter_message_id",
            "card_message_id",
            "post_status",
            "last_posted_at",
            "last_synced_at",
            "last_error",
        ]:
            if key in discord_block:
                discord_block.pop(key, None)
                changed = True
        doc["discord"] = discord_block
        if changed:
            self.characters.update_one(
                {"_id": doc["_id"]},
                {"$set": {"scope": doc["scope"], "discord": discord_block}},
            )
        return doc

    async def get_character(self, character_id: str) -> dict[str, Any] | None:
        return await asyncio.to_thread(lambda: self._backfill_doc(self.characters.find_one({"_id": character_id})))

    async def find_by_doc_id(self, doc_id: str) -> list[dict[str, Any]]:
        def _do():
            docs = list(self.characters.find({"source_doc_id": doc_id}).sort("name", 1))
            return [self._backfill_doc(doc) for doc in docs if doc]
        return await asyncio.to_thread(_do)

    async def find_one_by_reference(self, ref: str) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
        from cogs_cardmaker.service import extract_doc_id

        doc_id = extract_doc_id(ref)

        def _do():
            direct = self.characters.find_one({"_id": ref})
            if direct:
                direct = self._backfill_doc(direct)
                return direct, [direct]
            if doc_id:
                docs = [self._backfill_doc(doc) for doc in self.characters.find({"source_doc_id": doc_id}).sort("name", 1)]
                docs = [doc for doc in docs if doc]
                return (docs[0] if len(docs) == 1 else None), docs
            docs = [self._backfill_doc(doc) for doc in self.characters.find({"safe_name": ref}).sort("name", 1)]
            docs = [doc for doc in docs if doc]
            return (docs[0] if len(docs) == 1 else None), docs

        return await asyncio.to_thread(_do)

    async def find_by_thread_id(self, thread_id: int) -> dict[str, Any] | None:
        def _do():
            return self._backfill_doc(self.characters.find_one({
                "discord.posts.thread_id": str(thread_id)
            }))
        return await asyncio.to_thread(_do)

    async def list_postable(self, guild_id: int) -> list[dict[str, Any]]:
        def _do():
            docs = list(self.characters.find({
                "admin.status": {"$in": ["active", "Active", None]},
            }).sort("name", 1))
            results = []
            for doc in docs:
                doc = self._backfill_doc(doc)
                if not doc:
                    continue
                posts = (doc.get("discord") or {}).get("posts") or []
                if any(str(p.get("guild_id")) == str(guild_id) for p in posts):
                    continue
                results.append(doc)
            return results
        return await asyncio.to_thread(_do)

    async def create_character(self, character: dict[str, Any]) -> dict[str, Any]:
        def _do():
            self.characters.insert_one(character)
            return self._backfill_doc(character)
        return await asyncio.to_thread(_do)

    async def delete_character(self, character_id: str, actor_id: int | str | None) -> dict[str, Any] | None:
        now = utc_now()

        def _do():
            doc = self.characters.find_one({"_id": character_id})
            if not doc:
                return None
            deleted_doc = dict(doc)
            deleted_doc["deletion"] = {
                "original_id": character_id,
                "at": now,
                "by": str(actor_id) if actor_id is not None else None,
            }
            self.deleted.replace_one({"_id": character_id}, deleted_doc, upsert=True)
            self.characters.delete_one({"_id": character_id})
            self._insert_audit_sync(character_id, actor_id, "card_deleted", {"old": doc})
            return deleted_doc

        return await asyncio.to_thread(_do)

    async def restore_deleted_character(self, character_id: str, actor_id: int | str | None, kind: str, details: dict[str, Any]) -> dict[str, Any] | None:
        def _do():
            deleted_doc = self.deleted.find_one({"_id": character_id})
            if not deleted_doc:
                return None
            restored_doc = dict(deleted_doc)
            restored_doc.pop("deletion", None)
            self.characters.replace_one({"_id": character_id}, restored_doc, upsert=True)
            self.deleted.delete_one({"_id": character_id})
            self._insert_audit_sync(character_id, actor_id, kind, details)
            return restored_doc

        return await asyncio.to_thread(_do)

    async def update_fields(self, character_id: str, fields: dict[str, Any], actor_id: int | str | None, kind: str) -> dict[str, Any] | None:
        now = utc_now()
        fields = dict(fields)
        fields["admin.updated_at"] = now
        if actor_id is not None:
            fields["admin.updated_by"] = str(actor_id)

        def _do():
            old = self.characters.find_one({"_id": character_id}) or {}
            doc = self.characters.find_one_and_update(
                {"_id": character_id},
                {"$set": fields},
                return_document=ReturnDocument.AFTER,
            )
            self._insert_audit_sync(character_id, actor_id, kind, {"fields": fields, "old": old})
            return self._backfill_doc(doc)
        return await asyncio.to_thread(_do)

    async def mark_posted(
        self,
        character_id: str,
        *,
        guild_id: int,
        forum_channel_id: int,
        thread_id: int,
        starter_message_id: int | None,
        resource_message_id: int | None,
        actor_id: int | str | None,
    ) -> None:
        now = utc_now()
        post_doc = {
            "guild_id": str(guild_id),
            "forum_channel_id": str(forum_channel_id),
            "thread_id": str(thread_id),
            "starter_message_id": str(starter_message_id) if starter_message_id else None,
            "resource_message_id": str(resource_message_id) if resource_message_id else None,
            "card_message_id": str(starter_message_id) if starter_message_id else None,
            "post_status": "posted",
            "last_posted_at": now,
            "last_synced_at": now,
            "last_error": None,
        }

        def _do():
            doc = self.characters.find_one({"_id": character_id}) or {}
            discord_block = dict(doc.get("discord") or {})
            posts = list(discord_block.get("posts") or [])
            replaced = False
            for index, existing in enumerate(posts):
                if str(existing.get("guild_id")) == str(guild_id):
                    posts[index] = post_doc
                    replaced = True
                    break
            if not replaced:
                posts.append(post_doc)

            update = {
                "discord.posts": posts,
                "admin.updated_at": now,
            }
            if actor_id is not None:
                update["admin.updated_by"] = str(actor_id)
            self.characters.update_one({"_id": character_id}, {"$set": update})
            self._insert_audit_sync(character_id, actor_id, "card_posted", {"post": post_doc})

        await asyncio.to_thread(_do)

    async def set_resource_message_id(
        self,
        character_id: str,
        *,
        thread_id: int,
        resource_message_id: int,
        actor_id: int | str | None,
    ) -> None:
        now = utc_now()

        def _do():
            doc = self.characters.find_one({"_id": character_id}) or {}
            discord_block = dict(doc.get("discord") or {})
            posts = list(discord_block.get("posts") or [])
            changed = False
            for post in posts:
                if str(post.get("thread_id")) == str(thread_id):
                    post["resource_message_id"] = str(resource_message_id)
                    post["last_synced_at"] = now
                    changed = True
                    break
            if not changed:
                return
            update = {
                "discord.posts": posts,
                "admin.updated_at": now,
            }
            if actor_id is not None:
                update["admin.updated_by"] = str(actor_id)
            self.characters.update_one({"_id": character_id}, {"$set": update})
            self._insert_audit_sync(
                character_id,
                actor_id,
                "card_resource_message_linked",
                {"thread_id": str(thread_id), "resource_message_id": str(resource_message_id)},
            )

        await asyncio.to_thread(_do)

    async def remove_post_for_guild(
        self,
        character_id: str,
        *,
        guild_id: int,
        thread_id: str | int | None,
        actor_id: int | str | None,
    ) -> dict[str, Any] | None:
        now = utc_now()

        def _do():
            doc = self.characters.find_one({"_id": character_id})
            if not doc:
                return None
            discord_block = dict(doc.get("discord") or {})
            old_posts = list(discord_block.get("posts") or [])
            posts = [
                post for post in old_posts
                if not (
                    str(post.get("guild_id")) == str(guild_id)
                    and (thread_id is None or str(post.get("thread_id")) == str(thread_id))
                )
            ]
            if len(posts) == len(old_posts):
                return self._backfill_doc(doc)

            update = {
                "discord.posts": posts,
                "admin.updated_at": now,
            }
            if actor_id is not None:
                update["admin.updated_by"] = str(actor_id)
            self.characters.update_one({"_id": character_id}, {"$set": update})
            self._insert_audit_sync(
                character_id,
                actor_id,
                "stale_card_thread_unlinked",
                {"guild_id": str(guild_id), "thread_id": str(thread_id) if thread_id is not None else None},
            )
            updated = dict(doc)
            discord_block["posts"] = posts
            updated["discord"] = discord_block
            return self._backfill_doc(updated)

        return await asyncio.to_thread(_do)

    async def set_last_error(self, character_id: str, message: str, actor_id: int | str | None = None) -> None:
        await self.update_fields(
            character_id,
            {"discord.last_error": {"message": message, "at": utc_now()}},
            actor_id,
            "error",
        )

    async def set_card_channels(self, guild_id: int, *, full_channel_id: int | None = None, minor_channel_id: int | None = None) -> None:
        update = {}
        if full_channel_id is not None:
            update["cardmaker_full_forum_channel_id"] = str(full_channel_id)
        if minor_channel_id is not None:
            update["cardmaker_minor_forum_channel_id"] = str(minor_channel_id)

        def _do():
            self.config.update_one({"guild_id": str(guild_id)}, {"$set": update}, upsert=True)
        await asyncio.to_thread(_do)

    async def set_default_design(self, guild_id: int, design: str) -> None:
        def _do():
            self.config.update_one(
                {"guild_id": str(guild_id)},
                {"$set": {"cardmaker_default_design": design}},
                upsert=True,
            )
        await asyncio.to_thread(_do)

    async def get_config(self, guild_id: int) -> dict[str, Any]:
        def _do():
            cfg = self.config.find_one({"guild_id": str(guild_id)})
            if not cfg:
                cfg = {"guild_id": str(guild_id)}
                self.config.insert_one(cfg)
            return cfg
        return await asyncio.to_thread(_do)

    async def add_audit(self, character_id: str | None, actor_id: int | str | None, kind: str, details: dict[str, Any]) -> None:
        await asyncio.to_thread(self._insert_audit_sync, character_id, actor_id, kind, details)

    def _insert_audit_sync(self, character_id: str | None, actor_id: int | str | None, kind: str, details: dict[str, Any]) -> None:
        self.audit.insert_one({
            "character_id": character_id,
            "actor_id": str(actor_id) if actor_id is not None else None,
            "kind": kind,
            "details": details,
            "created_at": utc_now(),
        })


def build_character_doc(fields: dict[str, str], *, player_user: Any, created_by: int | str, default_design: str = "default-rotw") -> dict[str, Any]:
    from cogs_cardmaker.service import extract_doc_id, safe_name_for

    if fields.get("faceclaim") or fields.get("avatar_path"):
        raise ValueError("Do not use --faceclaim or --avatar_path in create templates. Attach a faceclaim image to the create message instead.")

    source_url = fields.get("doc") or fields.get("source_url")
    doc_id = extract_doc_id(source_url)
    if not doc_id:
        raise ValueError("Create template needs a valid --doc Google Docs URL or ID.")
    name = fields.get("name")
    if not name:
        raise ValueError("Create template needs --name.")
    safe_name = fields.get("safe_name") or safe_name_for(name)
    now = utc_now()
    username = normalize_username(getattr(player_user, "name", None) or getattr(player_user, "display_name", None))
    role = fields.get("role") or "Master"
    template_role = template_role_for({"role": role})
    if template_role == "servant":
        missing = [key for key in ("class", "nationality") if not fields.get(key)]
        extra = [key for key in ("affiliation", "occupation") if fields.get(key)]
        errors = []
        if missing:
            errors.append("Servant create templates need --class and --nationality")
        if extra:
            errors.append("Servant create templates should not include --affiliation or --occupation")
        if errors:
            raise ValueError(". ".join(errors) + ".")
    else:
        missing = [key for key in ("affiliation", "occupation") if not fields.get(key)]
        extra = [key for key in ("class", "nationality") if fields.get(key)]
        errors = []
        if missing:
            errors.append("Master and non-Servant create templates need --affiliation and --occupation")
        if extra:
            errors.append("Master and non-Servant create templates should not include --class or --nationality")
        if errors:
            raise ValueError(". ".join(errors) + ".")

    doc = {
        "_id": f"{doc_id}:{safe_name}",
        "source_doc_id": doc_id,
        "name": name,
        "role": role,
        "scope": (fields.get("scope") or "full").lower(),
        "type": (fields.get("type") or "PC").upper(),
        "username": username,
        "userid": str(player_user.id),
        "avatar_path": None,
        "footer_text": fields.get("footer") or fields.get("footer_text"),
        "source_url": source_url,
        "class": fields.get("class"),
        "nationality": fields.get("nationality"),
        "affiliation": fields.get("affiliation"),
        "occupation": fields.get("occupation"),
        "alignment": fields.get("alignment"),
        "safe_name": safe_name,
        "card": {
            "default_design": fields.get("design") or default_design,
            "last_rendered_at": None,
        },
        "discord": default_discord_block(),
        "admin": {
            "status": "active",
            "created_by": str(created_by),
            "created_at": now,
            "updated_by": str(created_by),
            "updated_at": now,
        },
        "status_history": [
            {"from": None, "to": "active", "changed_by": str(created_by), "changed_at": now}
        ],
    }
    doc["discord"]["starter_body"] = generated_starter_body(doc)
    return doc
