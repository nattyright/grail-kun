# Character Card Handbook

This handbook explains how to use the character card bot and the card maker site.
It is written for players and admins who need a quick reference during normal server use.

## What This Is For

The card system keeps the character compendium consistent and easy to browse.

Each posted character gets a Discord forum thread with:

- a rendered character card image
- a short starter post with key character details
- a second post with the character sheet link and faceclaim thumbnail
- forum tags for status, type, and RP availability

The bot stores card data separately from the forum post, so edits can rerender the card and keep the thread up to date.

## For Players

### Opening Your Card Controls

Go to your character's card thread and run either:

```text
f.card edit
```

or use the Discord app command:

```text
/card edit
```

This opens card controls. Only you and admins can edit your card.

### What You Can Edit Yourself

Players can edit normal card display fields, such as:

- character name
- role
- class and nationality for Servants
- affiliation and occupation for Masters or non-Servants
- alignment
- starter post text
- card design
- faceclaim
- custom background, if the selected card design supports it

Changes apply immediately. The card rerenders after edits, so the updated image is the confirmation.

### Editing Your Faceclaim

1. Open your card controls with `f.card edit` or `/card edit`.
2. Click `Edit Faceclaim`.
3. Send your new faceclaim image as your next message in that same thread.
4. The bot saves it, rerenders the card, updates the sheet/faceclaim embed, and deletes the upload message.

Allowed image types:

- PNG
- JPG/JPEG
- WEBP
- GIF

Images should be 1 MB or smaller. Large JPG/WEBP images may be compressed automatically. Large PNGs are optimized without changing them into JPG/WEBP.

### Editing The Starter Post

Use `Edit Starter Post` if the visible thread text needs cleanup.

The starter post should stay focused on the character summary. Links are stripped so Discord does not create extra embeds there. The Google Docs sheet link belongs in the second resource post, which the bot manages automatically.

### Using Forum Tags

You may see tags such as:

- `Active`
- `Hiatus`
- `Retired`
- `PC`
- `NPC`
- `Looking for RP`
- `Looking for Master`
- `Looking for Servant`

Only the character owner, admins, and approved cardmaker roles should change these tags.

When the owner, an admin, or someone with an approved cardmaker role changes status and PC/NPC tags, the bot updates the stored card data. If someone else changes the tags, the bot changes them back.

`Looking for RP`, `Looking for Master`, and `Looking for Servant` count as active status. If you choose `Hiatus` or `Retired`, the bot removes active-looking-for tags.

### When To Contact An Admin

Contact an admin if you need to change:

- the Google Docs sheet URL
- whether the card belongs in the full or minor character forum
- the listed player/owner
- the canonical username shown in the thread title
- the debut/footer text
- PC/NPC type if tag sync did not behave as expected
- tags that keep changing back unexpectedly
- a deleted or accidentally duplicated card
- a card that should be moved to a different forum

Google Docs URLs are intentionally not edited on existing cards. A new Google Docs sheet is treated as a new character submission.

## For Admins

### Posting A New Character

Use:

```text
f.card create
```

With no fields, the bot prints copy/paste templates.

Master or non-Servant template:

```text
f.card create
--doc: google_doc_URL
--name: character_name
--role: Master OR Servant OR Other
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
--role: Master OR Servant OR Other
--scope: full OR minor
--type: PC OR NPC
--player: @mention
--class: class
--nationality: nationality
--alignment: alignment
--footer: origin_event_name | origin_event_details
--design: default-rotw OR other_design_name
```

Attach a faceclaim image to the same `f.card create` message if you want to set the initial faceclaim.

Do not include `--faceclaim` or `--avatar_path` in create templates.

### Posting Existing Characters

Post one or more existing records with:

```text
f.card post <character_id_or_doc_url>
```

or:

```text
f.card post <ref_1> <ref_2> <ref_3>
```

Accepted references include:

- exact character ID
- Google Doc ID
- Google Docs URL
- unambiguous safe name

The bot checks whether a stored thread still exists before reposting. If the old thread was manually deleted, the stale stored reference is removed and the card can be posted again.

### Opening Admin Controls

Admins and approved cardmaker roles can use `f.card edit` or `/card edit` in any card thread.

Admins and approved cardmaker roles get the same normal edit buttons plus:

- `Sync Tags`
- `Admin Fields`
- `Delete Card`

Use `Admin Fields` for canonical username and footer/debut text.

Use `Sync Tags` if forum tags and stored card data ever get out of step.

Use `Delete Card` when a card should be removed. This archives the MongoDB record and deletes the Discord thread. If Discord thread deletion fails, the bot rolls back the database delete.

### Configuring Forums

The following commands can be used by server admins and approved cardmaker roles.

Set the full character forum:

```text
f.card fullchannel #forum-channel
```

Set the minor character forum:

```text
f.card minorchannel #forum-channel
```

Set the default design for newly created cards:

```text
f.card setdefaultdesign default-rotw
```

### Configuring Approved Cardmaker Roles

Server admins can allow trusted non-admin roles to use cardmaker staff commands:

```text
f.card setapprovedrole @RoleName
```

You can set multiple roles at once:

```text
f.card setapprovedrole @RoleOne @RoleTwo
```

To clear all approved cardmaker roles:

```text
f.card setapprovedrole
```

Approved cardmaker roles can create, post, edit, sync, and delete cards, but only server admins can change the approved role list.

### Admin Do's And Don'ts

Do:

- use `--player: @mention` so the bot stores the correct Discord user ID
- keep `--scope` to `full` or `minor`
- keep `--type` to `PC` or `NPC`
- use the correct detail fields for the role
- post each character once per server

Do not:

- edit Google Docs URLs on existing records
- reuse an existing card for a new Google Docs sheet
- manually delete threads unless you know the next `f.card post` will clean up the stale reference
- put sheet links into the starter post

## Card Maker Site Guide

The card maker site is for designing card layouts. It is not the same thing as submitting or editing a character card in Discord.

Use it when you want to create or adjust a card design package for the bot.

### What The Site Can Do

The site lets you:

- upload Master and Servant base images
- arrange image layers
- set layer opacity and visibility
- mark one layer as a custom background slot
- position the avatar area
- choose avatar shape and size
- edit text placement, font, size, color, and alignment
- drag text and avatar elements directly on the preview
- export a preview PNG
- export a full design package ZIP
- import a design package ZIP created by the tool

### Basic Site Workflow

1. Open the card maker site.
2. Use `Sample` if you want a starting point.
3. In `Assets`, choose Master or Servant and upload base images for that role.
4. Repeat for the other role.
5. Upload any fonts you want to use.
6. In `Layers`, order images from bottom to top.
7. In `Avatar`, set the faceclaim frame position, shape, width, and height.
8. In `Text`, pick each field and place it on the card.
9. Drag text or avatar elements directly on the preview for faster positioning.
10. In `Export`, set the design name and download the design package.

### Important Site Notes

Base images must match the canvas ratio. The default canvas is 8:5.

Layer order is bottom to top. If something is covering another element, move it down or reduce its opacity.

Hidden layers stay in the editor but are not exported.

The avatar preview image is only for local preview. It is not included in the design package.

If you mark a layer as the custom background slot, the Discord bot can temporarily replace that layer for a one-time custom background render.

### Exporting A Design Package

Use `Download Design Package` when the design is ready.

The exported ZIP includes:

- design config JSON
- ordered Master and Servant image layers
- uploaded fonts
- preview PNGs
- a manifest

Send the ZIP package to whoever manages bot deployment or card design installation.

### Importing A Design Package

Use `Import` to load a package previously exported by the site.

Package import restores:

- design config
- image layers
- layer order
- avatar settings
- text settings
- uploaded fonts included in the package

Loose JSON import is not supported because JSON alone cannot restore image and font files.

### When To Ask For Help With The Site

Ask an admin or designer if:

- a base image is rejected because of its ratio
- text does not fit after resizing
- a font does not load
- a design package does not import
- you are unsure which layer should be the custom background slot
- you want the design installed for live bot use

## Quick Reference

Player commands:

```text
f.card edit
/card edit
```

Admin commands:

```text
f.card create
f.card post <id_or_url>
f.card postall
f.card fullchannel #forum-channel
f.card minorchannel #forum-channel
f.card setdefaultdesign default-rotw
f.card setapprovedrole @RoleName
```

Best rule of thumb:

Players can fix the card's visible details and images. Admins and approved cardmaker roles handle identity, ownership, forum placement, deletion, and new submissions.
