from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time
from typing import Any

from trello_metrics.utils.text import normalize_key


@dataclass(frozen=True)
class CalendarException:
    day: date
    kind: str  # holiday | schedule_override | exclude_window
    start_time: time | None = None
    end_time: time | None = None
    scope: str = "all"  # all | collaborators
    people: frozenset[str] = field(default_factory=frozenset)
    note: str = ""

    def applies_to(self, person: str | None) -> bool:
        if self.scope == "all" or not self.people:
            return True
        if not person:
            return False
        person_key = normalize_key(person)
        people_keys = {normalize_key(name) for name in self.people}
        if person_key in people_keys:
            return True
        return any(
            person_key.endswith(key) or key.endswith(person_key)
            for key in people_keys
            if key
        )


@dataclass(frozen=True)
class OvertimeWindow:
    day: date
    start_time: time
    end_time: time
    person: str
    note: str = ""

    def applies_to(self, person: str | None) -> bool:
        if not person:
            return False
        person_key = normalize_key(person)
        ot_key = normalize_key(self.person)
        return person_key == ot_key or person_key.endswith(ot_key) or ot_key.endswith(person_key)


@dataclass
class WorkCalendar:
    exceptions: list[CalendarException] = field(default_factory=list)
    overtime: list[OvertimeWindow] = field(default_factory=list)
    holidays: list[date] = field(default_factory=list)

    def holidays_for(self, person: str | None) -> set[date]:
        days = set(self.holidays)
        for item in self.exceptions:
            if item.kind == "holiday" and item.applies_to(person):
                days.add(item.day)
        return days

    def exceptions_on(self, day: date, person: str | None) -> list[CalendarException]:
        return [item for item in self.exceptions if item.day == day and item.applies_to(person)]

    def overtime_on(self, day: date, person: str | None) -> list[OvertimeWindow]:
        return [item for item in self.overtime if item.day == day and item.applies_to(person)]

    def to_applied_payload(self) -> dict[str, Any]:
        return {
            "holidays": [day.isoformat() for day in sorted(self.holidays)],
            "exceptions": [
                {
                    "date": item.day.isoformat(),
                    "kind": item.kind,
                    "start": item.start_time.strftime("%H:%M") if item.start_time else None,
                    "end": item.end_time.strftime("%H:%M") if item.end_time else None,
                    "scope": item.scope,
                    "people": sorted(item.people),
                    "note": item.note,
                }
                for item in self.exceptions
            ],
            "overtime": [
                {
                    "date": item.day.isoformat(),
                    "start": item.start_time.strftime("%H:%M"),
                    "end": item.end_time.strftime("%H:%M"),
                    "person": item.person,
                    "note": item.note,
                }
                for item in self.overtime
            ],
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any] | None) -> WorkCalendar:
        if not raw:
            return cls()
        exceptions: list[CalendarException] = []
        for item in raw.get("exceptions") or []:
            if not isinstance(item, dict) or not item.get("date"):
                continue
            exceptions.append(
                CalendarException(
                    day=_parse_date(item["date"]),
                    kind=str(item.get("kind") or "holiday"),
                    start_time=_parse_time_opt(item.get("start") or item.get("start_time")),
                    end_time=_parse_time_opt(item.get("end") or item.get("end_time")),
                    scope=str(item.get("scope") or "all"),
                    people=frozenset(str(p) for p in (item.get("people") or [])),
                    note=str(item.get("note") or ""),
                )
            )
        overtime: list[OvertimeWindow] = []
        for item in raw.get("overtime") or []:
            if not isinstance(item, dict) or not item.get("date") or not item.get("person"):
                continue
            start = _parse_time_opt(item.get("start") or item.get("start_time"))
            end = _parse_time_opt(item.get("end") or item.get("end_time"))
            if not start or not end:
                continue
            overtime.append(
                OvertimeWindow(
                    day=_parse_date(item["date"]),
                    start_time=start,
                    end_time=end,
                    person=str(item["person"]),
                    note=str(item.get("note") or ""),
                )
            )
        holidays = [_parse_date(value) for value in (raw.get("holidays") or []) if value]
        return cls(exceptions=exceptions, overtime=overtime, holidays=holidays)


def _parse_date(value: object) -> date:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    return date.fromisoformat(str(value)[:10])


def _parse_time_opt(value: object) -> time | None:
    if value is None or value == "":
        return None
    if isinstance(value, time):
        return value
    try:
        hour, minute = str(value).split(":", 1)
        return time(int(hour), int(minute))
    except (TypeError, ValueError):
        return None
