"""
Text processing + hashing utilities for sheetwatch (Markdown-first).

Responsibilities:
- Extract Google Doc ID / URL from arbitrary message content.
- Normalize exported doc text to be stable under cosmetic edits.
- Strip irrelevant / high-noise Markdown constructs:
    - images (inline, ref, and base64 image definitions)
    - navigation/link bars
    - heavy layout tables (flatten to text)
- Parse normalized Markdown into flexible sections using Markdown headings:
    - users may reorder sections
    - users may add custom sections
- Compute per-section SHA256 hashes + a stable global hash (order-independent).
- Generate readable word-level unified diffs for changed sections.

This module is intentionally pure (no Discord state, no Mongo, no network),
so it’s easy to test and tweak.
"""

from __future__ import annotations

import re
import hashlib
import unicodedata
import difflib
from typing import Dict, List, Optional, Tuple


# -----------------------------
# Google Doc URL patterns
# -----------------------------

MENTION_ID_RE = re.compile(r"<@!?(\d+)>")

DOC_ID_RE = re.compile(r"https?://docs\.google\.com/document/d/([a-zA-Z0-9_-]+)")
DOC_URL_RE = re.compile(r"https?://docs\.google\.com/document/d/[a-zA-Z0-9_-]+(?:/[^\s>]*)?")


# -----------------------------
# Discord message/embed parsing
# -----------------------------

def extract_user_ids(text: str) -> List[int]:
    return [int(x) for x in MENTION_ID_RE.findall(text or "")]

def extract_doc_urls(text: str) -> List[str]:
    return DOC_URL_RE.findall(text or "")

def doc_id_from_url(url: str) -> Optional[str]:
    m = DOC_ID_RE.search(url or "")
    return m.group(1) if m else None

def extract_doc_id(text: str) -> Optional[str]:
    m = DOC_ID_RE.search(text or "")
    return m.group(1) if m else None

def extract_doc_url(text: str) -> Optional[str]:
    m = DOC_URL_RE.search(text or "")
    return m.group(0) if m else None

def flatten_embed_text(emb) -> str:
    parts: List[str] = []
    if getattr(emb, "url", None):
        parts.append(str(emb.url))
    if getattr(emb, "title", None):
        parts.append(str(emb.title))
    if getattr(emb, "description", None):
        parts.append(str(emb.description))
    for f in getattr(emb, "fields", []) or []:
        if getattr(f, "name", None):
            parts.append(str(f.name))
        if getattr(f, "value", None):
            parts.append(str(f.value))
    footer = getattr(emb, "footer", None)
    if footer and getattr(footer, "text", None):
        parts.append(str(footer.text))
    author = getattr(emb, "author", None)
    if author:
        if getattr(author, "name", None):
            parts.append(str(author.name))
        if getattr(author, "url", None):
            parts.append(str(author.url))
    return "\n".join(parts)

def extract_pairs_from_message(msg) -> list[tuple[int, str, str]]:
    """
    Returns list of (owner_user_id, doc_id, doc_url).

    Strategy:
      1) Try per-embed “card” parsing first (multi-embed supported).
      2) If that yields nothing, fallback to parsing msg.content (handles link-preview embeds).
      3) Extra fallback: if URL only exists in embed.url, consider that too.
    """
    pairs: list[tuple[int, str, str]] = []

    embeds = getattr(msg, "embeds", []) or []

    # 1) Per-embed parsing
    for emb in embeds:
        text = flatten_embed_text(emb)
        user_ids = extract_user_ids(text)
        doc_urls = extract_doc_urls(text)
        if user_ids and doc_urls:
            owner_id = user_ids[0]
            doc_url = doc_urls[0]
            doc_id = doc_id_from_url(doc_url)
            if doc_id:
                pairs.append((owner_id, doc_id, doc_url))

    if pairs:
        return pairs

    # 2) Fallback: message content
    text = getattr(msg, "content", "") or ""

    owner_id: Optional[int] = None
    if getattr(msg, "mentions", None) and msg.mentions:
        owner_id = msg.mentions[0].id
    if owner_id is None:
        ids = extract_user_ids(text)
        owner_id = ids[0] if ids else None

    doc_urls = extract_doc_urls(text)

    # 3) Extra fallback: embed.url (common for link-preview embeds)
    if not doc_urls:
        for emb in embeds:
            if getattr(emb, "url", None):
                doc_urls.extend(extract_doc_urls(str(emb.url)))

    if owner_id and doc_urls:
        doc_url = doc_urls[0]
        doc_id = doc_id_from_url(doc_url)
        if doc_id:
            return [(owner_id, doc_id, doc_url)]

    return []


# -----------------------------
# Hashing + diff helpers
# -----------------------------

def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()

def sha256_text(s: str) -> str:
    return sha256_bytes((s or "").encode("utf-8"))

def hash_sections(section_texts: Dict[str, str]) -> Dict[str, str]:
    return {k: sha256_text(v) for k, v in section_texts.items()}

def global_hash(section_hashes: Dict[str, str]) -> str:
    """
    Order-independent: section order changes won't alter the hash.
    """
    payload = "||".join(f"{k}:{section_hashes[k]}" for k in sorted(section_hashes.keys()))
    return sha256_text(payload)

def diff_words(old: str, new: str, max_chars: int = 3500) -> str:
    d = difflib.unified_diff(
        (old or "").split(),
        (new or "").split(),
        fromfile="approved",
        tofile="current",
        lineterm=""
    )
    out = "\n".join(d)
    if len(out) > max_chars:
        return out[:max_chars] + "\n... (diff truncated)"
    return out

def diff_words(old: str, new: str, max_chars: int = 3500, max_changed_words: int = 120) -> str:
    old_words = (old or "").split()
    new_words = (new or "").split()

    sm = difflib.SequenceMatcher(None, old_words, new_words)

    lines: List[str] = []
    changed_word_count = 0

    def take(words: List[str], remaining: int) -> List[str]:
        return words[:max(0, remaining)]

    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op == "equal":
            continue

        removed = old_words[i1:i2] if op in ("delete", "replace") else []
        added   = new_words[j1:j2] if op in ("insert", "replace") else []

        remaining = max_changed_words - changed_word_count
        if remaining <= 0:
            break

        rem_take = take(removed, remaining)
        remaining -= len(rem_take)
        add_take = take(added, remaining)

        # Each change region becomes 1-2 lines:
        # - ... (red)
        # + ... (green)
        if rem_take:
            lines.append("- " + " ".join(rem_take))
            changed_word_count += len(rem_take)
        if add_take:
            lines.append("+ " + " ".join(add_take))
            changed_word_count += len(add_take)

        # stop if we couldn't fully include this region
        if len(rem_take) < len(removed) or len(add_take) < len(added):
            break

    body = "\n".join(lines) or "No changes."

    # Wrap in diff code block for coloring
    out = "```diff\n" + body + "\n```"

    if len(out) > max_chars:
        # Keep header/footer intact
        budget = max_chars - len("```diff\n\n```") - 5
        trimmed_body = body[:max(0, budget)].rstrip() + "\n..."
        out = "```diff\n" + trimmed_body + "\n```"

    if changed_word_count >= max_changed_words:
        out += f"\n(truncated at {max_changed_words} changed words)"

    return out



# -----------------------------
# Markdown cleanup (images/nav/tables)
# -----------------------------

# Inline image: ![alt](url)
MD_IMAGE_INLINE_RE = re.compile(r"!\[[^\]]*]\(([^)]+)\)")
# Ref image: ![alt][ref]
MD_IMAGE_REF_RE = re.compile(r"!\[[^\]]*]\[[^\]]+]")
# Image definition: [ref]: <data:image/png;base64,...>  OR [ref]: data:image...
MD_IMAGE_DEF_DATA_RE = re.compile(
    r"^\[[^\]]+]:\s*(?:<)?data:image/[^>\s]+(?:>)?\s*$",
    re.IGNORECASE | re.MULTILINE
)

# Generic data: URLs (sometimes appear not as image defs)
MD_DATA_IMAGE_ANYWHERE_RE = re.compile(r"data:image/[a-zA-Z0-9.+-]+;base64,[A-Za-z0-9+/=\s]+")

# “Nav bar” line heuristic: your exports often contain long runs of links/markers.
# We keep this heuristic conservative; you can tune it later.
MD_LINK_RE = re.compile(r"\[[^\]]+]\([^)]+\)")
MD_NAV_LIKELY_RE = re.compile(r"^\s*(?:✦|•|-|\*)?\s*(?:\[[^\]]+]\([^)]+\)\s*){3,}.*$")

# Markdown table row (starts and ends with |, or has multiple pipes)
MD_TABLE_ROW_RE = re.compile(r"^\s*\|.*\|\s*$")
# Markdown table separator row like: | :--- | ---: |
MD_TABLE_SEP_RE = re.compile(r"^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$")


def strip_images(md: str) -> str:
    """
    Remove all images and base64 blobs from Markdown.
    """
    md = md or ""
    md = MD_IMAGE_INLINE_RE.sub("", md)
    md = MD_IMAGE_REF_RE.sub("", md)
    md = MD_IMAGE_DEF_DATA_RE.sub("", md)
    md = MD_DATA_IMAGE_ANYWHERE_RE.sub("", md)
    return md

def strip_nav_bars(md: str) -> str:
    """
    Remove “link bar” / navigation junk lines that are mostly repeated links.
    """
    out_lines: List[str] = []
    for line in (md or "").splitlines():
        # If the line looks like 3+ markdown links in one line, treat as nav.
        if MD_NAV_LIKELY_RE.match(line):
            continue
        out_lines.append(line)
    return "\n".join(out_lines)

def flatten_tables(md: str) -> str:
    """
    Flatten markdown tables by removing pipes and separator rows.
    Keeps cell content so edits remain detectable, but layout noise is reduced.
    """
    out_lines: List[str] = []
    for line in (md or "").splitlines():
        if MD_TABLE_SEP_RE.match(line):
            continue
        if MD_TABLE_ROW_RE.match(line):
            # Convert pipes into spaces; collapse multiple spaces later.
            line = line.replace("|", " ")
        out_lines.append(line)
    return "\n".join(out_lines)


# -----------------------------
# Normalization (Markdown-oriented)
# -----------------------------

def normalize_markdown(text: str) -> str:
    """
    Produce a stable, hash-friendly text representation.

    - Unicode normalization
    - newline normalization
    - strip BOM / zero-width chars
    - normalize bullets/quotes/dashes
    - strip images + base64
    - strip nav bars
    - flatten tables
    - collapse excessive blank lines
    """
    text = text or ""

    text = unicodedata.normalize("NFKC", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # Strip BOM + zero-width chars
    text = text.lstrip("\ufeff")
    text = re.sub(r"[\u200b-\u200f\uFEFF]", "", text)

    # Normalize bullets/dashes/quotes (helps stable diffs)
    text = text.replace("•", "-").replace("–", "-").replace("—", "-")
    text = text.replace("“", '"').replace("”", '"').replace("’", "'").replace("‘", "'")

    # Strip images/nav/tables (order matters: images first)
    text = strip_images(text)
    text = strip_nav_bars(text)
    text = flatten_tables(text)

    # Strip trailing whitespace per line
    text = "\n".join(line.rstrip() for line in text.split("\n"))

    # Collapse excessive blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)

    # Collapse excessive spaces (but keep newlines)
    text = re.sub(r"[ \t]{2,}", " ", text)

    return text.strip()


# -----------------------------
# Section parsing (Markdown headings)
# -----------------------------

MD_HEADING_RE = re.compile(r"^(?P<hashes>#{1,6})\s+(?P<title>.+?)\s*$")

def norm_key(title: str) -> str:
    """
    Normalizes a section title into a stable key:
    - collapses whitespace
    - casefolds (Unicode-safe)
    """
    t = " ".join((title or "").strip().split())
    return t.casefold()

def parse_sections_markdown(md: str) -> Dict[str, Dict[str, str]]:
    """
    Parses Markdown into flexible sections using headings.

    Returns:
      {
        "<normalized_key>": {"title": "<Original Title>", "text": "<Section body>"},
        ...
      }

    Behavior:
    - Uses ANY markdown heading (#..######) as a section boundary.
    - Merges repeated headings by appending text with a separator.
    - Ignores content before the first heading (often export header noise).
    """
    lines = (md or "").split("\n")

    # Find first heading
    start = None
    for i, line in enumerate(lines):
        if MD_HEADING_RE.match(line):
            start = i
            break
    if start is None:
        return {"__full__": {"title": "__full__", "text": (md or "").strip()}}

    lines = lines[start:]

    sections: Dict[str, Dict[str, str]] = {}
    buf: List[str] = []
    current_key: Optional[str] = None
    current_title: Optional[str] = None

    def flush() -> None:
        nonlocal buf, current_key, current_title
        if current_key is None:
            buf = []
            return
        chunk = "\n".join(buf).strip()
        buf = []
        if not chunk:
            return

        if current_key in sections:
            sections[current_key]["text"] += "\n\n---\n\n" + chunk
        else:
            sections[current_key] = {"title": current_title or current_key, "text": chunk}

    for line in lines:
        m = MD_HEADING_RE.match(line)
        if m:
            flush()
            current_title = m.group("title").strip()
            current_key = norm_key(current_title)
            continue

        buf.append(line)

    flush()
    return sections

def sections_to_texts(sections: Dict[str, Dict[str, str]]) -> Dict[str, str]:
    return {k: (sections[k].get("text") or "") for k in sections}


# Convenience: keep old name normalize_text for your existing imports
normalize_text = normalize_markdown

# Convenience: keep old name parse_sections for your existing imports
# (now Markdown-first)
parse_sections = parse_sections_markdown
