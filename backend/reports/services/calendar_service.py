from __future__ import annotations

from datetime import date

from reports.models import OvertimeEntry, WorkCalendarException
from trello_metrics.utils.work_calendar import (
    CalendarException,
    OvertimeWindow,
    WorkCalendar,
)


def load_work_calendar(
    *,
    start: date | None = None,
    end: date | None = None,
) -> WorkCalendar:
    exceptions_qs = WorkCalendarException.objects.filter(active=True).prefetch_related(
        "collaborators"
    )
    overtime_qs = OvertimeEntry.objects.filter(active=True).select_related("collaborator")
    if start is not None:
        exceptions_qs = exceptions_qs.filter(date__gte=start)
        overtime_qs = overtime_qs.filter(date__gte=start)
    if end is not None:
        exceptions_qs = exceptions_qs.filter(date__lt=end)
        overtime_qs = overtime_qs.filter(date__lt=end)

    exceptions = [
        CalendarException(
            day=item.date,
            kind=item.kind,
            start_time=item.start_time,
            end_time=item.end_time,
            scope=item.scope,
            people=frozenset(item.collaborators.values_list("name", flat=True)),
            note=item.note,
        )
        for item in exceptions_qs
    ]
    overtime = [
        OvertimeWindow(
            day=item.date,
            start_time=item.start_time,
            end_time=item.end_time,
            person=item.collaborator.name,
            note=item.note,
        )
        for item in overtime_qs
    ]
    return WorkCalendar(exceptions=exceptions, overtime=overtime)
