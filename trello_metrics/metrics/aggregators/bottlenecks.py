from __future__ import annotations

import statistics
from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any

from trello_metrics.domain.models import TrelloCard
from trello_metrics.domain.workflow import WorkflowConfig
from trello_metrics.metrics.timeline import CardTimeline
from trello_metrics.utils.dates import human_hours
from trello_metrics.utils.period import MonthPeriod


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = int(round((pct / 100) * (len(ordered) - 1)))
    return round(ordered[index], 2)


def aggregate_bottlenecks(
    timelines: list[CardTimeline],
    cards: list[TrelloCard],
    workflow: WorkflowConfig,
    period: MonthPeriod,
) -> dict[str, Any]:
    group_values: dict[str, list[float]] = {
        group: [] for group in workflow.bottleneck_groups()
    }

    for timeline in timelines:
        if not timeline.is_delivered_in(period):
            continue
        for group in workflow.bottleneck_groups():
            hours = timeline.group_hours.get(group, 0.0)
            if hours > 0:
                group_values[group].append(hours)

    rows = []
    for group in workflow.bottleneck_groups():
        values = group_values[group]
        avg = round(statistics.mean(values), 2) if values else 0.0
        median = round(statistics.median(values), 2) if values else 0.0
        p95 = _percentile(values, 95)
        rows.append(
            {
                "group": group,
                "title": workflow.title_for_group(group),
                "avg_hours": avg,
                "avg_human": human_hours(avg),
                "median_hours": median,
                "p95_hours": p95,
                "samples": len(values),
            }
        )

    rows.sort(key=lambda row: row["avg_hours"], reverse=True)
    top = rows[0] if rows and rows[0]["avg_hours"] > 0 else None

    now = datetime.now(timezone.utc)
    stuck_now = []
    for card in cards:
        group = workflow.group_for_list(card.current_list_name)
        if group in workflow.bottleneck_groups():
            days_stuck = 0.0
            if card.date_last_activity:
                days_stuck = round((now - card.date_last_activity).total_seconds() / 86400, 1)
            stuck_now.append(
                {
                    "card": card.name,
                    "list": card.current_list_name,
                    "group": workflow.title_for_group(group),
                    "responsavel": card.custom_fields.get(
                        workflow.attribution_field_for_group(group) or "", "Nao informado"
                    ),
                    "days_stuck": days_stuck,
                }
            )
    stuck_now.sort(key=lambda item: item["days_stuck"], reverse=True)

    by_sistema = _bottlenecks_by_sistema(timelines, workflow, period)
    management_view = _management_only_view(cards, workflow)

    return {
        "by_stage": rows,
        "top_bottleneck": top,
        "stuck_now_count": len(stuck_now),
        "stuck_now": stuck_now[:20],
        "by_sistema": by_sistema,
        "management_only_view": management_view,
    }


def _bottlenecks_by_sistema(
    timelines: list[CardTimeline],
    workflow: WorkflowConfig,
    period: MonthPeriod,
) -> list[dict[str, Any]]:
    """Cruza tempo de gargalo com o campo personalizado Sistema, para saber
    em qual sistema/projeto os cards mais travam nas etapas de espera."""
    values_by_sistema: dict[str, list[float]] = defaultdict(list)
    for timeline in timelines:
        if not timeline.is_delivered_in(period):
            continue
        total_bottleneck_hours = sum(
            timeline.group_hours.get(group, 0.0) for group in workflow.bottleneck_groups()
        )
        if total_bottleneck_hours > 0:
            values_by_sistema[timeline.sistema].append(total_bottleneck_hours)

    rows = []
    for sistema, values in values_by_sistema.items():
        rows.append(
            {
                "sistema": sistema,
                "avg_hours": round(statistics.mean(values), 2),
                "avg_human": human_hours(round(statistics.mean(values), 2)),
                "samples": len(values),
            }
        )
    rows.sort(key=lambda row: row["avg_hours"], reverse=True)
    return rows


def _management_only_view(
    cards: list[TrelloCard],
    workflow: WorkflowConfig,
) -> dict[str, list[dict[str, Any]]]:
    """Contagem de cards por lista especifica (por projeto/canal) dentro de
    'aguardando teste' e 'aguardando producao'. E so visao gerencial: as
    metricas de gargalo usam o grupo fundido, nao a lista especifica."""
    management_lists = workflow.management_only_lists()
    result: dict[str, list[dict[str, Any]]] = {}
    for group, list_names in management_lists.items():
        counter: Counter[str] = Counter()
        normalized_names = {name for name in list_names}
        for card in cards:
            if card.current_list_name in normalized_names:
                counter[card.current_list_name] += 1
        result[group] = [
            {"list": name, "count": counter.get(name, 0)} for name in list_names
        ]
    return result
