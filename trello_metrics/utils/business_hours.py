from __future__ import annotations

from datetime import datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from trello_metrics.domain.workflow import WorkflowConfig
from trello_metrics.utils.dates import hours_between


def duration_hours(
    start: datetime | None,
    end: datetime | None,
    workflow: WorkflowConfig | None,
    *,
    calendar: bool = False,
) -> float:
    if not start or not end:
        return 0.0
    if calendar or workflow is None:
        return hours_between(start, end)

    rules = workflow.sla_rules()
    business = rules.get("business_hours")
    if not business:
        return hours_between(start, end)

    timezone_name = str(rules.get("timezone", "America/Sao_Paulo"))
    return business_hours_between(start, end, rules, timezone_name)


def business_hours_between(
    start: datetime,
    end: datetime,
    sla_rules: dict[str, Any],
    timezone_name: str,
) -> float:
    if end <= start:
        return 0.0

    business = sla_rules.get("business_hours", {})
    tz = ZoneInfo(str(sla_rules.get("timezone") or timezone_name))
    start_local = start.astimezone(tz)
    end_local = end.astimezone(tz)
    weekdays = set(int(day) for day in business.get("weekdays", [0, 1, 2, 3, 4]))

    total_seconds = 0.0
    current_day = start_local.date()
    last_day = end_local.date()
    while current_day <= last_day:
        if current_day.weekday() in weekdays:
            for window_start, window_end in _business_windows_for_day(current_day, business, tz):
                overlap_start = max(start_local, window_start)
                overlap_end = min(end_local, window_end)
                if overlap_end > overlap_start:
                    total_seconds += (overlap_end - overlap_start).total_seconds()
        current_day += timedelta(days=1)

    return round(total_seconds / 3600, 6)


def _business_windows_for_day(
    day: datetime.date,
    business: dict[str, Any],
    tz: ZoneInfo,
) -> list[tuple[datetime, datetime]]:
    day_start_time = _parse_time(business.get("start"), time(8, 0))
    day_end_time = _resolve_day_end(day.weekday(), business)
    day_start = datetime.combine(day, day_start_time, tzinfo=tz)
    day_end = datetime.combine(day, day_end_time, tzinfo=tz)
    if day_end <= day_start:
        return []

    lunch = business.get("lunch_break")
    if not isinstance(lunch, dict):
        return [(day_start, day_end)]

    lunch_start_time = _parse_time(lunch.get("start"), time(12, 0))
    lunch_end_time = _parse_time(lunch.get("end"), time(13, 0))
    lunch_start = datetime.combine(day, lunch_start_time, tzinfo=tz)
    lunch_end = datetime.combine(day, lunch_end_time, tzinfo=tz)

    windows: list[tuple[datetime, datetime]] = []
    morning_end = min(lunch_start, day_end)
    if morning_end > day_start:
        windows.append((day_start, morning_end))

    afternoon_start = max(lunch_end, day_start)
    if day_end > afternoon_start:
        windows.append((afternoon_start, day_end))

    return windows


def _resolve_day_end(weekday: int, business: dict[str, Any]) -> time:
    schedules = business.get("weekday_schedules")
    if isinstance(schedules, list):
        for item in schedules:
            if not isinstance(item, dict):
                continue
            days = {int(day) for day in item.get("weekdays", [])}
            if weekday in days:
                return _parse_time(item.get("end"), time(18, 0))

    return _parse_time(business.get("end"), time(18, 0))


def _parse_time(value: object, default: time) -> time:
    if not value:
        return default
    try:
        hour, minute = str(value).split(":", 1)
        return time(int(hour), int(minute))
    except (TypeError, ValueError):
        return default
