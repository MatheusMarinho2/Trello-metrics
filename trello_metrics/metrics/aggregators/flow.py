from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, time, timedelta, timezone
from typing import Any

from trello_metrics.domain.models import TrelloCard
from trello_metrics.domain.workflow import WorkflowConfig
from trello_metrics.metrics.aggregators.common import (
    first_stage_start,
    ratio,
    stage_duration_until,
    time_stats,
)
from trello_metrics.metrics.timeline import CardTimeline, StageTimelineEntry
from trello_metrics.utils.dates import hours_between, human_hours, isoformat
from trello_metrics.utils.period import MonthPeriod


QUEUE_GROUPS = {
    "approval",
    "backlog",
    "backlog_analysis",
    "waiting_peer_review",
    "review_control",
    "waiting_review",
    "waiting_deploy",
    "cicd_homologacao",
    "waiting_test",
    "waiting_production",
    "paused",
    "return_support",
}

WORK_GROUPS = {
    "analysis_planning",
    "planning",
    "development",
    "return_developer",
    "peer_review",
    "review",
    "testing",
}

TERMINAL_GROUPS = {"production", "direct_production", "analysis_done"}


def aggregate_flow_metrics(
    timelines: list[CardTimeline],
    cards: list[TrelloCard],
    workflow: WorkflowConfig,
    period: MonthPeriod,
    now: datetime,
) -> dict[str, Any]:
    delivered = [timeline for timeline in timelines if timeline.is_delivered_in(period)]
    open_cards = _open_cards(cards, workflow)
    timeline_by_id = {timeline.card_id: timeline for timeline in timelines}

    lead_values = [
        hours_between(timeline.created_at, timeline.delivered_at)
        for timeline in delivered
        if timeline.created_at and timeline.delivered_at
    ]
    cycle_values = [
        hours_between(start, timeline.delivered_at)
        for timeline in delivered
        if (start := first_stage_start(timeline, "development")) and timeline.delivered_at
    ]
    planning_to_approval = _planning_to_approval_hours(delivered)

    wait_hours = 0.0
    work_hours = 0.0
    stage_values: dict[str, list[float]] = defaultdict(list)
    for timeline in delivered:
        cap = timeline.delivered_at
        for stage in timeline.stage_timeline:
            if stage.group in TERMINAL_GROUPS:
                continue
            hours = stage_duration_until(stage, cap)
            if hours <= 0:
                continue
            stage_values[stage.group].append(hours)
            if stage.group in QUEUE_GROUPS:
                wait_hours += hours
            elif stage.group in WORK_GROUPS:
                work_hours += hours

    throughput_per_day = len(delivered) / max(1, (period.end - period.start).days)
    little_days = round(len(open_cards) / throughput_per_day, 2) if throughput_per_day else None

    return {
        "team": {
            "cards_delivered": len(delivered),
            "lead_time": time_stats(lead_values),
            "cycle_time": time_stats(cycle_values),
            "planning_to_approval_time": time_stats(planning_to_approval),
            "flow_efficiency": _flow_efficiency(wait_hours, work_hours),
            "wip_total": len(open_cards),
            "little_law_predicted_lead_time_days": little_days,
            "little_law": {
                "wip": len(open_cards),
                "throughput_per_day": round(throughput_per_day, 4),
                "predicted_lead_time_days": little_days,
            },
        },
        "stage_time": [
            {
                "group": group,
                "title": workflow.title_for_group(group),
                **time_stats(values),
            }
            for group, values in sorted(stage_values.items())
        ],
        "wip_by_stage": _wip_by_stage(open_cards, workflow),
        "aging_wip": aging_wip(timelines, cards, workflow, now),
        "cfd": cumulative_flow(timelines, workflow, period, now),
        "open_cards": [
            _open_card_row(card, workflow, timeline_by_id.get(card.id), now)
            for card in open_cards
        ],
    }


def aging_wip(
    timelines: list[CardTimeline],
    cards: list[TrelloCard],
    workflow: WorkflowConfig,
    now: datetime,
) -> list[dict[str, Any]]:
    historical: dict[str, list[float]] = defaultdict(list)
    for timeline in timelines:
        for stage in timeline.stage_timeline:
            if stage.group in TERMINAL_GROUPS:
                continue
            if stage.start_at and stage.end_at:
                historical[stage.group].append(hours_between(stage.start_at, stage.end_at))

    card_by_id = {card.id: card for card in cards}
    rows: list[dict[str, Any]] = []
    for timeline in timelines:
        card = card_by_id.get(timeline.card_id)
        if not card or card.closed:
            continue
        current = _current_non_terminal_stage(timeline)
        if not current:
            continue
        age = hours_between(current.start_at, now)
        p50 = _percentile_from(historical.get(current.group, []), 50)
        p85 = _percentile_from(historical.get(current.group, []), 85)
        status = "ok"
        if p85 is not None and age > p85:
            status = "above_p85"
        elif p50 is not None and age > p50:
            status = "above_p50"
        rows.append(
            {
                "card_id": timeline.card_id,
                "card_name": timeline.card_name,
                "id_short": card.id_short,
                "url": card.url,
                "group": current.group,
                "title": workflow.title_for_group(current.group),
                "list_name": current.list_name,
                "age_hours": round(age, 2),
                "age_human": human_hours(age),
                "p50_hours": p50,
                "p50_human": human_hours(p50 or 0),
                "p85_hours": p85,
                "p85_human": human_hours(p85 or 0),
                "status": status,
                "desenvolvedor": timeline.desenvolvedor,
                "prioridade": timeline.prioridade,
                "sistema": timeline.sistema,
                "fibonacci_level": timeline.fibonacci_level,
            }
        )
    rows.sort(key=lambda item: (item["status"] == "ok", -item["age_hours"]))
    return rows


def cumulative_flow(
    timelines: list[CardTimeline],
    workflow: WorkflowConfig,
    period: MonthPeriod,
    now: datetime,
) -> list[dict[str, Any]]:
    start_date = period.start.date()
    end = min(period.end.astimezone(timezone.utc), now.astimezone(timezone.utc))
    end_date = end.date()
    rows: list[dict[str, Any]] = []
    day = start_date
    while day <= end_date:
        local_cutoff = datetime.combine(day, time.max, tzinfo=period.start.tzinfo)
        cutoff = local_cutoff.astimezone(timezone.utc)
        counts: Counter[str] = Counter()
        for timeline in timelines:
            group = _group_at(timeline, cutoff)
            if group:
                counts[workflow.title_for_group(group)] += 1
        rows.append({"date": day.isoformat(), **dict(sorted(counts.items()))})
        day += timedelta(days=1)
    return rows


def _flow_efficiency(wait_hours: float, work_hours: float) -> dict[str, Any]:
    total = wait_hours + work_hours
    pct = ratio(work_hours, total)
    return {
        "wait_hours": round(wait_hours, 2),
        "wait_human": human_hours(wait_hours),
        "work_hours": round(work_hours, 2),
        "work_human": human_hours(work_hours),
        "total_hours": round(total, 2),
        "total_human": human_hours(total),
        "efficiency_pct": pct,
    }


def _open_cards(cards: list[TrelloCard], workflow: WorkflowConfig) -> list[TrelloCard]:
    rows = []
    for card in cards:
        group = workflow.group_for_list(card.current_list_name)
        if card.closed or group in TERMINAL_GROUPS:
            continue
        rows.append(card)
    return rows


def _wip_by_stage(cards: list[TrelloCard], workflow: WorkflowConfig) -> list[dict[str, Any]]:
    counter = Counter(workflow.group_for_list(card.current_list_name) for card in cards)
    return [
        {"group": group, "title": workflow.title_for_group(group), "count": count}
        for group, count in counter.most_common()
    ]


def _open_card_row(
    card: TrelloCard,
    workflow: WorkflowConfig,
    timeline: CardTimeline | None,
    now: datetime,
) -> dict[str, Any]:
    current = _current_non_terminal_stage(timeline) if timeline else None
    age = hours_between(current.start_at, now) if current else 0.0
    return {
        "card_id": card.id,
        "id_short": card.id_short,
        "card_name": card.name,
        "url": card.url,
        "current_group": workflow.group_for_list(card.current_list_name),
        "current_title": workflow.title_for_group(workflow.group_for_list(card.current_list_name)),
        "current_list": card.current_list_name,
        "age_hours": round(age, 2),
        "age_human": human_hours(age),
        "desenvolvedor": card.custom_fields.get("Desenvolvedor", "Nao informado"),
        "prioridade": card.custom_fields.get("Prioridade", "Nao informado"),
        "sistema": card.custom_fields.get("Sistema", "Nao informado"),
    }


def _planning_to_approval_hours(timelines: list[CardTimeline]) -> list[float]:
    values: list[float] = []
    for timeline in timelines:
        previous: StageTimelineEntry | None = None
        for stage in timeline.stage_timeline:
            if previous and previous.group == "planning" and stage.group == "approval":
                if previous.start_at and previous.end_at:
                    values.append(hours_between(previous.start_at, previous.end_at))
                break
            previous = stage
    return values


def _current_non_terminal_stage(timeline: CardTimeline | None) -> StageTimelineEntry | None:
    if not timeline:
        return None
    for stage in reversed(timeline.stage_timeline):
        if stage.group not in TERMINAL_GROUPS:
            return stage
        return None
    return None


def _group_at(timeline: CardTimeline, cutoff: datetime) -> str | None:
    if not timeline.created_at or timeline.created_at > cutoff:
        return None
    current: str | None = None
    for stage in timeline.stage_timeline:
        if stage.start_at and stage.start_at <= cutoff:
            end_at = stage.end_at
            if end_at is None or end_at > cutoff:
                return stage.group
            current = stage.group
    return current


def _percentile_from(values: list[float], pct: float) -> float | None:
    return time_stats(values)["p85_hours" if pct == 85 else "median_hours"]
