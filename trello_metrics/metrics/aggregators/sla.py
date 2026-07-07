from __future__ import annotations

import statistics
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from trello_metrics.domain.models import TrelloCard
from trello_metrics.domain.workflow import WorkflowConfig
from trello_metrics.metrics.timeline import CardTimeline, StageTimelineEntry
from trello_metrics.utils.business_hours import business_hours_between
from trello_metrics.utils.dates import hours_between, human_hours, isoformat
from trello_metrics.utils.period import MonthPeriod
from trello_metrics.utils.text import normalize_key


def aggregate_sla(
    timelines: list[CardTimeline],
    cards: list[TrelloCard],
    workflow: WorkflowConfig,
    period: MonthPeriod,
    now: datetime,
    timezone_name: str,
) -> dict[str, Any]:
    rules = workflow.sla_rules()
    if not rules:
        return {}

    checks: list[dict[str, Any]] = []
    current_alerts: list[dict[str, Any]] = []
    card_by_id = {card.id: card for card in cards}

    for timeline in timelines:
        if not timeline.is_active_in(period) and not timeline.is_delivered_in(period):
            continue

        card_checks: list[dict[str, Any]] = []
        for stage in timeline.stage_timeline:
            if not _stage_in_period_scope(timeline, stage, period):
                continue
            check = _stage_check(timeline, stage, workflow, rules, now, timezone_name)
            if check:
                card_checks.append(check)
                checks.append(check)

        card = card_by_id.get(timeline.card_id)
        if card and card_checks and not card.closed:
            current = _current_stage_check(
                timeline,
                card,
                workflow,
                rules,
                now,
                timezone_name,
            )
            if current and current["status"] in {"em_risco", "estourado"}:
                current_alerts.append(current)

    by_stage = _by_stage(checks, workflow)
    by_developer = _by_developer(checks)
    by_card = _by_card(checks)
    breached = [item for item in checks if item["breached"]]

    return {
        "policy": {
            "timezone": rules.get("timezone", timezone_name),
            "business_hours": rules.get("business_hours", {}),
            "risk_threshold_pct": float(rules.get("risk_threshold_pct", 80)),
            "note": (
                "Horas uteis usam expediente INTGEST (seg-qua 8h-18h, qui-sex 8h-17h30, "
                "almoco 12h-13h); Aguardando producao usa dias corridos; "
                "Em andamento usa nivel Fibonacci (cards problema); "
                "Analises para planejamento usa nivel de analise; "
                "Retornos usam prioridade do card."
            ),
        },
        "team": {
            "cards_evaluated": len(by_card),
            "stage_checks": len(checks),
            "breached_count": len(breached),
            "compliance_pct": _pct(len(checks) - len(breached), len(checks)),
            "current_at_risk_count": sum(1 for item in current_alerts if item["status"] == "em_risco"),
            "current_breached_count": sum(1 for item in current_alerts if item["status"] == "estourado"),
        },
        "by_stage": by_stage,
        "by_developer": by_developer,
        "cards": by_card,
        "current_alerts": sorted(
            current_alerts,
            key=lambda item: (item["status"] != "estourado", -item["usage_pct"]),
        ),
    }


def _stage_check(
    timeline: CardTimeline,
    stage: StageTimelineEntry,
    workflow: WorkflowConfig,
    rules: dict[str, Any],
    now: datetime,
    timezone_name: str,
) -> dict[str, Any] | None:
    limit, sla_basis = _sla_limit_info(timeline, stage.group, rules)
    if limit is None or limit <= 0:
        return None

    mode = _sla_mode(stage.group, rules)
    end_at = stage.end_at or now
    elapsed = _elapsed_hours(stage.start_at, end_at, mode, rules, timezone_name)
    usage_pct = round(100 * elapsed / limit, 1) if limit else 0.0
    breached = elapsed > limit
    risk_threshold = float(rules.get("risk_threshold_pct", 80))
    is_open_stage = stage.end_at is None or _same_instant(stage.end_at, now)
    status = "ok"
    if breached:
        status = "estourado"
    elif is_open_stage and usage_pct >= risk_threshold:
        status = "em_risco"

    return {
        "card_id": timeline.card_id,
        "card_name": timeline.card_name,
        "kind": timeline.kind,
        "sistema": timeline.sistema,
        "desenvolvedor": timeline.desenvolvedor,
        "fibonacci_level": timeline.fibonacci_level,
        "prioridade": timeline.prioridade,
        "sla_basis": sla_basis,
        "group": stage.group,
        "title": workflow.title_for_group(stage.group),
        "list_name": stage.list_name,
        "start_at": isoformat(stage.start_at),
        "end_at": isoformat(end_at),
        "mode": mode,
        "limit_hours": round(limit, 2),
        "limit_human": human_hours(limit),
        "elapsed_hours": round(elapsed, 2),
        "elapsed_human": human_hours(elapsed),
        "usage_pct": usage_pct,
        "breached": breached,
        "breach_hours": round(max(0.0, elapsed - limit), 2),
        "breach_human": human_hours(max(0.0, elapsed - limit)),
        "status": status,
    }


def _current_stage_check(
    timeline: CardTimeline,
    card: TrelloCard,
    workflow: WorkflowConfig,
    rules: dict[str, Any],
    now: datetime,
    timezone_name: str,
) -> dict[str, Any] | None:
    if not timeline.stage_timeline:
        return None
    stage = timeline.stage_timeline[-1]
    check = _stage_check(timeline, stage, workflow, rules, now, timezone_name)
    if not check:
        return None
    check.update(
        {
            "current_list": card.current_list_name,
            "date_last_activity": isoformat(card.date_last_activity),
            "url": card.url,
        }
    )
    return check


def _stage_in_period_scope(
    timeline: CardTimeline,
    stage: StageTimelineEntry,
    period: MonthPeriod,
) -> bool:
    if stage.start_at is None:
        return False
    if timeline.is_delivered_in(period):
        return True
    end = stage.end_at or period.end.astimezone(timezone.utc)
    period_start = period.start.astimezone(timezone.utc)
    period_end = period.end.astimezone(timezone.utc)
    return stage.start_at < period_end and end > period_start


def _sla_limit_info(
    timeline: CardTimeline,
    group: str,
    rules: dict[str, Any],
) -> tuple[float | None, str]:
    excluded = set(rules.get("excluded_groups", []))
    if group in excluded:
        return None, ""

    wip_only = set(rules.get("wip_only_groups", []))
    if group in wip_only:
        return None, ""

    analysis_groups = set(rules.get("analysis_sla_groups", ["analysis_planning"]))
    if group in analysis_groups and timeline.kind == "analysis":
        by_level = rules.get("analysis_hours_by_level", {})
        level = timeline.fibonacci_level
        if level is None:
            return None, ""
        value = by_level.get(str(level))
        if value is None:
            return None, ""
        return float(value), "analysis_level"

    if group == "development":
        if timeline.kind != "problem":
            return None, ""
        by_level = rules.get("development_hours_by_level", {})
        level = timeline.fibonacci_level
        if level is None:
            return None, ""
        value = by_level.get(str(level))
        if value is None:
            return None, ""
        return float(value), "development_level"

    return_rules = rules.get("return_hours_by_priority", {})
    if group in return_rules:
        priority_key = _priority_sla_key(timeline.prioridade)
        group_rules = return_rules[group]
        if not isinstance(group_rules, dict):
            return None, ""
        value = group_rules.get(priority_key) or group_rules.get("default")
        if value is None:
            return None, ""
        return float(value), "return_priority"

    stage_hours = rules.get("stage_hours", {})
    if group in stage_hours:
        return float(stage_hours[group]), "stage"

    calendar_hours = rules.get("stage_calendar_hours", {})
    if group in calendar_hours:
        return float(calendar_hours[group]), "stage"

    return None, ""


def _priority_sla_key(prioridade: str | None) -> str:
    key = normalize_key(prioridade)
    mapping = {
        "CRITICA": "critica",
        "URGENTE": "urgente",
        "ALTA": "alta",
    }
    return mapping.get(key, "default")


def _sla_limit_hours(
    timeline: CardTimeline,
    group: str,
    rules: dict[str, Any],
) -> float | None:
    limit, _ = _sla_limit_info(timeline, group, rules)
    return limit


def _sla_mode(group: str, rules: dict[str, Any]) -> str:
    calendar_hours = rules.get("stage_calendar_hours", {})
    if group in calendar_hours:
        return "calendar"
    return "business"


def _elapsed_hours(
    start: datetime | None,
    end: datetime | None,
    mode: str,
    rules: dict[str, Any],
    timezone_name: str,
) -> float:
    if not start or not end:
        return 0.0
    if mode == "calendar":
        return hours_between(start, end)
    return business_hours_between(start, end, rules, timezone_name)


def _by_stage(
    checks: list[dict[str, Any]],
    workflow: WorkflowConfig,
) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for check in checks:
        grouped[check["group"]].append(check)

    rows = []
    for group, items in grouped.items():
        elapsed = [float(item["elapsed_hours"]) for item in items]
        breaches = [item for item in items if item["breached"]]
        first_limit = items[0]["limit_hours"] if items else 0.0
        same_limit = all(item["limit_hours"] == first_limit for item in items)
        bases = {item.get("sla_basis") for item in items}
        if same_limit:
            sla_label = human_hours(first_limit)
        elif bases == {"development_level"} or bases == {"analysis_level"}:
            sla_label = "Por nivel"
        elif bases == {"return_priority"}:
            sla_label = "Por prioridade"
        else:
            sla_label = "Variavel"
        rows.append(
            {
                "group": group,
                "title": workflow.title_for_group(group),
                "checks": len(items),
                "breached_count": len(breaches),
                "compliance_pct": _pct(len(items) - len(breaches), len(items)),
                "sla_human": sla_label,
                "avg_elapsed_hours": round(statistics.mean(elapsed), 2) if elapsed else 0.0,
                "avg_elapsed_human": human_hours(round(statistics.mean(elapsed), 2)) if elapsed else "0 s",
                "max_breach_hours": round(max((item["breach_hours"] for item in items), default=0.0), 2),
                "max_breach_human": human_hours(max((item["breach_hours"] for item in items), default=0.0)),
            }
        )

    rows.sort(key=lambda item: (item["breached_count"], item["avg_elapsed_hours"]), reverse=True)
    return rows


def _by_developer(checks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for check in checks:
        dev = check.get("desenvolvedor") or "Nao informado"
        if not str(dev).startswith("D-"):
            continue
        grouped[str(dev)].append(check)

    rows = []
    for dev, items in grouped.items():
        card_ids = {item["card_id"] for item in items}
        breached = [item for item in items if item["breached"]]
        rows.append(
            {
                "name": dev,
                "cards_evaluated": len(card_ids),
                "stage_checks": len(items),
                "breached_count": len(breached),
                "compliance_pct": _pct(len(items) - len(breached), len(items)),
                "breached_cards": len({item["card_id"] for item in breached}),
            }
        )

    rows.sort(key=lambda item: (item["compliance_pct"], -item["breached_count"]), reverse=True)
    return rows


def _by_card(checks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for check in checks:
        grouped[check["card_id"]].append(check)

    rows = []
    for card_id, items in grouped.items():
        breached = [item for item in items if item["breached"]]
        worst = max(items, key=lambda item: item["usage_pct"])
        rows.append(
            {
                "card_id": card_id,
                "card_name": items[0]["card_name"],
                "desenvolvedor": items[0]["desenvolvedor"],
                "sistema": items[0]["sistema"],
                "fibonacci_level": items[0]["fibonacci_level"],
                "stage_checks": len(items),
                "breached_count": len(breached),
                "compliance_pct": _pct(len(items) - len(breached), len(items)),
                "worst_stage": worst["title"],
                "worst_usage_pct": worst["usage_pct"],
                "checks": items,
            }
        )

    rows.sort(key=lambda item: (item["breached_count"], item["worst_usage_pct"]), reverse=True)
    return rows


def _pct(numerator: int, denominator: int) -> float:
    return round(100 * numerator / denominator, 1) if denominator else 0.0


def _same_instant(left: datetime | None, right: datetime | None) -> bool:
    if not left or not right:
        return False
    return abs((left - right).total_seconds()) < 1
