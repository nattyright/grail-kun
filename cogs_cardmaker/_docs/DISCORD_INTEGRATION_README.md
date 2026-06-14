# Cardmaker Discord Integration

This document describes the Discord bot integration for `cogs_cardmaker/`.
The original standalone renderer documentation remains in `README.md`.

## Overview

The integration lets Grail-kun render character cards from MongoDB records and publish them into Discord forum channels as gallery-style card threads.

Key behavior:

- Full characters and minor characters use separate configured forum channels.
- Each posted card is represented by one forum thread.
- The rendered card image is attached to the starter message for gallery thumbnail use.
- The starter message body stores structured Markdown character details.
- The bot sends a second resource post immediately after the starter message with the Google Docs sheet URL and the faceclaim as an embed thumbnail.
- Existing cards are edited from inside their own thread.
- MongoDB remains the character data source of truth.
- Discord forum tags are used for lightweight public filtering and status sync.

## Main Files

- `cogs/cog_cardmaker.py`: Discord cog and `f.card` command group.
- `cogs_cardmaker/card.py`: Pillow renderer, now path-safe from the bot root.
- `cogs_cardmaker/service.py`: Rendering helpers, title/body generation, template parsing, faceclaim handling.
- `cogs_cardmaker/repo.py`: Async-safe MongoDB access and audit logging.
- `cogs_cardmaker/import_mongo.py`: Import/migration tool updated for new fields.
- `cogs_cardmaker/DISCORD_INTEGRATION_PLAN.md`: Design notes and resolved decisions.

## Requirements

`requirements.txt` now pins:

```text
discord.py==2.7.1
```

The integration also relies on existing project dependencies:

- `pillow`
- `pymongo`
- `python-dotenv`

## MongoDB Collections

Character records live in:

```text
grail-kun.cardmaker_characters
```

Audit/log records live in:

```text
grail-kun.cardmaker_audit
```

Deleted card records are archived in:

```text
grail-kun.cardmaker_deleted
```

Guild-level cardmaker config is stored in the existing:

```text
grail-kun.guild_config
```

Relevant config keys:

- `cardmaker_full_forum_channel_id`
- `cardmaker_minor_forum_channel_id`
- `cardmaker_default_design`

## Character Schema Notes

Important cardmaker fields:

```json
{
  "_id": "{source_doc_id}:{safe_name}",
  "source_doc_id": "google_doc_id",
  "name": "Captain Ahab",
  "role": "Servant",
  "scope": "full",
  "type": "PC",
  "username": "@magnetm",
  "userid": "291225855823446016",
  "avatar_path": "captain_ahab.png",
  "footer_text": "Rest of the World | Event Details",
  "source_url": "https://docs.google.com/document/d/.../edit",
  "class": "Lancer",
  "nationality": "American",
  "affiliation": null,
  "occupation": null,
  "alignment": "Chaotic Good",
  "safe_name": "captain_ahab"
}
```

`scope` determines which forum channel receives the card:

- `full`
- `minor`

`type` remains independent:

- `PC`
- `NPC`

Both full and minor characters may be either PCs or NPCs.

The `discord` block tracks publishing state:

```json
{
  "discord": {
    "starter_body": null,
    "posts": [
      {
        "guild_id": "server_id",
        "forum_channel_id": "forum_channel_id",
        "thread_id": "thread_id",
        "starter_message_id": "starter_message_id",
        "resource_message_id": "resource_message_id",
        "card_message_id": "starter_message_id",
        "post_status": "posted",
        "last_posted_at": "2026-06-14T00:00:00Z",
        "last_synced_at": "2026-06-14T00:00:00Z",
        "last_error": null
      }
    ]
  }
}
```

`discord.posts` is the only source of truth for posted thread locations.
Legacy top-level post fields such as `discord.guild_id`, `discord.thread_id`, and `discord.post_status` are intentionally not used.

Existing documents are backfilled at read time with:

- `scope: "full"`
- `discord.starter_body` generated from the character record if missing
- `discord.posts: []` if missing

## Thread Titles

Thread title format:

```text
{Master OR Servant} | {character_name} | @{canonical_username} | {footer_text}
```

Examples:

```text
Servant | Captain Ahab | @magnetm | Rest of the World | Event Details
Master | Nannerl von Eltz | @inkown | Narssarsuk
```

Rules:

- Masters use `Master`.
- Servants use `Servant`. Servant class is already visible on the card.
- `username` should be canonical plain text with an `@`.
- `footer_text` is shown in full.

## Starter Message Body

Starter bodies are structured Markdown and stored in `discord.starter_body`.

Example:

```md
**Name:** Captain Ahab
**Role:** Servant
**Type:** PC
**Player:** <@291225855823446016>
**Class:** Lancer
**Nationality:** American
**Alignment:** Chaotic Good
**Debut:** Rest of the World | Event Details
```

Servants include:

- `class`
- `nationality`

Masters include:

- `affiliation`
- `occupation`

All characters include:

- `name`
- `role`
- `type`
- `Player` mention from `userid`
- `alignment`
- `footer_text` as `Debut`

Links are stripped/suppressed to avoid embeds.

## Resource Post

After the starter message, the bot posts a second message in the same thread with a compact embed:

- `Character Sheet` links to the character's `source_url`.
- The current faceclaim is attached to that message and used as the embed thumbnail.
- No Discord components are attached.

On card updates, design changes, starter body edits, and faceclaim uploads, the bot refreshes this resource message. If an older posted card does not have a stored `resource_message_id`, the next update sends the missing resource message and stores the new message ID in `discord.posts`.

## Forum Tags

The initial tag set is intentionally limited to 8 tags:

Status:

- `Active`
- `Hiatus`
- `Retired`

Type:

- `PC`
- `NPC`

Player status:

- `Looking for RP`
- `Looking for Master`
- `Looking for Servant`

Status tags sync into MongoDB `admin.status`.
The `PC` and `NPC` tags sync into MongoDB `type`.

`Looking for RP`, `Looking for Master`, and `Looking for Servant` imply active status and sync `admin.status` to `active`.
`Active`, `Hiatus`, and `Retired` are mutually exclusive. When one is newly added, it becomes the status to keep and the other two are dropped.
Because `Looking for...` implies active, a newly-added `Looking for...` tag also drops `Hiatus`, `Retired`, and `Active`.
`Active` and any `Looking for...` tag are mutually exclusive.
`Looking for Master` and `Looking for Servant` are mutually exclusive.
`Looking for RP` can coexist with either `Looking for Master` or `Looking for Servant`.
If a thread is tagged `Hiatus` or `Retired`, the bot drops `Active` and all `Looking for...` tags during sync.
`PC` and `NPC` are mutually exclusive.
Native PC/NPC tag changes sync into MongoDB `type`.
Admins can also sync the current PC/NPC tag into MongoDB with the admin-only `Sync Tags` panel button.

Status sync happens:

- during card update flows
- when thread tags are manually changed

## Commands

All commands are under:

```text
f.card
```

### `f.card fullchannel #forum-channel`

Admin-only.
Sets the full-character forum channel.
The channel must be a Discord forum channel.

### `f.card minorchannel #forum-channel`

Admin-only.
Sets the minor-character forum channel.
The channel must be a Discord forum channel.

### `f.card setdefaultdesign <design>`

Admin-only.
Sets the guild default card design used when creating new characters without `--design`.

### `f.card create`

Admin-only.
With no fields, prints copy/paste create templates. With filled `--field:` lines, creates a MongoDB record from the templated command message, then posts it.

Master and non-Servant template:

```text
f.card create
--doc: google_doc_URL
--name: character_name
--role: Master OR Servant OR Other (Human,DOG,etc.)
--scope: full OR minor
--type: PC OR NPC
--player: @mention
--affiliation: affiliation
--occupation: occupation
--alignment: alignment
--footer: origin_event_name | origin_event_details
--design: default-rotw OR other_design_name
```

Servant template:

```text
f.card create
--doc: google_doc_URL
--name: character_name
--role: Master OR Servant OR Other (Human,DOG,etc.)
--scope: full OR minor
--type: PC OR NPC
--player: @mention
--class: class
--nationality: nationality
--alignment: alignment
--footer: origin_event_name | origin_event_details
--design: default-rotw OR other_design_name
```

Notes:

- `--player` must be a Discord mention.
- The bot derives `userid` and canonical `username` from the mention.
- `--scope` should be `full` or `minor`.
- `--type` should be `PC` or `NPC`.
- Attach a faceclaim image to the same `f.card create` message to set the initial faceclaim.
- Do not use faceclaim filenames in create templates. `--faceclaim` and `--avatar_path` are rejected.
- Servant-first roles use `--class` and `--nationality`.
- Master-first, Master, and non-Servant roles use `--affiliation` and `--occupation`.
- `--design` is optional if a guild default is set.

### `f.card post <doc_id_or_url_or_character_id> [...]`

Admin-only.
Posts one or more existing MongoDB characters.

Accepted references:

- exact character `_id`
- Google Doc ID
- Google Doc URL
- `safe_name`, if unambiguous

If multiple characters match a Google Doc ID, the bot asks for the exact character ID.

If the character is already posted, the bot does not create a replacement thread.
It links the existing thread instead.
Before blocking a post, the bot verifies that the stored thread still exists in Discord. If Discord returns `NotFound`, the stale `discord.posts` entry is removed, an audit event is written, and the card is posted again so each character still has at most one live thread per server.

### `f.card postall`

Admin-only.
Posts all eligible active, unposted characters.
Already-posted characters are skipped.

### `f.card edit`

Thread-only.
Opens card controls for the current card thread.

Owners can use it for their own cards.
Admins can use it for any card.

The same controls are also available as the `/card edit` app command.
`f.card panel` remains as a backwards-compatible alias.

Panel actions:

- Edit Card
- Edit Starter Post
- Edit Design
- Edit Faceclaim
- Sync Tags
- Admin Fields
- Delete Card

`Sync Tags` manually reapplies the forum tag rules and updates MongoDB `admin.status` and `type` from the current thread tags. It is mostly a recovery/repair button, because normal status and PC/NPC tag edits are also synced automatically.
`Sync Tags`, `Admin Fields`, and `Delete Card` are admin-only.

## Editing Rules

Existing-card edits are modal-driven from `f.card edit` or `/card edit`.

Owners may edit all normal card fields except:

- `username`
- `footer_text`
- `scope`
- `type`
- `userid`
- `safe_name`

Admins may edit admin-controlled display/data fields.

Admin fields currently include:

- canonical username
- footer text

Google Docs URL is intentionally not editable. It determines `source_doc_id` and the character `_id`; a new Google Docs submission should be created as a new character record instead of mutating an existing record's identity.

`source_url`, `source_doc_id`, `scope`, `userid`, `safe_name`, and faceclaim filenames are treated as internal/automatic fields and are not directly edited in modals.

There is no preview command. Updates are applied and rerendered immediately.
There is no separate rerender panel button because edits, design changes, faceclaim uploads, and starter-post updates already rerender immediately.

If a character changes scope between full and minor, treat that as a new public listing: retire the previous thread/card and create or post the character in the correct scope channel with the appropriate Google Doc URL.

`Delete Card` moves the MongoDB record to `cardmaker_deleted` and deletes the Discord thread after an explicit admin confirmation. If Discord thread deletion fails, the MongoDB delete is rolled back by restoring the record to `cardmaker_characters` and removing the archived copy.
Deletion metadata is stored under the archived document's `deletion` object:

```json
{
  "deletion": {
    "original_id": "{source_doc_id}:{safe_name}",
    "at": "2026-06-14T00:00:00Z",
    "by": "discord_user_id"
  }
}
```

## Faceclaim Uploads

Faceclaim upload currently uses a reliable fallback flow:

1. Run `f.card edit` or `/card edit` inside a card thread.
2. Click `Edit Faceclaim`.
3. Send the next message in that thread with an image attachment.
4. The bot validates, saves, updates MongoDB, rerenders, and deletes the upload message.

The upload flow does not send a success message. The updated card is the confirmation.

Allowed image types:

- PNG
- JPG/JPEG
- WEBP
- GIF

Size rules:

- Target max size is 1 MB.
- JPEG/WEBP can be compressed by quality reduction and resizing.
- PNG is never converted to JPEG/WEBP just to meet the size limit.
- Large PNGs are optimized/resized while preserving PNG format.
- If a PNG remains over 1 MB, the upload is rejected.

Filename format:

```text
{safe_name}_{source_doc_id}.{ext}
```

This keeps files browsable by character name while preserving collision safety.

## Audit Logging

Audit events are written to `cardmaker_audit` for important actions, including:

- card created
- card posted
- card updated
- card body edited
- card design changed
- faceclaim replaced
- status synced from tags
- already-posted card encountered
- render/post/update/upload errors

## Import/Migration Notes

`import_mongo.py` now includes:

- `scope`
- `discord.starter_body`

If imported data omits `scope`, it defaults to:

```text
full
```

When reordering or rewriting documents, keep `scope` directly after `role`.

## Verification Performed

Local checks performed during implementation:

```powershell
python -m py_compile cogs\cog_cardmaker.py cogs_cardmaker\card.py cogs_cardmaker\repo.py cogs_cardmaker\service.py cogs_cardmaker\import_mongo.py
```

Import smoke test:

```powershell
python -c "import discord; import cogs.cog_cardmaker as c; import cogs_cardmaker.service as s; print(discord.__version__); print(c.CardmakerCog.__name__); print(s.thread_title({'name':'Captain Ahab','role':'Servant','class':'Lancer','username':'@magnetm','footer_text':'Rest of the World | Event'}))"
```

Renderer smoke test:

```powershell
python -c "from cogs_cardmaker.card import CardGenerator; g=CardGenerator('default-rotw'); img=g.render(dict(g.layout_cfg['character'])); print(img.size)"
```

Expected render size:

```text
(1800, 1118)
```

## Live Discord Testing

Verified in live Discord testing:

- Starter message attachment replacement during rerender works.
- Starter message image/link removal works.
- Faceclaim upload fallback flow works.
- Status tag sync for `Active`, `Hiatus`, and `Retired` works.

Still unresolved:

- PC/NPC tag sync should be retested after the latest `type` sync fix.

## Operational Notes

- The cog is auto-loaded because it is named `cogs/cog_cardmaker.py`.
- MongoDB operations are wrapped with `asyncio.to_thread`.
- Rendering and faceclaim image work are also pushed off the event loop.
- The bot needs permissions to create forum threads, attach files, manage/edit its own messages, apply tags, and delete card threads.
- The rendered card image remains visible as an inline attachment in the starter post and is also used by Discord forum/gallery views.
