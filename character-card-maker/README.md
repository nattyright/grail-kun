# Character Card Maker

A static browser tool for sketching card designs visually before editing `character-compendium` design config JSON.

Open `index.html` in a browser. No build step or server is required.

## What It Does

- Keeps the design canvas dynamic, defaulting to 1600 x 1000 (an 8:5 ratio). Dimensions are updated when importing designs.
- Accepts uploaded base images that match the canvas ratio.
- Supports multiple image layers with opacity and ordering controls.
- Keeps separate Master and Servant image layer stacks.
- Allows layers to be hidden while designing.
- Keeps asset uploads, layer controls, avatar controls, text controls, and export actions in focused tabs.
- Allows an image layer to be marked as the one-time customizable background slot.
- Supports a local avatar preview image and exports avatar position, dimensions, and shape settings used by the card renderer.
- Supports uploaded `.ttf`, `.otf`, `.woff`, and `.woff2` fonts for live preview.
- Uses fixed Master and Servant text field sets.
- Lets text fields be dragged directly on the preview.
- Lets each text field configure sample content, font, size, color, anchor, position, max width, and line height.
- Exports design config JSON compatible with the flexible `templates.*.text` direction used by `character-compendium`.
- Exports a PNG preview.
- Exports a ZIP package containing the JSON config, ordered image layers, uploaded fonts, Master and Servant preview PNGs, and manifest.
- Imports ZIP packages created by this tool.

## Fixed Text Fields

Master fields:

- `name`
- `role`
- `username`
- `affiliation`
- `occupation`
- `alignment`
- `footer_text`

Servant fields:

- `name`
- `role`
- `username`
- `class`
- `nationality`
- `alignment`
- `footer_text`

The text fields cannot be added or removed because these are the fields expected by the card renderer. Use the role selector to switch between Master and Servant positioning.

Drag text fields or the avatar preview directly on the canvas, or type exact numeric positions into the controls. Snap-to-grid rounds dragged positions to the configured grid size.

## Image Layers

Master and Servant have separate image stacks. Use the asset role selector to switch between them.

Hidden image layers remain in the editor, but they are ignored by config and package export. This lets you keep alternate ideas around without accidentally shipping them into the renderer.

Use the Layers tab to select and configure image layers. Opacity, movement, visibility, and custom-background settings always apply to the currently selected layer.

Select an image layer and enable `Custom background slot` when that layer should export with `customizable: "background"`. Only one layer per role can be marked as the custom background slot. The Discord bot can temporarily replace that layer during a one-time custom-background render. The uploaded background itself is not saved by the bot.

## Avatar Export

Upload an avatar preview image from the Assets tab, then use the Avatar tab to configure `config.avatar` settings for position, dimensions, and shape. Circle and square use one size value; rectangular shapes use width and height. Supported shape values match the Python renderer: `circle`, `square`, `rectangle`, `diamond`, `oval`, and `rounded_rectangle`.

The avatar preview image is only for local design work and is not included in exported design packages.

## Export Package

The package ZIP uses predictable filenames:

- `designs/{layout_name}/config.json`
- `preview/{layout_name}_master_preview.png`
- `preview/{layout_name}_servant_preview.png`
- `designs/{layout_name}/{role}/01_background_{source_name}.png`
- `designs/{layout_name}/{role}/02_overlay_{source_name}.png`
- `designs/{layout_name}/{role}/03_foreground_{source_name}.png`
- `fonts/{font_name}.ttf`
- `manifest.json`

Layer order is bottom to top. The numeric prefixes keep the order obvious while browsing files. In actual packages, layers are grouped by design first, then role:

- `designs/{layout_name}/master/01_background_{source_name}.png`
- `designs/{layout_name}/master/02_overlay_{source_name}.png`
- `designs/{layout_name}/servant/01_background_{source_name}.png`
- `designs/{layout_name}/servant/02_overlay_{source_name}.png`

The exported config references those files relative to the design folder, such as `master/01_background_base.png`.

Font paths in the exported config are relative to `character-compendium/fonts/`, and uploaded font files are included under `fonts/` in the package.

## Import

Use the Import button to load a ZIP package created by this tool. Package import restores:

- design config JSON
- Master and Servant text placement
- visible Master and Servant image layers
- customizable background layer flags
- avatar export settings
- uploaded fonts included in the package

Loose JSON import is not currently supported because it cannot restore the referenced image and font files by itself.

## Notes

This is a visual aid, not a full replacement for `character-compendium/card.py`.

The exported JSON still needs review before dropping it into the compendium because browser-uploaded fonts and image files must be copied into the matching Python project folders.
