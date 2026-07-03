from __future__ import annotations

from datetime import datetime, timezone


def parse_trello_datetime(value: object) -> datetime | None:
    if not value:
        return None
    text = str(value)
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def trello_id_datetime(card_id: str | None) -> datetime | None:
    if not card_id or len(card_id) < 8:
        return None
    try:
        seconds = int(card_id[:8], 16)
    except ValueError:
        return None
    return datetime.fromtimestamp(seconds, tz=timezone.utc)


def hours_between(start: datetime | None, end: datetime | None) -> float:
    if not start or not end:
        return 0.0
    seconds = max(0.0, (end - start).total_seconds())
    return round(seconds / 3600, 6)


def human_hours(hours: float) -> str:
    if hours <= 0:
        return "0 s"
    total_seconds = int(round(hours * 3600))
    if total_seconds < 60:
        return f"{total_seconds} s"
    if hours < 1:
        minutes, seconds = divmod(total_seconds, 60)
        if seconds:
            return f"{minutes} min {seconds} s"
        return f"{minutes} min"
    if hours < 24:
        return f"{hours:.2f} h"
    days = hours / 24
    return f"{days:.2f} dias"


def isoformat(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
