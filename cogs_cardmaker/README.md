# Character Card Generator

A Python/Pillow card generator for the Starry Night character compendium. It renders high-resolution character cards from MongoDB records or command-line fields, using role-specific card art, local faceclaim images, and configurable design files.

## Features

- Batch renders characters from MongoDB.
- Supports single-card rendering from command-line fields.
- Uses self-contained designs under `designs/{design}/`.
- Lets each design place every text field independently through `config.json`.
- Supports role-specific layout templates for future card designs.
- Treats special roles such as `Human` and `Homunculus` as Master templates.
- For mixed roles, uses whichever role appears first, such as `Master / Servant` or `Servant / Master`.
- Skips the avatar layer when an avatar path is blank or unresolved, leaving the base card art visible.
- Caches fonts and card assets during a run.
- Shrinks and wraps long names to fit the configured name area.

## Directory Structure

- `card.py`: Card rendering CLI.
- `import_mongo.py`: Imports the migration file `characters/_batch_import.json` into MongoDB.
- `designs/`: Card designs, each with `config.json` and role-specific image layers.
- `faceclaims/`: Faceclaim images referenced by `avatar_path`.
- `fonts/`: TrueType/OpenType fonts.
- `outputs/`: Generated cards.

## Setup

From the workspace root:

```powershell
python -m venv .venv --upgrade
.\.venv\Scripts\python.exe -m pip install -r character-compendium\requirements.txt
```

Or, from inside `character-compendium`:

```powershell
..\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## Usage

Run commands from `character-compendium` so relative asset paths resolve correctly.

### Batch Render From MongoDB

```powershell
$env:MONGODB_URI = "mongodb+srv://..."
..\.venv\Scripts\python.exe card.py --batch --layout card2
```

`--batch` reads active characters from `grail-kun.cardmaker_characters`. Provide the connection string with `MONGODB_URI` or `--mongo-uri`.

MongoDB batch options:

| Flag | Description |
| --- | --- |
| `--mongo-uri` | MongoDB connection string. Defaults to `MONGODB_URI`. |
| `--database` | MongoDB database name. Defaults to `grail-kun`. |
| `--collection` | Character collection name. Defaults to `cardmaker_characters`. |
| `--status` | MongoDB `admin.status` filter. Defaults to `active`; use `all` for no filter. |

### Render One Card From The Command Line

```powershell
..\.venv\Scripts\python.exe card.py --layout card2 --name "Captain Ahab" --role Servant --username "@magnetm" --faceclaim captain_ahab.png --servant-class Lancer --servant-nationality American --alignment "Chaotic Good" --footer "Smoke Test" --output "captain_ahab_test.png"
```

Command-line fields are useful for testing a card without touching MongoDB.

## CLI Arguments

| Flag | Short | Description |
| --- | --- | --- |
| `--layout` | `-l` | Design name, design folder, or `config.json` path. Defaults to `card1`. |
| `--batch` | `-b` | Render characters from MongoDB. Requires `MONGODB_URI` or `--mongo-uri`. |
| `--mongo-uri` | | MongoDB connection string. Defaults to `MONGODB_URI`. |
| `--database` | | MongoDB database name for `--batch`. Defaults to `grail-kun`. |
| `--collection` | | MongoDB collection name for `--batch`. Defaults to `cardmaker_characters`. |
| `--status` | | MongoDB `admin.status` filter for `--batch`. Defaults to `active`; use `all` for no filter. |
| `--name` | | Override character name. |
| `--role` | | Override role text and template selection. |
| `--username` | | Override username. Values may include or omit `@`. |
| `--faceclaim` | | Override faceclaim filename relative to `faceclaims/`. `--faceclaims` is also accepted. |
| `--master-affiliation` | | Override Master affiliation. |
| `--master-occupation` | | Override Master occupation. |
| `--servant-class` | | Override Servant class. |
| `--class` | | Alias for `--servant-class`. |
| `--servant-nationality` | | Override Servant nationality. |
| `--nationality` | | Alias for `--servant-nationality`. |
| `--alignment` | | Override alignment. Shared by Master and Servant cards. |
| `--affiliation` | | Compatibility alias for Master affiliation or Servant class. |
| `--occupation` | | Compatibility alias for Master occupation or Servant nationality. |
| `--footer` | | Override footer text. |
| `--output` | | Custom output filename. Only valid when rendering one card. |

## Character Data

The MongoDB source of truth is `grail-kun.cardmaker_characters`. `card.py` reads this collection for batch rendering. The `characters/_batch_import.json` file is only used by `import_mongo.py` as migration input.

```json
{
  "_id": "1VtnTiKiVNwuZGWCWccBK6MVLgRfFWhOQD3vBozbosLk:captain_ahab",
  "source_doc_id": "1VtnTiKiVNwuZGWCWccBK6MVLgRfFWhOQD3vBozbosLk",
  "name": "Captain Ahab",
  "role": "Servant",
  "type": "PC",
  "username": "@magnetm",
  "userid": "291225855823446016",
  "avatar_path": "captain_ahab.png",
  "footer_text": "Rest of the World",
  "source_url": "https://docs.google.com/document/d/1VtnTiKiVNwuZGWCWccBK6MVLgRfFWhOQD3vBozbosLk/edit",
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

Output filenames prefer `output_path`, then `safe_name`, then `name`.

Master detail fields:

- `affiliation`
- `occupation`
- `alignment`

Servant detail fields:

- `class`
- `nationality`
- `alignment`

## MongoDB Import

`import_mongo.py` migrates `characters/_batch_import.json` into MongoDB and keeps imported documents aligned with the current schema. MongoDB is the long-term source of truth for cardmaker characters; the JSON file is only migration input and is not used by `card.py`.

The importer writes to the `grail-kun` database by default:

- `cardmaker_characters`: one document per character.
- `cardmaker_audit`: one audit document per create/update import event.

### Required Environment

Set the MongoDB connection string before running live imports:

```powershell
$env:MONGODB_URI = "mongodb+srv://..."
```

Do not commit real credentials to the repository. You can also pass the URI for a one-off command with `--mongo-uri`.

### Validate First

Run a dry run before writing anything:

```powershell
..\.venv\Scripts\python.exe import_mongo.py --dry-run
```

The dry run checks that:

- The input is a JSON array.
- Every character has a usable `source_url`.
- Every character has a `safe_name`.
- Every computed character `_id` is unique.

### Live Import

Run the importer from inside `character-compendium`:

```powershell
..\.venv\Scripts\python.exe import_mongo.py
```

By default this reads `characters/_batch_import.json`, uses `card2` as `card.default_design`, and imports characters as `admin.status = "active"`.

Useful options:

| Option | Description |
| --- | --- |
| `--input` | Migration JSON array to import. Defaults to `characters/_batch_import.json`. |
| `--mongo-uri` | MongoDB connection string. Defaults to `MONGODB_URI`. |
| `--database` | Database name. Defaults to `grail-kun`. |
| `--status` | Imported `admin.status`. Defaults to `active`. |
| `--default-design` | Imported `card.default_design`. Defaults to `card2`. |
| `--dry-run` | Validate without writing to MongoDB. |
| `--reorder-existing` | Rewrite existing documents in readable schema order without adding audit events. |

Example:

```powershell
..\.venv\Scripts\python.exe import_mongo.py --default-design card1 --status active
```

### Character IDs

The importer extracts the Google Doc ID from `source_url` and stores it as `source_doc_id`.

Character `_id` uses:

```text
{source_doc_id}:{safe_name}
```

This handles source documents that contain more than one character while still grouping related characters by `source_doc_id`.

### Updates And Audit

The importer upserts characters:

- New characters are inserted and get a `_created` audit event.
- Existing characters are replaced in readable field order.
- Audit events are written only when imported character fields change.
- `card`, `discord`, `admin.created_*`, and `status_history` are preserved across re-imports where appropriate.

The `discord` block stores current publishing state only. It is preserved on re-import and is not treated as character audit data.

### Reorder Existing Documents

MongoDB update operators can make documents display in a less readable order. To refresh existing documents into the importer's schema order without creating audit events:

```powershell
..\.venv\Scripts\python.exe import_mongo.py --reorder-existing
```

This is also useful after adding new preserved schema blocks, such as `discord`.

## Role Templates

Template selection is based on `role`:

- `Servant` uses the selected design's `servant` assets.
- `Master` uses the selected design's `master` assets.
- Roles without `Servant` use the selected design's `master` assets.
- Mixed roles use whichever appears first.

Examples:

- `Human` -> Master template.
- `Homunculus` -> Master template.
- `Master / Servant` -> Master template.
- `Servant / Master` -> Servant template.

## Faceclaims

`avatar_path` is resolved relative to `faceclaims/`.

If `avatar_path` is blank or the file cannot be found, rendering continues without drawing a faceclaim. This allows cards to render before all faceclaim images have been reviewed.

## Designs

Designs live in `designs/{design}/`. A design contains one `config.json` file plus any role-specific image layers it needs:

```text
designs/
  custom_card/
    config.json
    master/
      01_background_base.png
      02_overlay_frame.png
    servant/
      01_background_base.png
      02_overlay_frame.png
```

Use the design folder name with `--layout`, such as `--layout custom_card`. Direct paths to a design folder or config file can also be loaded.

Important layout sections:

- `canvas`: Output dimensions.
- `layers.background_image`: Base card image filename.
- `layers.image_layers`: Optional ordered image stack, drawn bottom to top.
- `layers.color_overlay`: Optional translucent panel.
- `layers.decoration_overlay`: Foreground decoration filename.
- `fonts`: Font files, sizes, and colors.
- `avatar`: Avatar position, size, and shape.
- `templates.master`: Master-specific layout overrides.
- `templates.servant`: Servant-specific layout overrides.
- `templates.*.text`: Text fields and their positions.

Card asset filenames are resolved relative to the design folder. For example, `designs/custom_card/config.json` should refer to `master/01_background_base.png`, not `designs/custom_card/master/01_background_base.png`.

If `layers.image_layers` exists, it replaces the older `background_image` / `decoration_overlay` flow:

```json
{
  "templates": {
    "master": {
      "layers": {
        "image_layers": [
          {"path": "master/01_background_base.png", "fit": "stretch", "opacity": 1},
          {"type": "color_overlay", "color": [20, 20, 20], "opacity": 204, "border_radius": 40, "margin": 0},
          {"path": "master/02_foreground_frame.png", "fit": "stretch", "opacity": 1}
        ]
      }
    }
  }
}
```

### Text Placement

Each entry in `templates.*.text` draws one piece of text. The key is used as the character-data field unless `field` is supplied.

```json
{
  "templates": {
    "master": {
      "text": {
        "name": {
          "x": 574,
          "y": 208,
          "font": "name",
          "anchor": "mt",
          "max_width": 860,
          "max_lines": 3,
          "line_height": 116
        },
        "affiliation": {
          "x": 1600,
          "y": 759,
          "font": "detail",
          "anchor": "ra"
        },
        "footer": {
          "field": "footer_text",
          "x": 900,
          "y": 1080,
          "font": "footer",
          "anchor": "mm"
        }
      }
    }
  }
}
```

Supported text options:

- `field`: Character-data field to draw. Defaults to the text entry key.
- `value`: Literal text to draw instead of reading character data.
- `x`, `y`: Text anchor position.
- `font`: Font key from the layout's `fonts` section. Defaults to `detail`.
- `anchor`: Pillow text anchor, such as `mt`, `mm`, `ra`, or `la`.
- `prefix`: Optional prefix, useful for usernames.
- `max_width`: Enables wrapping and dynamic shrinking.
- `max_lines`: Maximum wrapped lines.
- `line_height`: Vertical distance between wrapped lines.

Master templates usually render:

- `name`
- `role`
- `username`
- `affiliation`
- `occupation`
- `alignment`
- `footer_text`

Servant templates usually render:

- `name`
- `role`
- `username`
- `class`
- `nationality`
- `alignment`
- `footer_text`

Because placement is per field, future card designs can move any text independently. For example, `alignment` can be placed in a footer badge while `affiliation` sits near the avatar.

### Role-Specific Overrides

The renderer starts with the base layout, then merges in the selected role template. This means future designs can override only what changes:

```json
{
  "templates": {
    "master": {
      "avatar": {"x": 1100, "y": 68, "size": 600},
      "text": {}
    },
    "servant": {
      "avatar": {"x": 80, "y": 80, "size": 480},
      "text": {}
    }
  }
}
```

Current `card1` and `card2` designs define complete `text` maps for both Master and Servant templates.

## Dependencies

Dependencies are listed in `requirements.txt`.

- Python 3.14.2 was used for the current local setup.
- Pillow is required for rendering.
