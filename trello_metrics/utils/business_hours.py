from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from trello_metrics.domain.workflow import WorkflowConfig
from trello_metrics.utils.dates import hours_between
from trello_metrics.utils.work_calendar import WorkCalendar


def duration_hours(
    start: datetime | None,
    end: datetime | None,
    workflow: WorkflowConfig | None,
    *,
    calendar: bool = False,
    person: str | None = None,
    work_calendar: WorkCalendar | None = None,
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
    cal = work_calendar if work_calendar is not None else getattr(workflow, "work_calendar", None)
    person_name = person if person is not None else getattr(workflow, "duration_person", None)
    return business_hours_between(
        start,
        end,
        rules,
        timezone_name,
        work_calendar=cal,
        person=person_name,
    )


def business_hours_between(
    start: datetime,
    end: datetime,
    sla_rules: dict[str, Any],
    timezone_name: str,
    *,
    work_calendar: WorkCalendar | None = None,
    person: str | None = None,
) -> float:
    if end <= start:
        return 0.0

    business = sla_rules.get("business_hours", {})
    tz = ZoneInfo(str(sla_rules.get("timezone") or timezone_name))
    start_local = start.astimezone(tz)
    end_local = end.astimezone(tz)
    weekdays = set(int(day) for day in business.get("weekdays", [0, 1, 2, 3, 4]))

    cal = work_calendar or WorkCalendar.from_dict(
        {
            "holidays": sla_rules.get("holidays") or [],
            "exceptions": sla_rules.get("calendar_exceptions") or [],
            "overtime": sla_rules.get("overtime") or [],
        }
    )
    holiday_days = set(cal.holidays_for(person))
    if sla_rules.get("holidays"):
        for value in sla_rules["holidays"]:
            holiday_days.add(date.fromisoformat(str(value)[:10]))

    total_seconds = 0.0
    current_day = start_local.date()
    last_day = end_local.date()
    while current_day <= last_day:
        for window_start, window_end in _countable_windows_for_day(
            current_day,
            business,
            tz,
            weekdays,
            cal,
            person,
            holiday_days,
        ):
            overlap_start = max(start_local, window_start)
            overlap_end = min(end_local, window_end)
            if overlap_end > overlap_start:
                total_seconds += (overlap_end - overlap_start).total_seconds()
        current_day += timedelta(days=1)

    return round(total_seconds / 3600, 6)


def _countable_windows_for_day(
    day: date,
    business: dict[str, Any],
    tz: ZoneInfo,
    weekdays: set[int],
    calendar: WorkCalendar,
    person: str | None,
    holiday_days: set[date],
) -> list[tuple[datetime, datetime]]:
    if day in holiday_days:
        windows: list[tuple[datetime, datetime]] = []
    else:
        day_exceptions = calendar.exceptions_on(day, person)
        override = next((item for item in day_exceptions if item.kind == "schedule_override"), None)
        if override and override.start_time and override.end_time:
            windows = _windows_from_range(day, override.start_time, override.end_time, business, tz)
        elif day.weekday() in weekdays:
            windows = _business_windows_for_day(day, business, tz)
        else:
            windows = []

        for item in day_exceptions:
            if item.kind != "exclude_window" or not item.start_time or not item.end_time:
                continue
            exclude_start = datetime.combine(day, item.start_time, tzinfo=tz)
            exclude_end = datetime.combine(day, item.end_time, tzinfo=tz)
            windows = _subtract_window(windows, exclude_start, exclude_end)

    for ot in calendar.overtime_on(day, person):
        ot_start = datetime.combine(day, ot.start_time, tzinfo=tz)
        ot_end = datetime.combine(day, ot.end_time, tzinfo=tz)
        if ot_end > ot_start:
            windows.append((ot_start, ot_end))

    return _merge_windows(windows)


def _windows_from_range(
    day: date,
    start_t: time,
    end_t: time,
    business: dict[str, Any],
    tz: ZoneInfo,
) -> list[tuple[datetime, datetime]]:
    day_start = datetime.combine(day, start_t, tzinfo=tz)
    day_end = datetime.combine(day, end_t, tzinfo=tz)
    if day_end <= day_start:
        return []

    lunch = business.get("lunch_break")
    if not isinstance(lunch, dict):
        return [(day_start, day_end)]

    lunch_start = datetime.combine(day, _parse_time(lunch.get("start"), time(12, 0)), tzinfo=tz)
    lunch_end = datetime.combine(day, _parse_time(lunch.get("end"), time(13, 0)), tzinfo=tz)
    windows: list[tuple[datetime, datetime]] = []
    morning_end = min(lunch_start, day_end)
    if morning_end > day_start:
        windows.append((day_start, morning_end))
    afternoon_start = max(lunch_end, day_start)
    if day_end > afternoon_start:
        windows.append((afternoon_start, day_end))
    return windows


def _business_windows_for_day(
    day: date,
    business: dict[str, Any],
    tz: ZoneInfo,
) -> list[tuple[datetime, datetime]]:
    day_start_time = _parse_time(business.get("start"), time(8, 0))
    day_end_time = _resolve_day_end(day.weekday(), business)
    return _windows_from_range(day, day_start_time, day_end_time, business, tz)


def _subtract_window(
    windows: list[tuple[datetime, datetime]],
    exclude_start: datetime,
    exclude_end: datetime,
) -> list[tuple[datetime, datetime]]:
    result: list[tuple[datetime, datetime]] = []
    for start, end in windows:
        if exclude_end <= start or exclude_start >= end:
            result.append((start, end))
            continue
        if exclude_start > start:
            result.append((start, exclude_start))
        if exclude_end < end:
            result.append((exclude_end, end))
    return result


def _merge_windows(
    windows: list[tuple[datetime, datetime]],
) -> list[tuple[datetime, datetime]]:
    if not windows:
        return []
    ordered = sorted(windows, key=lambda item: item[0])
    merged: list[tuple[datetime, datetime]] = [ordered[0]]
    for start, end in ordered[1:]:
        last_start, last_end = merged[-1]
        if start <= last_end:
            merged[-1] = (last_start, max(last_end, end))
        else:
            merged.append((start, end))
    return merged


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
