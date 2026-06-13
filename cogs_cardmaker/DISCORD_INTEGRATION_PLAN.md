# Discord Cardmaker Integration Plan

Working design notes for integrating `cogs_cardmaker/` into Grail-kun.

## Goals

- Let admins create character cards and post them into designated Discord forum channels.
- Use each forum thread as a gallery item, with the rendered card image as the lone thread thumbnail.
- Render cards from existing MongoDB character documents.
- Support single, multiple, and all-character batch posting.
- Create a MongoDB character record when an admin creates a card for a Google Doc ID that is not already present.
- Let admins and card owners update existing posted cards from inside the card's forum thread only.
- Keep card-status management tied to Discord forum tags rather than separate bot commands.

## Current Repo Shape

- `bot.py` loads all files matching `cogs/cog*.py`.
- The bot command prefix is `f.`.
- MongoDB handles are exposed as:
  - `bot.db` for the `grail-kun` database.
  - `bot.db_fan_servants` for the `fan-servants` database.
- `cogs_cardmaker/card.py` contains the reusable renderer:
  - `CardGenerator(layout).render(data)` returns a Pillow image.
- `cogs_cardmaker/import_mongo.py` imports character records into `grail-kun.cardmaker_characters`.

## Important Technical Notes

- `cogs_cardmaker/` is not currently a bot cog.
- `cogs_cardmaker/` does not currently have an `__init__.py`.
- `card.py` currently assumes the working directory is `cogs_cardmaker/`, because default paths are relative:
  - `designs`
  - `fonts`
  - `faceclaims`
  - `outputs`
- For Discord integration, rendering should happen in memory with `BytesIO`, not by writing to `outputs/`.
- PyMongo is synchronous, so bot commands should wrap database work in `asyncio.to_thread`, following the `cogs_sheetwatch` pattern.

## Discord UI Limits

Current Discord modal/component limits to design around:

- Modal title: max 45 characters.
- Modal custom ID: 1-100 characters.
- Modal components: 1-5 components.
- Text input custom ID: 1-100 characters.
- Text input label: max 45 characters.
- Text input min/max length values: 0-4000 characters.
- Text input placeholder: max 100 characters.
- Text input prefilled value: max 4000 characters.
- Select menu options: max 25 options.
- Button label: max 80 characters, though shorter labels are recommended.
- File upload components are available in modals, so faceclaim upload can be part of the panel/modal flow if supported by `discord.py`.
- Verify `discord.py 2.6.4` support before implementation for Components V2 and modal file upload components.
- If modal file uploads are not supported by the installed `discord.py` version, fall back to asking the user/admin to send a normal message attachment in the card thread after clicking an upload button.
- These limits are acceptable. If a user's text exceeds Discord modal limits, the bot should reject it with a clear message rather than trying to work around the limit.

## MongoDB Character Document

The existing cardmaker schema is a good base:

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
  "safe_name": "captain_ahab",
  "card": {
    "default_design": "card2",
    "last_rendered_at": null
  },
  "discord": {
    "guild_id": null,
    "forum_channel_id": null,
    "thread_id": null,
    "starter_message_id": null,
    "starter_body": null,
    "card_message_id": null,
    "post_status": "not_posted",
    "last_posted_at": null,
    "last_synced_at": null,
    "last_error": null
  },
  "admin": {
    "status": "active",
    "created_by": "291225855823446016",
    "created_at": "2026-06-13T00:00:00Z",
    "updated_by": "291225855823446016",
    "updated_at": "2026-06-13T00:00:00Z"
  }
}
```

The `discord` block should become the link between MongoDB and the posted forum thread.

`scope` should distinguish full characters from minor characters:

- `full`
- `minor`

`type` should continue to distinguish:

- `PC`
- `NPC`

Both full and minor characters can be either PCs or NPCs.

Existing MongoDB documents should be backfilled with:

- `scope: "full"`
- `discord.starter_body`: generated from the standard starter body template unless a custom body already exists

When rewriting or importing documents, keep `scope` ordered directly after `role`.

## Forum Channel Model

- Admins configure designated card forum channels per guild.
- Full characters and minor characters should use separate forum channels because minor characters do not operate at the same capacity as full characters.
- Minor characters can also be NPCs, so "minor character" should not be treated as a mutually exclusive replacement for PC/NPC tagging.
- Use `scope == "full"` for the full-character forum and `scope == "minor"` for the minor-character forum.
- Configured channels must be Discord forum channels.
- Posting a card creates a forum thread.
- The rendered card image should be attached to the thread starter message so Discord gallery view uses it as the thumbnail.
- The card image should be the only attachment/image in the starter message.
- The starter message may also contain user-editable plain Markdown text for character details.
- Starter message text should strip or suppress links to avoid embeds and keep the gallery clean.
- The thread is the canonical public "card page" for that character.

## Thread Titles

Thread titles should carry useful browsing context that does not need a scarce forum tag.

Suggested title format:

```text
{Role Label} | {Character Name} | @{canonical_username} | {Debut Label}
```

Examples:

```text
Lancer | Captain Ahab | @magnetm | ROTW
Master | Nannerl von Eltz | @inkown | Narssarsuk
```

Thread title rules:

- If the character is a Master, use `Master` as the role label.
- If the character is a Servant, use their servant class as the role label.
- Use the canonical username from MongoDB, which should be plain text with an `@` symbol.
- The debut label comes from the first part of `footer_text` before the `|` symbol.
- If the debut label is `Rest of the World`, use `ROTW`.

## Forum Tags

Discord forum channels currently have a low tag limit, so forum tags should be reserved for the most useful gallery filters. Seasons, events, servant classes, and detailed taxonomy should not all become tags.

Expected status tags:

- `Active`
- `Hiatus`
- `Retired`

Expected role tags:

- `Master`
- `Servant`

Expected type tags:

- `PC`
- `NPC`

Expected player-status tags:

- `Looking for RP`
- `Looking for Master`
- `Looking for Servant`

This initial tag set is final for now: 10 tags total.

Status does not need special bot commands. The bot should read the applied forum thread tag when it needs to know the current status.

When a status tag changes, MongoDB should be synced:

- Only the three status tags count as status: `Active`, `Hiatus`, `Retired`.
- Other tags should not affect `admin.status`.
- `admin.status` should be updated to the matching status value.
- The status sync should update the relevant timestamp, such as `admin.updated_at` or a dedicated status-sync timestamp.
- Status sync events should be logged in MongoDB.

Information that should usually live in the thread title, starter message body, or MongoDB rather than tags:

- debut season
- debut event
- servant class
- nationality
- alignment
- affiliation
- occupation

Footer event data:

- `footer_text` stores debut information in this format:

```text
EVENT NAME | EVENT DETAILS
```

- The bot should derive the debut/event display value from the `EVENT NAME` portion:

```python
event_name = footer_text.split("|", 1)[0].strip()
```

- This value can be included in the thread title and starter message body.

## Admin Commands

Proposed command group:

```text
f.card
```

Possible commands:

```text
f.card channel #forum-channel
f.card minorchannel #forum-channel
f.card post <doc_id_or_url_or_character_id>
f.card postmany <doc_id_or_url_or_character_id> ...
f.card postall
f.card create <doc_url> ...
f.card panel
f.card setdesign <design>
f.card setdefaultdesign <design>
f.card template
```

### `f.card channel #forum-channel`

- Admin-only.
- Stores the full-character card forum channel in guild config.
- Rejects any channel that is not a forum channel.

### `f.card minorchannel #forum-channel`

- Admin-only.
- Stores the minor-character card forum channel in guild config.
- Rejects any channel that is not a forum channel.

### `f.card post <doc_id_or_url_or_character_id>`

- Admin-only.
- Looks up an existing character in MongoDB.
- Accepts a Google Doc URL, Google Doc ID, or exact character ID.
- Renders the selected character.
- Creates a forum thread in the configured forum channel.
  - Full characters go to the full-character forum.
  - Minor characters go to the minor-character forum.
- Stores `guild_id`, `forum_channel_id`, `thread_id`, and message IDs in the character document.
- Applies status, role, type, and player-status tags if possible.
- Uses the thread title and starter body for class/debut/event details.
- If the character is already posted, do not create another thread. Reply with an alert message that links the existing thread so the admin can go there and update it.

### `f.card postmany <...>`

- Admin-only.
- Posts multiple selected characters.
- Should report per-character success/failure.

### `f.card postall`

- Admin-only.
- Batch posts all eligible characters.
- Should likely include a dry-run or confirmation step before creating many threads.
- Eligibility could mean:
  - `admin.status == "active"`
  - `discord.post_status != "posted"`
- Already-posted characters should be skipped by default.

### `f.card template`

- Admin-facing helper.
- Sends a copy/paste template for `f.card create`.

### `f.card create`

- Admin-only.
- Used when the Google Doc ID does not exist in MongoDB.
- Accepts a templated Discord message body rather than a long one-line command.
- Creates a new MongoDB character document.
- Then renders and posts it.
- The command message should look like:

```text
f.card create
--doc: https://docs.google.com/document/d/.../edit
--name: Captain Ahab
--role: Servant
--scope: full
--type: PC
--player: @magnetm
--faceclaim: captain_ahab.png
--class: Lancer
--nationality: American
--alignment: Chaotic Good
--footer: Rest of the World | Event Details
--design: card2
```

- The bot parses the template fields, derives `username` and `userid` from the Discord mention in `--player`, saves the record, renders the card, and posts it.

### `f.card panel`

- Must be run inside a card thread.
- Opens or sends a thread-local control panel with buttons.
- Useful buttons:
  - Edit Info
  - Edit Body
  - Change Design
  - Rerender
  - Sync Tags
- Admins see all relevant controls.
- Owners see only allowed controls.

### `f.card setdesign <design>`

- Must be run inside a card thread.
- Updates that character's design.
- Rerenders immediately.

## User Commands

Users should have a narrow, clean command surface.

Possible commands:

```text
f.card panel
```

### User `f.card panel`

- Must be run inside an existing card forum thread.
- Finds the character by `discord.thread_id == ctx.channel.id`.
- Checks that:

```python
str(ctx.author.id) == str(character["userid"])
```

- Admins bypass the ownership check.
- If authorized, opens the thread-local control panel.
- Deletes the command message afterward.

### User Editing

- Existing-card edits should happen through modals launched from the thread-local panel.
- Owners may edit all card fields except:
  - `username`
  - `footer_text`
- Admins may edit all fields.
- Users and admins may upload a new faceclaim image through the edit flow.
- A newly uploaded faceclaim replaces the old faceclaim for that character.
- Saving a modal immediately updates MongoDB, rerenders the card, updates the starter message/card image, and syncs tags/title/body.
- There is no preview command. Cards are simple enough to update on the fly and check after each update.

## Starter Message Body

The starter message should contain the rendered card thumbnail attachment plus structured Markdown text.

Desired behavior:

- The rendered card is used as the forum gallery thumbnail.
- The rendered card should appear only as the forum gallery thumbnail, not as a large visible inline attachment in the starter message.
- This should be implemented with Discord message/component behavior equivalent to Discohook's ability to hide attachments from the message body while still using them for display/thumbnail purposes.
- The card should remain the only image/attachment associated with the starter message.
- Starter message text should contain no links.
- Links should be stripped or suppressed to avoid embeds.

Starter message fields:

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

For Servants, include:

- `class`
- `nationality`

For Masters, include:

- `affiliation`
- `occupation`

For all characters, include:

- `name`
- `role`
- `type`
- `Player`, displayed as a Discord mention derived from `userid`
- `alignment`
- `footer_text`, labeled as `Debut`

The starter message body may be edited by the owner/admin as pure Markdown text, while preserving the no-links/no-extra-images rule.

The current starter message text should be stored in MongoDB at `discord.starter_body`, so rerenders and sync operations do not accidentally overwrite user-edited text.

## Faceclaim Uploads

Users and admins should be able to upload replacement faceclaim images through the card edit flow.

Upload rules:

- Accept only standard image attachments: PNG, JPEG/JPG, WEBP, and GIF.
- Validate the image before saving.
- If the uploaded image exceeds 1 MB, compress it down to 1 MB or less before saving.
- Pillow can do this by resizing and/or iteratively lowering quality for JPEG/WEBP output.
- Do not convert PNG uploads to JPEG or WEBP just to meet the size limit. If a user uploads a PNG, assume they intend to preserve transparency.
- For large PNG uploads, preserve PNG format and try safe PNG optimization/resizing. If the image still cannot fit under 1 MB without format conversion, reject it with a clear message.
- Save the replacement under `cogs_cardmaker/faceclaims/`.
- Replace the previous faceclaim for that character by updating `avatar_path`.
- Avoid using `safe_name` alone as the filename, because different source documents can contain duplicate character names.

Recommended filename format:

```text
{safe_name}_{source_doc_id}.{ext}
```

This puts the readable character name first for alphabetical browsing, while keeping the full Google Doc ID for straightforward searching and collision avoidance.

If extra collision safety is wanted later, use:

```text
{short_hash_of_character_id}_{safe_name}.{ext}
```

## Audit Logging

Write MongoDB audit/log events for important cardmaker actions:

- card posted
- card updated
- card body edited
- card design changed
- faceclaim replaced
- status synced from forum tags
- batch post skipped an already-posted character
- post command found an already-posted character and linked the existing thread
- errors during render, post, update, upload, or sync

## Creation From Scratch Options

When a Google Doc ID is not in MongoDB, the bot needs character fields from somewhere.

### Option A: Templated Command Message

Example:

```text
f.card create
--doc: https://docs.google.com/document/d/.../edit
--name: Captain Ahab
--role: Servant
--scope: full
--type: PC
--player: @magnetm
--faceclaim: captain_ahab.png
--class: Lancer
--nationality: American
--alignment: Chaotic Good
--footer: Rest of the World | Event Details
--design: card2
```

Pros:

- Simpler implementation.
- Easy to copy, paste, log, and repeat.
- Easier to use in Discord than a long one-line command.
- Admins provide a Discord mention with `--player`, and the bot derives both `userid` and canonical `username`.

Cons:

- Still requires admins to fill fields correctly.

### Option B: Discord Modal

Admin runs:

```text
f.card create <doc_url>
```

The bot opens a modal for fields such as name, role, username, alignment, and footer text.

Pros:

- Better Discord UX.
- Less command clutter.

Cons:

- More implementation work.
- Modals have field/count limits, so multi-step input may be needed.

### Option C: Google Doc Parsing

The bot fetches/parses character data from the source document.

Pros:

- Least manual work if document format is consistent.

Cons:

- More fragile.
- Best saved for a later phase unless the sheet format is very reliable.

## Suggested Implementation Phases

### Phase 1: Path-Safe Renderer

- Make `cogs_cardmaker` importable.
- Make renderer asset paths resolve relative to `cogs_cardmaker/`, not the process working directory.
- Add an in-memory render helper returning `BytesIO`.

### Phase 2: Repository Layer

- Add async-safe cardmaker MongoDB access.
- Find character by:
  - character `_id`
  - Google Doc ID
  - Google Doc URL
  - Discord thread ID
- Update Discord publishing metadata.
- Update card design.

### Phase 3: Single Post And Update

- Add `cogs/cog_cardmaker.py`.
- Implement:
  - `f.card channel`
  - `f.card minorchannel`
  - `f.card post`
  - `f.card panel`
  - `f.card setdesign`
- Ensure forum channel validation.
- Ensure thread-only update behavior.
- Ensure owner/admin permission checks.

### Phase 4: Title, Body, And Tag Sync

- Map forum tags to status.
- Sync only `Active`, `Hiatus`, and `Retired` into `admin.status`.
- Apply role, type, and player-status tags.
- Include servant class and debut/event details in thread title/body instead of tags.
- Strip or suppress links in starter message text.

### Phase 5: Batch Posting

- Implement:
  - `f.card postmany`
  - `f.card postall`
- Include result reporting.
- Consider dry-run/confirmation.

### Phase 6: Create From Scratch

- Choose command args, modal, or parser.
- Create missing MongoDB records from admin-provided data.
- Render and post immediately.

## Resolved Design Decisions

1. Thread title format:

```text
{Master OR Servant Class} | {character_name} | @{canonical_username} | {debut_label}
```

If the debut label is `Rest of the World`, display it as `ROTW`.

2. Owners can edit all fields except `username` and `footer_text`. Admins can edit all fields.

3. `f.card setdesign <design>` rerenders immediately.

4. There is no preview command. Users can update on the fly and inspect the updated card afterward.

5. Status tags should sync into MongoDB. Only `Active`, `Hiatus`, and `Retired` count as status tags. Sync the matching value into `admin.status` and update the timestamp.

Status sync should happen in both places:

- during card update flows
- from an event listener when thread tags are changed manually

6. Batch posting should skip already-posted characters.

7. Reposting an already-posted character should not create or replace a thread. The bot should alert the admin and link the existing thread.

8. Starter message body includes only the structured fields listed above, with `footer_text` labeled as `Debut`.

9. Existing-card edits should use focused modals instead of one giant edit form.

Discord modals can only show a small number of text inputs at once, so editing should use several focused modals.

Modal grouping:

```text
Edit Identity
- name
- role
- scope
- type
- userid
```

```text
Edit Servant Details
- class
- nationality
- alignment
- faceclaim
```

```text
Edit Master Details
- affiliation
- occupation
- alignment
- faceclaim
```

```text
Edit Display Text
- starter message body
```

```text
Admin Fields
- username
- footer_text
- source_url
- safe_name
- design
```

Owners should not see or be able to submit restricted admin-only fields such as `username` and `footer_text`.

10. Add a `scope` field directly below `role` in MongoDB document ordering. Use `full` and `minor`. Both scopes can be either `PC` or `NPC`.

11. Store canonical username as plain text with an `@` symbol in `username`. Use `userid` for Discord mentions in the starter message body.

12. Store user/admin-edited starter text in `discord.starter_body`.

13. Users and admins can upload replacement faceclaim images. Replacement uploads update `avatar_path` and replace the old faceclaim for that character. Use `{safe_name}_{source_doc_id}.{ext}` instead of `safe_name` alone to avoid duplicate-name collisions while keeping files easy to browse alphabetically.

14. Status sync should update MongoDB with a timestamp and write a MongoDB log/audit event.

15. `f.card create` should use `--player: @mention`. The bot derives both `userid` and canonical `username`, so the template does not need a separate `--userid` field.

## Remaining Questions

No major design questions remain right now.
