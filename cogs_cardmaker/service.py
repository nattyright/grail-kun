from __future__ import annotations

import asyncio
import io
import re
from pathlib import Path
from typing import Any

from PIL import Image

from cogs_cardmaker.card import CardGenerator, Defaults


STATUS_TAGS = {"active": "active", "hiatus": "hiatus", "retired": "retired"}
ROLE_TAGS = {"master", "servant"}
TYPE_TAGS = {"pc", "npc"}
PLAYER_STATUS_TAGS = {"looking for rp", "looking for master", "looking for servant"}
ALLOWED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
MAX_FACECLAIM_BYTES = 1_000_000
MAX_CUSTOM_BACKGROUND_BYTES = 8_000_000


def extract_doc_id(value: str | None) -> str | None:
    if not value:
        return None
    match = re.search(r"/d/([^/?#]+)", value)
    if match:
        return match.group(1)
    if re.fullmatch(r"[-\w]{20,}", value.strip()):
        return value.strip()
    return None


def safe_name_for(name: str) -> str:
    safe = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
    return safe or "character"


def canonical_username(user: Any) -> str:
    name = getattr(user, "display_name", None) or getattr(user, "name", None) or str(user)
    name = str(name).strip()
    return name if name.startswith("@") else f"@{name}"


def normalize_username(value: str | None) -> str:
    value = (value or "").strip()
    if not value:
        return ""
    return value if value.startswith("@") else f"@{value}"


def template_role_for(character: dict[str, Any]) -> str:
    role = str(character.get("role") or "").lower()
    master_idx = role.find("master")
    servant_idx = role.find("servant")
    if master_idx != -1 and servant_idx != -1:
        return "master" if master_idx < servant_idx else "servant"
    if servant_idx != -1:
        return "servant"
    return "master"


def debut_label(footer_text: str | None) -> str:
    # first = (footer_text or "").split("|", 1)[0].strip()
    # we are posting the full footer now
    first = (footer_text or "")
    if first.lower() == "rest of the world":
        return "ROTW"
    return first or "Unknown"


def role_label(character: dict[str, Any]) -> str:
    if template_role_for(character) == "servant":
        return "Servant"
    return "Master"


def thread_title(character: dict[str, Any]) -> str:
    username = normalize_username(character.get("username")) or "@unknown"
    return " | ".join([
        role_label(character),
        str(character.get("name") or "Unnamed Character").strip(),
        username,
        debut_label(character.get("footer_text")),
    ])


def strip_links(text: str) -> str:
    text = re.sub(r"https?://\S+", "", text or "")
    text = re.sub(r"www\.\S+", "", text)
    return text.strip()


def generated_starter_body(character: dict[str, Any]) -> str:
    lines = [
        f"**Name:** {character.get('name') or ''}",
        f"**Role:** {character.get('role') or ''}",
        f"**Type:** {character.get('type') or ''}",
    ]
    userid = character.get("userid")
    if userid:
        lines.append(f"**Player:** <@{userid}>")
    else:
        lines.append(f"**Player:** {normalize_username(character.get('username'))}")

    if template_role_for(character) == "servant":
        if character.get("class"):
            lines.append(f"**Class:** {character.get('class')}")
        if character.get("nationality"):
            lines.append(f"**Nationality:** {character.get('nationality')}")
    else:
        if character.get("affiliation"):
            lines.append(f"**Affiliation:** {character.get('affiliation')}")
        if character.get("occupation"):
            lines.append(f"**Occupation:** {character.get('occupation')}")

    if character.get("alignment"):
        lines.append(f"**Alignment:** {character.get('alignment')}")
    if character.get("footer_text"):
        lines.append(f"**Debut:** {character.get('footer_text')}")

    return strip_links("\n".join(lines))


def starter_body(character: dict[str, Any]) -> str:
    body = ((character.get("discord") or {}).get("starter_body") or "").strip()
    return strip_links(body) if body else generated_starter_body(character)


def required_card_design(character: dict[str, Any], design: str | None = None) -> str:
    layout = design or (character.get("card") or {}).get("default_design")
    if not layout:
        character_id = character.get("_id") or character.get("name") or "unknown character"
        raise ValueError(f"Character {character_id!r} is missing card.default_design.")
    return str(layout)


def render_card_bytes(
    character: dict[str, Any],
    design: str | None = None,
    runtime_images: dict[str, Image.Image] | None = None,
) -> io.BytesIO:
    layout = required_card_design(character, design)
    image = CardGenerator(layout).render(character, runtime_images=runtime_images)
    buf = io.BytesIO()
    image.save(buf, "PNG")
    buf.seek(0)
    return buf


async def render_card_bytes_async(
    character: dict[str, Any],
    design: str | None = None,
    runtime_images: dict[str, Image.Image] | None = None,
) -> io.BytesIO:
    return await asyncio.to_thread(render_card_bytes, character, design, runtime_images)


def design_supports_custom_background(character: dict[str, Any], design: str | None = None) -> bool:
    layout = required_card_design(character, design)
    role = template_role_for(character)
    return CardGenerator(layout).supports_runtime_image("background", role)


async def design_supports_custom_background_async(character: dict[str, Any], design: str | None = None) -> bool:
    return await asyncio.to_thread(design_supports_custom_background, character, design)


def image_filename(character: dict[str, Any]) -> str:
    safe = character.get("safe_name") or safe_name_for(str(character.get("name") or "character"))
    return f"{safe}_card.png"


def faceclaim_filename(character: dict[str, Any], extension: str) -> str:
    existing = str(character.get("avatar_path") or "").strip()
    if existing:
        return Path(existing).name
    safe = character.get("safe_name") or safe_name_for(str(character.get("name") or "character"))
    doc_id = character.get("source_doc_id") or "unknown_doc"
    return f"{safe}_{doc_id}{extension.lower()}"


def _save_image_under_limit(img: Image.Image, path: Path, fmt: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fmt == "PNG":
        working = img
        for _ in range(5):
            working.save(path, "PNG", optimize=True)
            if path.stat().st_size <= MAX_FACECLAIM_BYTES:
                return
            width, height = working.size
            if width <= 512 and height <= 512:
                break
            scale = 0.85
            working = working.resize((max(1, int(width * scale)), max(1, int(height * scale))), Image.Resampling.LANCZOS)
        raise ValueError("PNG faceclaim is still over 1 MB after safe optimization. Please upload a smaller PNG.")

    if fmt in {"JPEG", "WEBP"}:
        working = img.convert("RGB") if fmt == "JPEG" else img
        quality = 92
        while quality >= 45:
            working.save(path, fmt, quality=quality, optimize=True)
            if path.stat().st_size <= MAX_FACECLAIM_BYTES:
                return
            quality -= 7
        width, height = working.size
        while path.stat().st_size > MAX_FACECLAIM_BYTES and width > 512 and height > 512:
            width = int(width * 0.85)
            height = int(height * 0.85)
            working = working.resize((width, height), Image.Resampling.LANCZOS)
            working.save(path, fmt, quality=70, optimize=True)
        if path.stat().st_size <= MAX_FACECLAIM_BYTES:
            return
        raise ValueError("Faceclaim is still over 1 MB after compression. Please upload a smaller image.")

    img.save(path, fmt)
    if path.stat().st_size > MAX_FACECLAIM_BYTES:
        raise ValueError("GIF faceclaims must be 1 MB or smaller.")


def save_faceclaim_bytes(character: dict[str, Any], data: bytes, filename: str) -> str:
    uploaded_ext = Path(filename).suffix.lower()
    if uploaded_ext not in ALLOWED_IMAGE_EXTENSIONS:
        raise ValueError("Faceclaim must be PNG, JPG, JPEG, WEBP, or GIF.")

    output_name = faceclaim_filename(character, uploaded_ext)
    output_ext = Path(output_name).suffix.lower()
    if output_ext not in ALLOWED_IMAGE_EXTENSIONS:
        output_ext = uploaded_ext
        output_name = f"{Path(output_name).stem}{output_ext}"
    output_path = Defaults.FACECLAIMS_DIR / output_name
    with Image.open(io.BytesIO(data)) as img:
        img.verify()
    with Image.open(io.BytesIO(data)) as img:
        fmt = {
            ".jpg": "JPEG",
            ".jpeg": "JPEG",
            ".png": "PNG",
            ".webp": "WEBP",
            ".gif": "GIF",
        }[output_ext]
        _save_image_under_limit(img, output_path, fmt)
    return output_name


async def save_faceclaim_bytes_async(character: dict[str, Any], data: bytes, filename: str) -> str:
    return await asyncio.to_thread(save_faceclaim_bytes, character, data, filename)


def load_temporary_background_image(data: bytes, filename: str) -> Image.Image:
    uploaded_ext = Path(filename).suffix.lower()
    if uploaded_ext not in ALLOWED_IMAGE_EXTENSIONS:
        raise ValueError("Background must be PNG, JPG, JPEG, WEBP, or GIF.")
    if len(data) > MAX_CUSTOM_BACKGROUND_BYTES:
        raise ValueError("Background image must be 8 MB or smaller.")

    with Image.open(io.BytesIO(data)) as img:
        img.verify()
    with Image.open(io.BytesIO(data)) as img:
        return img.convert("RGBA")


async def load_temporary_background_image_async(data: bytes, filename: str) -> Image.Image:
    return await asyncio.to_thread(load_temporary_background_image, data, filename)


def parse_create_template(content: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line.startswith("--") or ":" not in line:
            continue
        key, value = line[2:].split(":", 1)
        fields[key.strip().lower()] = value.strip()
    return fields


def create_template_text() -> str:
    servant_template = (
        "f.card create\n"
        "--doc: google_doc_URL\n"
        "--name: character_name\n"
        "--role: Master OR Servant OR Other (Human,DOG,etc.)\n"
        "--scope: full OR minor\n"
        "--type: PC OR NPC\n"
        "--player: @mention\n"
        "--class: class\n"
        "--nationality: nationality\n"
        "--alignment: alignment\n"
        "--footer: origin_event_name | origin_event_details\n"
        "--design: default-rotw OR other_design_name\n"
        "\n"
        "Attach a faceclaim image to this same message if you want to set one."
    )
    master_template = (
        "f.card create\n"
        "--doc: google_doc_URL\n"
        "--name: character_name\n"
        "--role: Master OR Servant OR Other (Human,DOG,etc.)\n"
        "--scope: full OR minor\n"
        "--type: PC OR NPC\n"
        "--player: @mention\n"
        "--affiliation: affiliation\n"
        "--occupation: occupation\n"
        "--alignment: alignment\n"
        "--footer: origin_event_name | origin_event_details\n"
        "--design: default-rotw OR other_design_name\n"
        "\n"
        "Attach a faceclaim image to this same message if you want to set one."
    )

    return (
        "Master / non-Servant template:\n"
        f"{master_template}\n\n"
        "Servant template:\n"
        f"{servant_template}"
    )
