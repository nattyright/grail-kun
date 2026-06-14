import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from pymongo import MongoClient, ReplaceOne
from pymongo.errors import DuplicateKeyError, PyMongoError


DEFAULT_INPUT = Path("characters") / "_batch_import.json"
DEFAULT_DATABASE = "grail-kun"
CHARACTER_COLLECTION = "cardmaker_characters"
AUDIT_COLLECTION = "cardmaker_audit"

CHARACTER_FIELDS = [
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
]

SYSTEM_FIELDS = {
    "_id",
    "source_doc_id",
    "card",
    "discord",
    "admin",
    "status_history",
}


def utc_now():
    return datetime.now(timezone.utc)


def extract_google_doc_id(source_url):
    match = re.search(r"/d/([^/?#]+)", source_url or "")
    if not match:
        raise ValueError(f"Could not extract Google Doc ID from source_url: {source_url!r}")
    return match.group(1)


def load_characters(path):
    with open(path, "r", encoding="utf-8") as handle:
        data = json.load(handle)

    if not isinstance(data, list):
        raise ValueError(f"Expected a JSON array in {path}")
    for index, item in enumerate(data, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"Expected object at index {index - 1}")
    return data


def normalize_character(item, now, default_status, default_design):
    source_doc_id = extract_google_doc_id(item.get("source_url"))
    safe_name = item.get("safe_name")
    if not safe_name:
        raise ValueError(f"Missing safe_name for {item.get('name')!r}")
    userid = item.get("userid")

    doc = {
        "_id": f"{source_doc_id}:{safe_name}",
        "source_doc_id": source_doc_id,
    }
    for field in CHARACTER_FIELDS:
        doc[field] = item.get(field)

    doc["card"] = {
        "default_design": default_design,
        "last_rendered_at": None,
    }
    doc["discord"] = {
        "starter_body": None,
        "posts": [],
    }
    doc["admin"] = {
        "status": default_status,
        "created_by": userid,
        "created_at": now,
        "updated_by": userid,
        "updated_at": now,
    }
    doc["status_history"] = [
        {
            "from": None,
            "to": default_status,
            "changed_by": userid,
            "changed_at": now,
        }
    ]
    if not doc.get("scope"):
        doc["scope"] = "full"
    return doc


def validate_unique_ids(docs):
    seen = {}
    duplicates = []
    for doc in docs:
        if doc["_id"] in seen:
            duplicates.append((doc["_id"], seen[doc["_id"]], doc.get("name")))
        else:
            seen[doc["_id"]] = doc.get("name")

    if duplicates:
        lines = [
            f"{doc_id}: {first_name!r} and {second_name!r}"
            for doc_id, first_name, second_name in duplicates
        ]
        raise ValueError("Duplicate character IDs in import file:\n" + "\n".join(lines))


def comparable_fields(doc):
    return {
        key: value
        for key, value in doc.items()
        if key not in SYSTEM_FIELDS
    }


def build_changes(existing, incoming):
    changes = {}
    existing_values = comparable_fields(existing)
    incoming_values = comparable_fields(incoming)

    for key, new_value in incoming_values.items():
        old_value = existing_values.get(key)
        if old_value != new_value:
            changes[key] = {
                "from": old_value,
                "to": new_value,
            }
    return changes


def merge_existing(existing, incoming, now):
    merged = dict(incoming)
    merged["card"] = {
        **incoming["card"],
        **existing.get("card", {}),
    }
    merged["discord"] = {
        **incoming["discord"],
        **existing.get("discord", {}),
    }

    existing_admin = existing.get("admin", {})
    merged["admin"] = {
        **incoming["admin"],
        "created_by": existing_admin.get("created_by", incoming["admin"]["created_by"]),
        "created_at": existing_admin.get("created_at", incoming["admin"]["created_at"]),
        "updated_by": incoming["userid"],
        "updated_at": now,
    }

    existing_status = existing_admin.get("status")
    incoming_status = incoming["admin"]["status"]
    history = list(existing.get("status_history", []))
    if existing_status != incoming_status:
        history.append({
            "from": existing_status,
            "to": incoming_status,
            "changed_by": incoming["userid"],
            "changed_at": now,
        })
    merged["status_history"] = history or incoming["status_history"]
    return merged


def reorder_existing(existing, incoming):
    reordered = dict(incoming)
    reordered["card"] = existing.get("card", incoming["card"])
    reordered["discord"] = {
        **incoming["discord"],
        **existing.get("discord", {}),
    }
    reordered["admin"] = existing.get("admin", incoming["admin"])
    reordered["status_history"] = existing.get("status_history", incoming["status_history"])
    return reordered


def ensure_indexes(db):
    characters = db[CHARACTER_COLLECTION]
    audit = db[AUDIT_COLLECTION]

    characters.create_index("source_doc_id")
    characters.create_index("source_url")
    characters.create_index("safe_name")
    characters.create_index("userid")
    characters.create_index("username")
    characters.create_index("role")
    characters.create_index("admin.status")
    characters.create_index("discord.posts.guild_id")

    audit.create_index([("character_id", 1), ("created_at", -1)])
    audit.create_index([("actor_id", 1), ("created_at", -1)])


def import_characters(args):
    now = utc_now()
    items = load_characters(args.input)
    docs = [
        normalize_character(item, now, args.status, args.default_design)
        for item in items
    ]
    validate_unique_ids(docs)

    if args.dry_run:
        print(f"Dry run OK: {len(docs)} character(s) ready for import.")
        print(f"Target database: {args.database}")
        print(f"Collections: {CHARACTER_COLLECTION}, {AUDIT_COLLECTION}")
        return 0

    mongo_uri = args.mongo_uri or os.environ.get("MONGODB_URI")
    if not mongo_uri:
        raise ValueError("Provide --mongo-uri or set MONGODB_URI.")

    client = MongoClient(mongo_uri)
    db = client[args.database]
    characters = db[CHARACTER_COLLECTION]
    audit = db[AUDIT_COLLECTION]

    ensure_indexes(db)

    existing_by_id = {
        doc["_id"]: doc
        for doc in characters.find({"_id": {"$in": [doc["_id"] for doc in docs]}})
    }

    writes = []
    audit_events = []
    inserted = 0
    updated = 0
    reordered = 0
    unchanged = 0

    for incoming in docs:
        existing = existing_by_id.get(incoming["_id"])
        if existing:
            changes = build_changes(existing, incoming)
            if not changes:
                if args.reorder_existing:
                    merged = reorder_existing(existing, incoming)
                    writes.append(ReplaceOne({"_id": incoming["_id"]}, merged))
                    reordered += 1
                else:
                    unchanged += 1
                continue

            merged = merge_existing(existing, incoming, now)
            writes.append(ReplaceOne({"_id": incoming["_id"]}, merged))
            audit_events.append({
                "character_id": incoming["_id"],
                "actor_id": incoming["userid"],
                "created_at": now,
                "changes": changes,
            })
            updated += 1
        else:
            writes.append(ReplaceOne({"_id": incoming["_id"]}, incoming, upsert=True))
            audit_events.append({
                "character_id": incoming["_id"],
                "actor_id": incoming["userid"],
                "created_at": now,
                "changes": {
                    "_created": {
                        "from": None,
                        "to": True,
                    }
                },
            })
            inserted += 1

    if not args.reorder_existing:
        unchanged += reordered

    if writes:
        characters.bulk_write(writes, ordered=False)
    if audit_events:
        audit.insert_many(audit_events, ordered=False)

    print(f"Imported {len(docs)} character(s).")
    print(f"Inserted: {inserted}")
    print(f"Updated: {updated}")
    print(f"Reordered: {reordered}")
    print(f"Unchanged: {unchanged}")
    print(f"Audit events: {len(audit_events)}")
    return 0


def parse_args():
    parser = argparse.ArgumentParser(description="Import cardmaker characters into MongoDB.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT, help="Migration JSON array to import.")
    parser.add_argument("--mongo-uri", help="MongoDB connection string. Prefer MONGODB_URI for regular use.")
    parser.add_argument("--database", default=DEFAULT_DATABASE, help="MongoDB database name.")
    parser.add_argument("--status", default="active", help="Admin status assigned to imported characters.")
    parser.add_argument("--default-design", default="default-rotw", help="Default card design for imported characters.")
    parser.add_argument("--reorder-existing", action="store_true", help="Replace unchanged existing documents to restore readable field order.")
    parser.add_argument("--dry-run", action="store_true", help="Validate and summarize without writing to MongoDB.")
    return parser.parse_args()


if __name__ == "__main__":
    try:
        raise SystemExit(import_characters(parse_args()))
    except (DuplicateKeyError, PyMongoError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1)
