from __future__ import annotations

from collections import Counter
from typing import Any

from trello_metrics.domain.workflow import WorkflowConfig
from trello_metrics.metrics.aggregators.common import (
    calendar_person_for_timeline,
    is_high_priority,
    priority_rank,
    ratio,
    time_stats,
)
from trello_metrics.metrics.timeline import CardTimeline
from trello_metrics.utils.business_hours import duration_hours
from trello_metrics.utils.period import MonthPeriod


def aggregate_priority_metrics(
    timelines: list[CardTimeline],
    period: MonthPeriod,
    aging_rows: list[dict[str, Any]],
    workflow: WorkflowConfig,
) -> dict[str, Any]:
    active = [timeline for timeline in timelines if timeline.is_active_in(period)]
    delivered = [timeline for timeline in timelines if timeline.is_delivered_in(period)]
    distribution = Counter(timeline.prioridade for timeline in active)
    high_count = sum(count for priority, count in distribution.items() if is_high_priority(priority))

    lead_by_priority: dict[str, list[float]] = {}
    for timeline in delivered:
        priority = timeline.prioridade or "Nao informado"
        if timeline.created_at and timeline.delivered_at:
            lead_by_priority.setdefault(priority, []).append(
                duration_hours(
                    timeline.created_at,
                    timeline.delivered_at,
                    workflow,
                    person=calendar_person_for_timeline(timeline),
                )
            )

    queue_jumps = _queue_jumps(delivered)
    urgent_aging = [
        row
        for row in aging_rows
        if is_high_priority(row.get("prioridade")) and row.get("status") != "ok"
    ]

    return {
        "lead_time_by_priority": [
            {"priority": priority, **time_stats(values)}
            for priority, values in sorted(
                lead_by_priority.items(),
                key=lambda item: priority_rank(item[0]),
            )
        ],
        "distribution": [
            {"priority": priority, "count": count}
            for priority, count in distribution.most_common()
        ],
        "urgent_critical_pct": ratio(high_count, sum(distribution.values())),
        "priority_inflation_alert": ratio(high_count, sum(distribution.values())) > 20,
        "queue_jumps_count": len(queue_jumps),
        "queue_jumps": queue_jumps[:20],
        "urgent_aging_count": len(urgent_aging),
        "urgent_aging": urgent_aging[:20],
    }


def _queue_jumps(delivered: list[CardTimeline]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for lower in delivered:
        if not lower.created_at or not lower.delivered_at:
            continue
        lower_rank = priority_rank(lower.prioridade)
        for higher in delivered:
            if lower.card_id == higher.card_id:
                continue
            if not higher.created_at or not higher.delivered_at:
                continue
            if lower_rank <= priority_rank(higher.prioridade):
                continue
            if lower.created_at > higher.created_at and lower.delivered_at < higher.delivered_at:
                rows.append(
                    {
                        "delivered_first": {
                            "card_id": lower.card_id,
                            "card_name": lower.card_name,
                            "priority": lower.prioridade,
                            "created_at": lower.created_at.isoformat(),
                            "delivered_at": lower.delivered_at.isoformat(),
                        },
                        "higher_priority_waited": {
                            "card_id": higher.card_id,
                            "card_name": higher.card_name,
                            "priority": higher.prioridade,
                            "created_at": higher.created_at.isoformat(),
                            "delivered_at": higher.delivered_at.isoformat(),
                        },
                    }
                )
                break
    rows.sort(
        key=lambda item: (
            priority_rank(item["higher_priority_waited"]["priority"]),
            item["higher_priority_waited"]["created_at"],
        )
    )
    return rows
