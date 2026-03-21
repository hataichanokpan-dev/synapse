"""
Guard helpers for spotting obviously corrupted text payloads.
"""

from __future__ import annotations

import re
from typing import Any, Mapping

_THAI_BLOCK_START = ord("\u0E00")
_THAI_BLOCK_END = ord("\u0E7F")
_QMARK_RUN_RE = re.compile(r"\?{4,}")


def _contains_thai(text: str) -> bool:
    return any(_THAI_BLOCK_START <= ord(char) <= _THAI_BLOCK_END for char in text)


def looks_like_corrupted_text(value: str) -> bool:
    """Heuristically detect question-mark corruption from non-UTF-8 clients."""
    text = str(value or "").strip()
    if not text or _contains_thai(text):
        return False

    non_space_chars = [char for char in text if not char.isspace()]
    if not non_space_chars:
        return False

    qmark_count = sum(char == "?" for char in non_space_chars)
    if qmark_count < 6:
        return False

    qmark_ratio = qmark_count / len(non_space_chars)
    return qmark_ratio >= 0.35 or bool(_QMARK_RUN_RE.search(text))


def find_corrupted_text_fields(fields: Mapping[str, Any]) -> list[str]:
    """Return field names whose string payloads look irreversibly corrupted."""
    suspicious: list[str] = []
    for field_name, value in fields.items():
        if value is None:
            continue
        if isinstance(value, str) and looks_like_corrupted_text(value):
            suspicious.append(field_name)
            continue
        if isinstance(value, (list, tuple, set)) and any(
            isinstance(item, str) and looks_like_corrupted_text(item) for item in value
        ):
            suspicious.append(field_name)
    return suspicious
