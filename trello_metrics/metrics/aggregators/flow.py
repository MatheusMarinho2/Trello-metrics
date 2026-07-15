from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, time, timedelta, timezone
from typing import Any

from trello_metrics.domain.models import TrelloCard
from trello_metrics.domain.workflow import WorkflowConfig
from trello_metrics.metrics.aggregators.common import (
    calendar_person_for_timeline,
    first_stage_start,
    percentile,
    ratio,
    stage_duration_until,
    time_stats,
    week_key,
)
from trello_metrics.metrics.timeline import CardTimeline, StageTimelineEntry
from trello_metrics.utils.business_hours import duration_hours
from trello_metrics.utils.dates import human_hours, isoformat
from trello_metrics.utils.period import MonthPeriod


QUEUE_GROUPS = {
    "approval",
    "backlog",
    "backlog_analysis",
    "waiting_peer_review",
    "review_control",
    "waiting_review",
    "waiting_deploy",
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
        duration_hours(
            timeline.created_at,
            timeline.delivered_at,
            workflow,
            person=calendar_person_for_timeline(timeline),
        )
        for timeline in delivered
        if timeline.created_at and timeline.delivered_at
    ]
    cycle_values = [
        timeline.metric_cycle_hours
        for timeline in delivered
        if timeline.metric_cycle_hours is not None
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
            hours = stage_duration_until(
                stage,
                cap,
                workflow,
                person=calendar_person_for_timeline(timeline, stage.group),
            )
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
            "flow_efficiency_distribution": _flow_efficiency_distribution(delivered, workflow),
            "rework_ratio": _rework_ratio(delivered),
            "blocked_time": _blocked_time(delivered, workflow),
            "wip_total": len(open_cards),
            "little_law_predicted_lead_time_days": little_days,
            "little_law": {
                "wip": len(open_cards),
                "throughput_per_day": round(throughput_per_day, 4),
                "predicted_lead_time_days": little_days,
            },
        },
        "note": (
            "Horas em expediente INTGEST (seg-qua 8-18, qui-sex 8-17:30, almoco 12-13) "
            "+ calendario operacional (feriados, meio periodo, exclusoes, HE do responsavel). "
            "Cycle time oficial = metric_cycle_hours (fim do pre_flow ate entrega). "
            "Eficiencia de fluxo trata planejamento como trabalho (WORK_GROUPS)."
        ),
        "aging_baseline": _aging_baseline(timelines, workflow, period),
        "net_flow": _net_flow(timelines, period),
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
                historical[stage.group].append(stage.hours)

    card_by_id = {card.id: card for card in cards}
    rows: list[dict[str, Any]] = []
    for timeline in timelines:
        card = card_by_id.get(timeline.card_id)
        if not card or card.closed:
            continue
        current = _current_non_terminal_stage(timeline)
        if not current:
            continue
        age = duration_hours(
            current.start_at,
            now,
            workflow,
            person=calendar_person_for_timeline(timeline, current.group),
        )
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
    person = calendar_person_for_timeline(timeline, current.group) if timeline and current else None
    age = (
        duration_hours(current.start_at, now, workflow, person=person)
        if current
        else 0.0
    )
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
                if previous.hours > 0:
                    values.append(previous.hours)
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
    return percentile(values, pct)


TOUCH_GROUPS = {"development", "peer_review", "review", "testing", "return_developer"}
BLOCKED_GROUPS = {"paused", "return_support"}


def _flow_efficiency_distribution(
    delivered: list[CardTimeline],
    workflow: WorkflowConfig,
) -> dict[str, Any]:
    values: list[float] = []
    worst: list[dict[str, Any]] = []
    for timeline in delivered:
        total = timeline.flow_hours_until_delivery
        if total <= 0:
            continue
        touch = 0.0
        for stage in timeline.stage_timeline:
            if stage.group in TOUCH_GROUPS:
                touch += stage_duration_until(
                    stage,
                    timeline.delivered_at,
                    workflow,
                    person=calendar_person_for_timeline(timeline, stage.group),
                )
        eff = round(100 * touch / total, 1)
        values.append(eff)
        worst.append(
            {
                "card_name": timeline.card_name,
                "desenvolvedor": timeline.desenvolvedor,
                "efficiency_pct": eff,
                "touch_hours": round(touch, 2),
                "total_hours": round(total, 2),
            }
        )
    worst.sort(key=lambda row: row["efficiency_pct"])
    return {
        **time_stats(values),
        "worst_cards": worst[:10],
    }


def _rework_ratio(delivered: list[CardTimeline]) -> dict[str, Any]:
    rework_total = 0.0
    flow_total = 0.0
    ratios: list[float] = []
    top: list[dict[str, Any]] = []
    for timeline in delivered:
        flow_h = timeline.flow_hours_until_delivery
        if flow_h <= 0:
            continue
        rework_h = max(
            0.0,
            timeline.group_hours.get("return_developer", 0.0) - timeline.undue_return_hours,
        )
        rework_total += rework_h
        flow_total += flow_h
        ratio_pct = round(100 * rework_h / flow_h, 1)
        ratios.append(ratio_pct)
        top.append(
            {
                "card_name": timeline.card_name,
                "desenvolvedor": timeline.desenvolvedor,
                "rework_hours": round(rework_h, 2),
                "ratio_pct": ratio_pct,
            }
        )
    top.sort(key=lambda row: row["rework_hours"], reverse=True)
    return {
        "team_rework_ratio_pct": (
            round(100 * rework_total / flow_total, 1) if flow_total > 0 else None
        ),
        "card_ratio_stats": time_stats(ratios),
        "top_cards": top[:10],
    }


def _blocked_time(
    delivered: list[CardTimeline],
    workflow: WorkflowConfig,
) -> dict[str, Any]:
    ratios: list[float] = []
    top: list[dict[str, Any]] = []
    by_week: dict[str, list[float]] = defaultdict(list)
    for timeline in delivered:
        flow_h = timeline.flow_hours_until_delivery
        if flow_h <= 0:
            continue
        blocked = 0.0
        for stage in timeline.stage_timeline:
            if stage.group in BLOCKED_GROUPS:
                blocked += stage_duration_until(
                    stage,
                    timeline.delivered_at,
                    workflow,
                    person=calendar_person_for_timeline(timeline, stage.group),
                )
        ratio_pct = round(100 * blocked / flow_h, 1)
        ratios.append(ratio_pct)
        top.append(
            {
                "card_name": timeline.card_name,
                "desenvolvedor": timeline.desenvolvedor,
                "blocked_hours": round(blocked, 2),
                "ratio_pct": ratio_pct,
            }
        )
        by_week[week_key(timeline.delivered_at)].append(ratio_pct)
    top.sort(key=lambda row: row["blocked_hours"], reverse=True)
    return {
        **time_stats(ratios),
        "top_cards": top[:10],
        "by_week": [
            {"week": week, "avg_ratio_pct": round(sum(vals) / len(vals), 1), "samples": len(vals)}
            for week, vals in sorted(by_week.items())
        ],
    }


def _aging_baseline(
    timelines: list[CardTimeline],
    workflow: WorkflowConfig,
    period: MonthPeriod,
) -> list[dict[str, Any]]:
    window_start = period.start - timedelta(days=365)
    hist: dict[str, list[float]] = defaultdict(list)
    for timeline in timelines:
        for stage in timeline.stage_timeline:
            if stage.group in TERMINAL_GROUPS or stage.end_at is None or not stage.start_at:
                continue
            if stage.start_at < window_start:
                continue
            hist[stage.group].append(stage.hours)
    rows = []
    for group, values in sorted(hist.items()):
        rows.append(
            {
                "group": group,
                "title": workflow.title_for_group(group),
                "samples": len(values),
                "p50_hours": percentile(values, 50),
                "p85_hours": percentile(values, 85),
                "p95_hours": percentile(values, 95),
                "p50_human": human_hours(percentile(values, 50) or 0),
                "p85_human": human_hours(percentile(values, 85) or 0),
                "p95_human": human_hours(percentile(values, 95) or 0),
                "insufficient_data": len(values) < 10,
            }
        )
    return rows


def _net_flow(timelines: list[CardTimeline], period: MonthPeriod) -> dict[str, Any]:
    lookback_start = period.start - timedelta(days=84)
    weeks: dict[str, dict[str, int]] = defaultdict(lambda: {"arrivals": 0, "departures": 0})
    for timeline in timelines:
        if timeline.created_at and timeline.created_at >= lookback_start:
            weeks[week_key(timeline.created_at)]["arrivals"] += 1
        if timeline.delivered_at and timeline.delivered_at >= lookback_start:
            weeks[week_key(timeline.delivered_at)]["departures"] += 1

    series = []
    wip = 0
    nets: list[int] = []
    for week in sorted(weeks):
        row = weeks[week]
        net = row["arrivals"] - row["departures"]
        wip += net
        nets.append(net)
        series.append(
            {
                "week": week,
                "arrivals": row["arrivals"],
                "departures": row["departures"],
                "net": net,
                "wip_cumulative": wip,
            }
        )
    recent = nets[-4:] if nets else []
    avg_net = round(sum(recent) / len(recent), 2) if recent else 0.0
    return {
        "series": series,
        "avg_net_last_4_weeks": avg_net,
        "alert_wip_rising": avg_net > 0,
    }
