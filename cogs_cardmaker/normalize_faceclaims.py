from __future__ import annotations

import argparse
import os
import shutil
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from pymongo import MongoClient

from cogs_cardmaker.card import Defaults


DEFAULT_DATABASE = "grail-kun"
CHARACTER_COLLECTION = "cardmaker_characters"
AUDIT_COLLECTION = "cardmaker_audit"


def standard_name(doc: dict[str, Any], old_name: str) -> str:
    ext = Path(old_name).suffix.lower()
    safe_name = doc.get("safe_name") or "character"
    source_doc_id = doc.get("source_doc_id") or "unknown_doc"
    return f"{safe_name}_{source_doc_id}{ext}"


def normalize(args: argparse.Namespace) -> int:
    load_dotenv()
    mongo_uri = args.mongo_uri or os.getenv("MONGODB_URI")
    if not mongo_uri:
        raise RuntimeError("Provide --mongo-uri or set MONGODB_URI.")

    client = MongoClient(mongo_uri)
    db = client[args.database]
    characters = db[CHARACTER_COLLECTION]
    audit = db[AUDIT_COLLECTION]

    docs = list(characters.find({"avatar_path": {"$nin": [None, ""]}}).sort("name", 1))
    by_old_path: dict[str, list[tuple[dict[str, Any], str]]] = defaultdict(list)
    for doc in docs:
        old_name = Path(str(doc.get("avatar_path"))).name
        new_name = standard_name(doc, old_name)
        if old_name == new_name:
            continue
        by_old_path[old_name].append((doc, new_name))

    planned_updates: list[tuple[str, str, str]] = []
    missing: list[str] = []
    for old_name, entries in by_old_path.items():
        old_path = Defaults.FACECLAIMS_DIR / old_name
        targets = sorted({new_name for _, new_name in entries})
        target_exists = any((Defaults.FACECLAIMS_DIR / target).exists() for target in targets)
        if not old_path.exists() and not target_exists:
            missing.append(old_name)
            continue
        for doc, new_name in entries:
            planned_updates.append((doc["_id"], old_name, new_name))

    print(f"Characters with faceclaims: {len(docs)}")
    print(f"Old filenames needing normalization: {len(by_old_path)}")
    print(f"Mongo avatar_path updates planned: {len(planned_updates)}")
    if missing:
        print(f"Missing source files skipped: {len(missing)}")
        for name in missing[:20]:
            print(f"  missing: {name}")

    if args.dry_run:
        for character_id, old_name, new_name in planned_updates[:20]:
            print(f"  {character_id}: {old_name} -> {new_name}")
        if len(planned_updates) > 20:
            print(f"  ... {len(planned_updates) - 20} more")
        return 0

    for old_name, entries in by_old_path.items():
        old_path = Defaults.FACECLAIMS_DIR / old_name
        targets = sorted({new_name for _, new_name in entries})
        if not old_path.exists() and not any((Defaults.FACECLAIMS_DIR / target).exists() for target in targets):
            continue
        for target in targets:
            target_path = Defaults.FACECLAIMS_DIR / target
            if not target_path.exists():
                shutil.copy2(old_path, target_path)
        if old_path.exists() and old_name not in targets:
            old_path.unlink()

    changed = 0
    now = datetime.now(timezone.utc)
    for character_id, old_name, new_name in planned_updates:
        result = characters.update_one(
            {"_id": character_id, "avatar_path": old_name},
            {"$set": {"avatar_path": new_name, "admin.updated_at": now}},
        )
        changed += result.modified_count

    audit.insert_one({
        "character_id": None,
        "actor_id": "system",
        "kind": "faceclaim_filename_normalized",
        "details": {
            "planned_updates": len(planned_updates),
            "changed": changed,
            "missing": missing,
            "format": "{safe_name}_{source_doc_id}.{ext}",
        },
        "created_at": now,
    })
    print(f"Normalized {changed} Mongo avatar_path value(s).")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Normalize cardmaker faceclaim filenames.")
    parser.add_argument("--mongo-uri", help="MongoDB connection string. Defaults to MONGODB_URI.")
    parser.add_argument("--database", default=DEFAULT_DATABASE, help="MongoDB database name.")
    parser.add_argument("--dry-run", action="store_true", help="Show planned file/Mongo changes without writing.")
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(normalize(parse_args()))
