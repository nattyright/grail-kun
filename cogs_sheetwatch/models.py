from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

@dataclass
class Snapshot:
    sections_text: Dict[str, str]
    sections_hash: Dict[str, str]
    global_hash: str

@dataclass
class CompareResult:
    changed: bool
    changed_sections: List[str]
    diffs: Dict[str, str]
    from_hashes: Dict[str, str]
    to_hashes: Dict[str, str]
    current_section_hashes: Dict[str, str]
    current_global_hash: str
