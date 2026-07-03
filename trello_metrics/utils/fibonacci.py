from __future__ import annotations

import re

VALID_LEVELS = {1, 2, 3, 5, 8, 13}


def parse_fibonacci_level(value: object) -> int | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() in {"nao informado", "não informado", "-", "none"}:
        return None
    match = re.search(r"\d+", text)
    if not match:
        return None
    level = int(match.group())
    return level if level in VALID_LEVELS else None
