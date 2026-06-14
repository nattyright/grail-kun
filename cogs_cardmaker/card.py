import json
import sys
import argparse
import copy
import os
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageOps
from pymongo import MongoClient


# --- DIRECTORY SETTINGS ---
class Defaults:
    BASE_DIR = Path(__file__).resolve().parent
    DESIGNS_DIR = BASE_DIR / "designs"
    FONTS_DIR = BASE_DIR / "fonts"
    FACECLAIMS_DIR = BASE_DIR / "faceclaims"
    OUTPUT_DIR = BASE_DIR / "outputs"
    MONGO_DATABASE = "grail-kun"
    MONGO_CHARACTER_COLLECTION = "cardmaker_characters"


class CardGenerator:
    def __init__(self, layout_name):
        self.design_dir = None
        self.layout_cfg = self._load_layout(layout_name)
        self.font_cache = {}
        self.asset_cache = {}
        self.canvas_size = (
            self.layout_cfg["canvas"]["width"],
            self.layout_cfg["canvas"]["height"]
        )
        self._validate_directories()

    def _validate_directories(self):
        """Ensure all required asset directories exist."""
        required = [
            Defaults.FACECLAIMS_DIR, Defaults.FONTS_DIR,
            Defaults.DESIGNS_DIR,
            Defaults.OUTPUT_DIR
        ]
        for folder in required:
            folder.mkdir(parents=True, exist_ok=True)

    def _load_layout(self, name):
        path = Path(name)
        candidates = []

        if path.is_file():
            candidates.append(path)
        elif path.is_dir():
            candidates.append(path / "config.json")
        else:
            candidates.extend([
                Defaults.DESIGNS_DIR / name / "config.json",
            ])

        layout_path = next((candidate for candidate in candidates if candidate.exists()), None)
        if layout_path is None:
            searched = ", ".join(str(candidate) for candidate in candidates)
            raise FileNotFoundError(f"Layout not found. Searched: {searched}")

        self.design_dir = layout_path.parent if layout_path.name == "config.json" else None

        with open(layout_path, "r", encoding="utf-8") as f:
            config = json.load(f)
        
        # Format colors into tuples for Pillow
        for font in config["fonts"].values():
            font["color"] = tuple(font["color"])
        
        overlay = config.get("layers", {}).get("color_overlay", {})
        if "color" in overlay:
            overlay["color"] = tuple(overlay["color"])

        for template in config.get("templates", {}).values():
            overlay = template.get("layers", {}).get("color_overlay")
            if overlay and "color" in overlay:
                overlay["color"] = tuple(overlay["color"])
            
        return config

    def _resolved_layout(self, template_role):
        layout = copy.deepcopy(self.layout_cfg)
        template = layout.pop("templates", {}).get(template_role, {})
        return self._deep_merge(layout, template)

    def _deep_merge(self, base, override):
        merged = copy.deepcopy(base)
        for key, value in override.items():
            if isinstance(value, dict) and isinstance(merged.get(key), dict):
                merged[key] = self._deep_merge(merged[key], value)
            else:
                merged[key] = copy.deepcopy(value)
        return merged

    def _get_font(self, font_config, size=None, weight=None):
        """Load and cache fonts to improve performance."""
        size = size or font_config["size"]
        weight = weight or font_config.get("weight")
        cache_key = (font_config["path"], size, weight)

        if cache_key in self.font_cache:
            return self.font_cache[cache_key]

        font_path = Path(font_config["path"])
        if not font_path.is_absolute():
            font_path = Defaults.FONTS_DIR / font_path

        font = ImageFont.truetype(str(font_path), size)
        
        if weight:
            try:
                # Handle variable font weight if supported by the environment's Pillow version
                axes = font.get_variation_axes()
                values = []
                for axis in axes:
                    name = axis.get("name", b"").lower()
                    if b"weight" in name or b"wght" in name:
                        values.append(float(weight))
                    else:
                        values.append(float(axis.get("default", 0)))
                font.set_variation_by_axes(values)
            except Exception:
                pass # Graceful fallback for non-variable fonts or incompatible Pillow versions
        
        self.font_cache[cache_key] = font
        return font

    def _template_role_for(self, data):
        role = data.get("role", "")
        role_lower = role.lower()
        master_idx = role_lower.find("master")
        servant_idx = role_lower.find("servant")

        if master_idx != -1 and servant_idx != -1:
            return "master" if master_idx < servant_idx else "servant"
        if servant_idx != -1:
            return "servant"
        return "master"

    def _load_image(self, path, is_faceclaim=False, template_role=None, missing_ok=False):
        """Load and cache card design assets."""
        cache_key = (str(path), template_role)
        if cache_key in self.asset_cache and not is_faceclaim:
            return self.asset_cache[cache_key]

        img_path = Path(path)
        if not img_path.is_absolute():
            if is_faceclaim:
                img_path = Defaults.FACECLAIMS_DIR / img_path
            else:
                candidates = []
                if self.design_dir:
                    candidates.append(self.design_dir / img_path)
                if not candidates:
                    candidates.append(img_path)
                img_path = next((candidate for candidate in candidates if candidate.exists()), candidates[0])

        if not img_path.exists():
            if missing_ok:
                return None
            raise FileNotFoundError(f"Image asset not found: {img_path}")

        img = Image.open(img_path).convert("RGBA")
        if not is_faceclaim:
            self.asset_cache[cache_key] = img
        return img

    def _fit_image(self, image, size, mode="cover"):
        target_w, target_h = size
        if mode == "stretch":
            return image.resize(size, Image.Resampling.LANCZOS)

        img_w, img_h = image.size
        if mode == "cover":
            scale = max(target_w / img_w, target_h / img_h)
        else: # contain
            scale = min(target_w / img_w, target_h / img_h)
        
        new_w, new_h = int(img_w * scale), int(img_h * scale)
        resized = image.resize((new_w, new_h), Image.Resampling.LANCZOS)
        
        canvas = Image.new("RGBA", size, (0, 0, 0, 0))
        canvas.alpha_composite(resized, ((target_w - new_w) // 2, (target_h - new_h) // 2))
        return canvas

    def _avatar_size(self, avatar_config):
        size = avatar_config.get("size")
        if isinstance(size, (list, tuple)):
            return int(size[0]), int(size[1])

        width = avatar_config.get("width", size)
        height = avatar_config.get("height", size)
        if width is None or height is None:
            raise ValueError("Avatar config requires size or both width and height.")

        return int(width), int(height)

    def _avatar_mask(self, avatar_config, size):
        shape = str(avatar_config.get("shape", "rectangle")).strip().lower()
        shape = shape.replace("-", "_").replace(" ", "_")
        width, height = size

        if shape in {"none", "square", "rectangle", "rect"}:
            return None

        mask = Image.new("L", size, 0)
        draw = ImageDraw.Draw(mask)
        bounds = (0, 0, width - 1, height - 1)

        if shape in {"circle", "oval", "ellipse"}:
            draw.ellipse(bounds, fill=255)
        elif shape == "diamond":
            draw.polygon(
                [
                    (width // 2, 0),
                    (width - 1, height // 2),
                    (width // 2, height - 1),
                    (0, height // 2),
                ],
                fill=255,
            )
        elif shape in {"rounded", "rounded_square", "rounded_rectangle", "rounded_rect"}:
            radius = avatar_config.get("radius", avatar_config.get("border_radius"))
            if radius is None:
                radius = min(width, height) // 8
            draw.rounded_rectangle(bounds, radius=int(radius), fill=255)
        else:
            supported = "circle, square, rectangle, diamond, oval, ellipse, rounded_rectangle"
            raise ValueError(f"Unsupported avatar shape '{shape}'. Supported shapes: {supported}.")

        return mask

    def _prepare_avatar(self, image, avatar_config):
        size = self._avatar_size(avatar_config)
        avatar = ImageOps.fit(image, size, centering=(0.5, 0.5))
        mask = self._avatar_mask(avatar_config, size)
        if mask is None:
            return avatar

        clipped = Image.new("RGBA", size, (0, 0, 0, 0))
        clipped.paste(avatar, (0, 0), mask)
        return clipped

    def supports_runtime_image(self, slot, template_role=None):
        roles = [template_role] if template_role else ["master", "servant"]
        for role in roles:
            layout = self._resolved_layout(role)
            for layer_cfg in layout.get("layers", {}).get("image_layers", []):
                if layer_cfg.get("customizable") == slot:
                    return True
        return False

    def _runtime_layer_image(self, layer_cfg, runtime_images):
        slot = layer_cfg.get("customizable")
        if not slot or not runtime_images or slot not in runtime_images:
            return None
        image = runtime_images[slot]
        if isinstance(image, Image.Image):
            return image.convert("RGBA")
        raise TypeError(f"Runtime image for '{slot}' must be a PIL Image.")

    def _create_base_canvas(self, layout, template_role, runtime_images=None):
        image_layers = layout["layers"]["image_layers"]
        canvas = Image.new("RGBA", self.canvas_size, (0, 0, 0, 0))
        for layer_cfg in image_layers:
            if layer_cfg.get("type") == "color_overlay":
                self._apply_color_overlay(canvas, layer_cfg)
                continue

            source_img = self._runtime_layer_image(layer_cfg, runtime_images)
            if source_img is None:
                source_img = self._load_image(layer_cfg["path"], template_role=template_role)

            layer_img = self._fit_image(
                source_img,
                self.canvas_size,
                layer_cfg.get("fit", "cover")
            )
            opacity = layer_cfg.get("opacity", 1)
            if opacity <= 1:
                opacity = int(opacity * 255)
            if opacity < 255:
                r, g, b, a = layer_img.split()
                a = a.point(lambda p: int(p * (opacity / 255)))
                layer_img.putalpha(a)
            canvas.alpha_composite(layer_img)
        return canvas

    def _apply_color_overlay(self, canvas, color_cfg):
        if not color_cfg or not color_cfg.get("enabled", True):
            return

        panel = Image.new("RGBA", self.canvas_size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(panel)
        radius = color_cfg.get("border_radius", 0)
        margin = color_cfg.get("margin", 0)
        color = tuple(color_cfg["color"])
        opacity = color_cfg.get("opacity", 255)
        if opacity <= 1:
            opacity = int(opacity * 255)
        fill = (*color, opacity)
        
        box = (margin, margin, self.canvas_size[0] - margin, self.canvas_size[1] - margin)
        draw.rounded_rectangle(box, radius=radius, fill=fill)
        canvas.alpha_composite(panel)

    def _fit_text(self, draw, text, font_config, max_width, max_lines):
        size = font_config["size"]
        min_size = font_config.get("min_size", size)
        
        while size >= min_size:
            font = self._get_font(font_config, size)
            lines = self._wrap_text(draw, text, font, max_width, max_lines)
            if self._all_words_fit(text, lines):
                return font, lines
            size -= 2
        
        # Final fallback to min size
        font = self._get_font(font_config, min_size)
        return font, self._wrap_text(draw, text, font, max_width, max_lines)

    def _wrap_text(self, draw, text, font, max_width, max_lines):
        # Respect existing newlines first
        input_lines = text.split('\n')
        final_lines = []

        for line in input_lines:
            words = line.split()
            current = ""
            for word in words:
                test = f"{current} {word}".strip()
                bbox = draw.textbbox((0, 0), test, font=font)
                if (bbox[2] - bbox[0]) <= max_width:
                    current = test
                else:
                    if current: final_lines.append(current)
                    current = word
                if len(final_lines) >= max_lines: break
            if current and len(final_lines) < max_lines: final_lines.append(current)
            if len(final_lines) >= max_lines: break
            
        return final_lines

    def _all_words_fit(self, original, lines):
        # Ignore newlines for comparison
        original_words = original.replace('\n', ' ').split()
        rendered_words = " ".join(lines).split()
        return len(rendered_words) >= len(original_words)

    def render(self, data, runtime_images=None):
        """Generate the final card image from character data."""
        template_role = self._template_role_for(data)
        layout = self._resolved_layout(template_role)
        card = self._create_base_canvas(layout, template_role, runtime_images=runtime_images)
        draw = ImageDraw.Draw(card)
        fonts = layout["fonts"]

        # 1. Avatar
        av_cfg = layout["avatar"]
        avatar_path = data.get("avatar_path")
        if avatar_path:
            faceclaim = self._load_image(avatar_path, is_faceclaim=True, missing_ok=True)
            if faceclaim:
                faceclaim = self._prepare_avatar(faceclaim, av_cfg)
                card.alpha_composite(faceclaim, (av_cfg["x"], av_cfg["y"]))

        self._render_text_elements(draw, dict(data), layout)

        return card

    def _render_text_elements(self, draw, data, layout):
        fonts = layout["fonts"]
        for element_id, cfg in layout.get("text", {}).items():
            field = cfg.get("field", element_id)
            value = data.get(field)
            if value is None:
                continue

            text = str(value)
            prefix = cfg.get("prefix")
            if prefix and text and not text.startswith(prefix):
                text = f"{prefix}{text}"

            font_config = fonts[cfg.get("font", "detail")]
            anchor = cfg.get("anchor", "la")
            x = cfg["x"]
            y = cfg["y"]

            max_width = cfg.get("max_width")
            max_lines = cfg.get("max_lines", 1)
            if max_width:
                font, lines = self._fit_text(draw, text, font_config, max_width, max_lines)
                line_height = cfg.get("line_height", font_config["size"])
                for i, line in enumerate(lines):
                    draw.text(
                        (x, y + i * line_height),
                        line,
                        font=font,
                        fill=font_config["color"],
                        anchor=anchor
                    )
            else:
                draw.text(
                    (x, y),
                    text,
                    font=self._get_font(font_config),
                    fill=font_config["color"],
                    anchor=anchor
                )

def iter_mongo_character_items(mongo_uri, database, collection, status="active"):
    """Yield character data from MongoDB."""
    client = MongoClient(mongo_uri)
    query = {} if status == "all" else {"admin.status": status}
    cursor = client[database][collection].find(query).sort("name", 1)

    for item in cursor:
        yield item, item.get("safe_name") or item.get("name") or item["_id"]


def character_from_overrides(args):
    data = {}
    overrides = {
        "name": args.name,
        "role": args.role,
        "username": args.username,
        "avatar_path": args.faceclaim,
        "alignment": args.alignment,
        "footer_text": args.footer,
    }
    for key, value in overrides.items():
        if value:
            data[key] = value

    return data


def default_output_filename(char_data, fallback_name):
    stem = (
        char_data.get("output_path")
        or char_data.get("safe_name")
        or char_data.get("name")
        or fallback_name
    )
    path = Path(stem)
    if path.suffix:
        return path.name
    return f"{path.name}.png"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Professional Character Card Generator")
    parser.add_argument("-l", "--layout", default="card1", help="Design name, design folder, or config.json path")
    parser.add_argument("-b", "--batch", action="store_true", help="Render characters from MongoDB")
    parser.add_argument("--mongo-uri", help="MongoDB connection string. Defaults to MONGODB_URI.")
    parser.add_argument("--database", default=Defaults.MONGO_DATABASE, help="MongoDB database name for --batch.")
    parser.add_argument("--collection", default=Defaults.MONGO_CHARACTER_COLLECTION, help="MongoDB collection name for --batch.")
    parser.add_argument("--status", default="active", help="MongoDB admin.status filter for --batch. Use 'all' for no filter.")
    
    # Character Data Overrides
    group = parser.add_argument_group("character overrides")
    group.add_argument("--name", help="Character name")
    group.add_argument("--role", help="Role")
    group.add_argument("--username", help="Username")
    group.add_argument("--faceclaim", "--faceclaims", dest="faceclaim", help="Faceclaim filename relative to faceclaims/")
    group.add_argument("--master-affiliation", help="Master affiliation text")
    group.add_argument("--master-occupation", help="Master occupation text")
    group.add_argument("--servant-class", "--class", dest="servant_class", help="Servant class text")
    group.add_argument("--servant-nationality", "--nationality", dest="servant_nationality", help="Servant nationality text")
    group.add_argument("--alignment", help="Alignment text")
    group.add_argument("--affiliation", help="Compatibility alias for Master affiliation or Servant class")
    group.add_argument("--occupation", help="Compatibility alias for Master occupation or Servant nationality")
    group.add_argument("--footer", help="Footer text")
    group.add_argument("--output", help="Custom output filename")

    args = parser.parse_args()

    try:
        gen = CardGenerator(args.layout)
        mongo_uri = args.mongo_uri or os.environ.get("MONGODB_URI")

        # Determine character data to process.
        if args.batch:
            if not mongo_uri:
                parser.error("--batch requires --mongo-uri or MONGODB_URI.")
            expanded_items = list(iter_mongo_character_items(
                mongo_uri,
                args.database,
                args.collection,
                args.status,
            ))
        else:
            char_data = character_from_overrides(args)
            # Design configs may include sample character data for smoke tests.
            if not char_data and "character" in gen.layout_cfg:
                char_data = dict(gen.layout_cfg.get("character", {}))
            if not char_data:
                parser.error("Please provide command-line character fields or use --batch with MongoDB.")
            expanded_items = [(char_data, char_data.get("safe_name") or char_data.get("name") or "manual_card")]

        processed = 0
        if args.output and len(expanded_items) > 1:
            parser.error("--output can only be used when rendering one card.")

        for char_data, char_name_from_file in expanded_items:
            template_role = gen._template_role_for(char_data)
            if args.master_affiliation:
                char_data["affiliation"] = args.master_affiliation
            if args.master_occupation:
                char_data["occupation"] = args.master_occupation
            if args.servant_class:
                char_data["class"] = args.servant_class
            if args.servant_nationality:
                char_data["nationality"] = args.servant_nationality

            # Older commands used Master field names for both templates.
            if args.affiliation:
                key = "class" if template_role == "servant" else "affiliation"
                char_data[key] = args.affiliation
            if args.occupation:
                key = "nationality" if template_role == "servant" else "occupation"
                char_data[key] = args.occupation

            # Auto-discover faceclaim if missing or default
            if "avatar_path" not in char_data or not char_data["avatar_path"]:
                name = char_data.get("name", "Unknown")
                # Look for name.png or name.jpg
                possible_faceclaims = [f"{name}.png", f"{name}.jpg", f"{name}.webp"]
                for faceclaim in possible_faceclaims:
                    if (Defaults.FACECLAIMS_DIR / faceclaim).exists():
                        char_data["avatar_path"] = faceclaim
                        break

            # Finalize character data
            output_filename = args.output if args.output else default_output_filename(char_data, char_name_from_file)
            output_path = Defaults.OUTPUT_DIR / output_filename
            
            print(f"Rendering: {char_data.get('name', 'Unknown')} -> {output_path}")
            card_img = gen.render(char_data)
            card_img.save(output_path)
            processed += 1

        print(f"\nSuccess! Processed {processed} card(s).")

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
