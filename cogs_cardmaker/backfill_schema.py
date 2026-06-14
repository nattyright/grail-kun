from __future__ import annotations

import argparse
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from pymongo import MongoClient, ReplaceOne

from cogs_cardmaker.service import generated_starter_body


DEFAULT_DATABASE = "grail-kun"
CHARACTER_COLLECTION = "cardmaker_characters"
AUDIT_COLLECTION = "cardmaker_audit"

ORDERED_FIELDS = [
    "_id",
    "source_doc_id",
    "name",
    "role",
    "scope",
    "type",
    "username",
    "userid",
    "avatar_path",
    "footer_text",
    "source_url",
    "class",
    "nationality",
    "affiliation",
    "occupation",
    "alignment",
    "safe_name",
    "card",
    "discord",
    "admin",
    "status_history",
]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def default_discord_block(doc: dict[str, Any]) -> dict[str, Any]:
    return {
        "starter_body": generated_starter_body(doc),
        "posts": [],
    }


def normalize_discord_block(doc: dict[str, Any]) -> dict[str, Any]:
    existing = dict(doc.get("discord") or {})
    defaults = default_discord_block(doc)
    merged = {}
    for key, value in defaults.items():
        merged[key] = existing.get(key, value)

    posts = list(merged.get("posts") or [])
    if not posts and merged.get("guild_id") and merged.get("thread_id"):
        posts.append({
            "guild_id": merged.get("guild_id"),
            "forum_channel_id": merged.get("forum_channel_id"),
            "thread_id": merged.get("thread_id"),
            "starter_message_id": merged.get("starter_message_id"),
            "card_message_id": merged.get("card_message_id"),
            "post_status": merged.get("post_status") or "posted",
            "last_posted_at": merged.get("last_posted_at"),
            "last_synced_at": merged.get("last_synced_at"),
            "last_error": merged.get("last_error"),
        })
    merged["posts"] = posts

    for key, value in existing.items():
        if key not in merged and key not in {
            "guild_id",
            "forum_channel_id",
            "thread_id",
            "starter_message_id",
            "card_message_id",
            "post_status",
            "last_posted_at",
            "last_synced_at",
            "last_error",
        }:
            merged[key] = value
    return merged


def normalize_doc(doc: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(doc)
    normalized["scope"] = normalized.get("scope") or "full"
    normalized["discord"] = normalize_discord_block(normalized)

    ordered = {}
    for field in ORDERED_FIELDS:
        if field in normalized:
            ordered[field] = normalized[field]

    for field, value in normalized.items():
        if field not in ordered:
            ordered[field] = value
    return ordered


def backfill(args: argparse.Namespace) -> int:
    load_dotenv()
    mongo_uri = args.mongo_uri or os.getenv("MONGODB_URI")
    if not mongo_uri:
        raise RuntimeError("Provide --mongo-uri or set MONGODB_URI.")

    client = MongoClient(mongo_uri)
    db = client[args.database]
    characters = db[CHARACTER_COLLECTION]
    audit = db[AUDIT_COLLECTION]

    docs = list(characters.find({}).sort("name", 1))
    writes = []
    changed = 0
    for doc in docs:
        normalized = normalize_doc(doc)
        if normalized != doc:
            changed += 1
            writes.append(ReplaceOne({"_id": doc["_id"]}, normalized))

    if args.dry_run:
        print(f"Dry run: {changed} of {len(docs)} document(s) need backfill/reorder.")
        return 0

    if writes:
        characters.bulk_write(writes, ordered=False)
        audit.insert_one({
            "character_id": None,
            "actor_id": "system",
            "kind": "cardmaker_schema_backfill",
            "details": {
                "matched": len(docs),
                "changed": changed,
                "fields": ["scope", "discord.starter_body", "discord.posts"],
                "removed_legacy_discord_fields": [
                    "guild_id",
                    "forum_channel_id",
                    "thread_id",
                    "starter_message_id",
                    "card_message_id",
                    "post_status",
                    "last_posted_at",
                    "last_synced_at",
                    "last_error",
                ],
            },
            "created_at": utc_now(),
        })

    print(f"Backfilled/reordered {changed} of {len(docs)} document(s).")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backfill cardmaker MongoDB schema fields.")
    parser.add_argument("--mongo-uri", help="MongoDB connection string. Defaults to MONGODB_URI.")
    parser.add_argument("--database", default=DEFAULT_DATABASE, help="MongoDB database name.")
    parser.add_argument("--dry-run", action="store_true", help="Report changes without writing.")
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(backfill(parse_args()))
