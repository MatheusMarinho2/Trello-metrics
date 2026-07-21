from __future__ import annotations

from datetime import datetime
from typing import Any

from trello_metrics.domain.models import TrelloCard
from trello_metrics.domain.workflow import WorkflowConfig
from trello_metrics.metrics.aggregators.bottlenecks import aggregate_bottlenecks
from trello_metrics.metrics.aggregators.common import time_stats
from trello_metrics.metrics.aggregators.flow import TERMINAL_GROUPS, aggregate_flow_metrics
from trello_metrics.metrics.timeline import CardTimeline
from trello_metrics.utils.period import MonthPeriod
from trello_metrics.utils.text import clean_spaces, strip_accents


def normalize_sistema(value: str | None) -> str:
    return strip_accents(clean_spaces(value)).casefold()


def list_systems(timelines: list[CardTimeline]) -> list[str]:
    names = {
        timeline.sistema
        for timeline in timelines
        if timeline.sistema and timeline.sistema != "Nao informado"
    }
    return sorted(names, key=lambda name: name.casefold())


def filter_by_sistema(
    timelines: list[CardTimeline],
    cards: list[TrelloCard],
    sistema: str,
) -> tuple[list[CardTimeline], list[TrelloCard]]:
    target = normalize_sistema(sistema)
    timeline_by_id = {
        timeline.card_id: timeline
        for timeline in timelines
        if normalize_sistema(timeline.sistema) == target
    }
    filtered_cards = [card for card in cards if card.id in timeline_by_id]
    filtered_timelines = [timeline_by_id[card.id] for card in filtered_cards]
    return filtered_timelines, filtered_cards


def _period_snapshot(
    timelines: list[CardTimeline],
    cards: list[TrelloCard],
    workflow: WorkflowConfig,
    period: MonthPeriod,
    now: datetime,
) -> dict[str, Any]:
    delivered = [timeline for timeline in timelines if timeline.is_delivered_in(period)]
    archived = [timeline for timeline in timelines if period.contains(timeline.archived_at)]
    flow = aggregate_flow_metrics(timelines, cards, workflow, period, now)
    team = flow.get("team") or {}
    lead = team.get("lead_time") or {}
    bottlenecks = aggregate_bottlenecks(timelines, cards, workflow, period)

    fibonacci_normal = sum(
        timeline.fibonacci_level or 0
        for timeline in delivered
        if timeline.kind == "problem"
    )
    fibonacci_analysis = sum(
        timeline.fibonacci_level or 0
        for timeline in delivered
        if timeline.kind == "analysis"
    )
    cards_with_rework = sum(1 for timeline in delivered if timeline.developer_penalty_return_count)
    rework_rate_pct = round(100 * cards_with_rework / len(delivered), 1) if delivered else 0.0

    return {
        "month": period.label,
        "cards_delivered": len(delivered),
        "cards_created": sum(1 for timeline in timelines if timeline.is_created_in(period)),
        "cards_archived": len(archived),
        "wip_total": team.get("wip_total", 0),
        "fibonacci_normal": fibonacci_normal,
        "fibonacci_analysis": fibonacci_analysis,
        "fibonacci_total": fibonacci_normal + fibonacci_analysis,
        "lead_time_avg_human": lead.get("avg_human", "-"),
        "lead_time_p50_human": lead.get("p50_human", "-"),
        "rework_rate_pct": rework_rate_pct,
        "quality_rate_pct": round(100 - rework_rate_pct, 1) if delivered else 0.0,
        "top_bottleneck": bottlenecks.get("top_bottleneck"),
    }


def _delta(current: float | int, previous: float | int) -> dict[str, Any]:
    curr = float(current or 0)
    prev = float(previous or 0)
    absolute = round(curr - prev, 1)
    pct = round(100 * absolute / prev, 1) if prev else None
    return {"current": curr, "previous": prev, "delta": absolute, "delta_pct": pct}


def aggregate_project_summary(
    timelines: list[CardTimeline],
    cards: list[TrelloCard],
    workflow: WorkflowConfig,
    period: MonthPeriod,
    now: datetime,
    sistema: str,
    previous_period: MonthPeriod | None = None,
) -> dict[str, Any]:
    current = _period_snapshot(timelines, cards, workflow, period, now)
    previous = (
        _period_snapshot(timelines, cards, workflow, previous_period, now)
        if previous_period
        else None
    )

    comparison: dict[str, Any] = {}
    if previous:
        for key in (
            "cards_delivered",
            "cards_archived",
            "wip_total",
            "fibonacci_total",
            "rework_rate_pct",
        ):
            comparison[key] = _delta(current.get(key, 0), previous.get(key, 0))

    open_non_terminal = 0
    for timeline in timelines:
        if not timeline.is_open:
            continue
        current_group = None
        for stage in reversed(timeline.stage_timeline or []):
            if stage.end_at is None:
                current_group = stage.group
                break
        if current_group and current_group not in TERMINAL_GROUPS:
            open_non_terminal += 1

    lead_values = [
        timeline.lead_time_hours
        for timeline in timelines
        if timeline.is_delivered_in(period) and timeline.lead_time_hours is not None
    ]

    return {
        "name": sistema,
        "month": period.label,
        "previous_month": previous_period.label if previous_period else None,
        "cards_delivered": current["cards_delivered"],
        "cards_created": current["cards_created"],
        "cards_archived": current["cards_archived"],
        "wip_total": current["wip_total"],
        "wip_open_non_terminal": open_non_terminal,
        "fibonacci_normal": current["fibonacci_normal"],
        "fibonacci_analysis": current["fibonacci_analysis"],
        "fibonacci_total": current["fibonacci_total"],
        "lead_time": time_stats(lead_values),
        "rework_rate_pct": current["rework_rate_pct"],
        "quality_rate_pct": current["quality_rate_pct"],
        "top_bottleneck": current["top_bottleneck"],
        "previous": previous,
        "comparison": comparison,
    }


def aggregate_project_profiles(
    timelines: list[CardTimeline],
    cards: list[TrelloCard],
    workflow: WorkflowConfig,
    period: MonthPeriod,
    now: datetime,
    timezone_name: str = "America/Sao_Paulo",
) -> list[dict[str, Any]]:
    """Perfil consolidado de cada sistema: entrega, WIP, SLA, gargalos e fluxo."""
    from trello_metrics.metrics.aggregators.developers import aggregate_developers
    from trello_metrics.metrics.aggregators.sla import aggregate_sla

    profiles: list[dict[str, Any]] = []
    for sistema in list_systems(timelines):
        scoped_timelines, scoped_cards = filter_by_sistema(timelines, cards, sistema)
        if not scoped_timelines:
            continue
        summary = aggregate_project_summary(
            scoped_timelines,
            scoped_cards,
            workflow,
            period,
            now,
            sistema,
        )
        flow = aggregate_flow_metrics(
            scoped_timelines, scoped_cards, workflow, period, now
        )
        bottlenecks = aggregate_bottlenecks(
            scoped_timelines, scoped_cards, workflow, period
        )
        sla = aggregate_sla(
            scoped_timelines,
            scoped_cards,
            workflow,
            period,
            now,
            timezone_name,
        )
        developers = aggregate_developers(scoped_timelines, period, workflow)
        top_dev = developers[0]["name"] if developers else None
        sla_team = sla.get("team") or {}
        flow_team = flow.get("team") or {}

        profiles.append(
            {
                **summary,
                "top_developer": top_dev,
                "developers": developers[:8],
                "sla": {
                    "compliance_pct": sla_team.get("compliance_pct", 0),
                    "breached_count": sla_team.get("breached_count", 0),
                    "cards_evaluated": sla_team.get("cards_evaluated", 0),
                    "stage_checks": sla_team.get("stage_checks", 0),
                    "current_at_risk_count": sla_team.get("current_at_risk_count", 0),
                    "current_breached_count": sla_team.get("current_breached_count", 0),
                    "by_stage": (sla.get("by_stage") or [])[:12],
                },
                "flow": {
                    "wip_total": flow_team.get("wip_total", summary.get("wip_total", 0)),
                    "lead_time": flow_team.get("lead_time") or summary.get("lead_time") or {},
                    "cycle_time": flow_team.get("cycle_time") or {},
                    "wip_by_stage": flow.get("wip_by_stage") or [],
                },
                "bottlenecks": {
                    "top_bottleneck": bottlenecks.get("top_bottleneck"),
                    "by_stage": (bottlenecks.get("by_stage") or [])[:10],
                },
            }
        )

    profiles.sort(
        key=lambda row: (
            row.get("fibonacci_total", 0),
            row.get("cards_delivered", 0),
            row.get("wip_total", 0),
        ),
        reverse=True,
    )
    return profiles


def projects_rows_from_profiles(profiles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for profile in profiles:
        top_bn = profile.get("top_bottleneck") or (profile.get("bottlenecks") or {}).get(
            "top_bottleneck"
        )
        sla = profile.get("sla") or {}
        lead = (profile.get("flow") or {}).get("lead_time") or profile.get("lead_time") or {}
        rows.append(
            {
                "name": profile.get("name"),
                "cards_delivered": profile.get("cards_delivered", 0),
                "cards_created": profile.get("cards_created", 0),
                "cards_archived": profile.get("cards_archived", 0),
                "wip_total": profile.get("wip_total", 0),
                "fibonacci_normal": profile.get("fibonacci_normal", 0),
                "fibonacci_analysis": profile.get("fibonacci_analysis", 0),
                "fibonacci_total": profile.get("fibonacci_total", 0),
                "top_developer": profile.get("top_developer"),
                "rework_rate_pct": profile.get("rework_rate_pct", 0),
                "quality_rate_pct": profile.get("quality_rate_pct", 0),
                "sla_compliance_pct": sla.get("compliance_pct", 0),
                "sla_breached_count": sla.get("breached_count", 0),
                "lead_time_avg_human": lead.get("avg_human", "-"),
                "top_bottleneck": (top_bn or {}).get("title")
                or (top_bn or {}).get("group")
                or "-",
            }
        )
    return rows
