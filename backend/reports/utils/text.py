from __future__ import annotations

import re
import unicodedata


def normalize_name(value: str | None) -> str:
    text = value or ""
    normalized = unicodedata.normalize("NFKD", text)
    without_accents = "".join(char for char in normalized if not unicodedata.combining(char))
    return re.sub(r"\s+", " ", without_accents).strip().casefold()


def title_or_fallback(value: str | None, fallback: str) -> str:
    return (value or "").strip() or fallback
