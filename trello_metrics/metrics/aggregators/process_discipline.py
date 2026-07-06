from __future__ import annotations

from collections import Counter
from typing import Any

from trello_metrics.domain.models import CustomFieldChange
from trello_metrics.domain.workflow import WorkflowConfig
from trello_metrics.metrics.aggregators.common import ratio, time_stats
from trello_metrics.metrics.timeline import CardTimeline
from trello_metrics.utils.dates import hours_between, isoformat
from trello_metrics.utils.period import MonthPeriod
from trello_metrics.utils.text import normalize_key


CANONICAL_ORDER = [
    "planning",
    "approval",
    "backlog",
    "development",
    "peer_review",
    "review",
    "waiting_deploy",
    "waiting_test",
    "testing",
    "waiting_production",
    "production",
]

OPTIONAL_GROUPS = {"approval", "backlog", "review"}
EXCEPTION_GROUPS = {"return_support", "return_developer", "paused"}
TERMINAL_GROUPS = frozenset({"production", "direct_production", "analysis_done"})
POST_TERMINAL_RETURN_GROUPS = frozenset({"return_developer", "return_support"})
DIRECT_PRODUCTION_WORK_ORIGINS = frozenset({"development", "peer_review", "review"})
DIRECT_PRODUCTION_SKIPPED_GROUPS = frozenset(
    {"waiting_deploy", "waiting_test", "testing", "waiting_production"}
)

REQUIRED_FIELDS_BY_STAGE = {
    "development": ("Desenvolvedor", "Sistema", "Prioridade", "Nivel", "Solicitante"),
    "peer_review": ("Desenvolvedor", "Revisor em Par"),
    "review": ("Revisor",),
    "waiting_test": ("Tester",),
    "testing": ("Tester",),
}


def aggregate_process_discipline(
    timelines: list[CardTimeline],
    field_changes: list[CustomFieldChange],
    workflow: WorkflowConfig,
    period: MonthPeriod,
) -> dict[str, Any]:
    active = [timeline for timeline in timelines if timeline.is_active_in(period)]
    delivered = [timeline for timeline in timelines if timeline.is_delivered_in(period)]
    flow_checks = [_flow_check(timeline, workflow) for timeline in delivered]
    compliant = [item for item in flow_checks if item["is_compliant"]]
    skipped = _skipped_stage_summary(flow_checks, workflow)
    post_terminal = _post_terminal_return_summary(timelines)

    return {
        "canonical_flow": [
            {"group": group, "title": workflow.title_for_group(group), "optional": group in OPTIONAL_GROUPS}
            for group in CANONICAL_ORDER
        ],
        "flow_conformity": {
            "cards_evaluated": len(flow_checks),
            "compliant_count": len(compliant),
            "compliance_pct": ratio(len(compliant), len(flow_checks)),
            "violations": [item for item in flow_checks if not item["is_compliant"]][:30],
        },
        "skipped_stages": skipped,
        "required_fields_by_stage": _required_fields_by_stage(active, workflow),
        "cards_without_level": _cards_without_level(active),
        "developer_assignment_latency": _developer_assignment_latency(
            timelines,
            field_changes,
        ),
        "post_terminal_returns": post_terminal,
    }


def _raw_groups(timeline: CardTimeline) -> list[str]:
    groups: list[str] = []
    for stage in timeline.stage_timeline:
        if groups and groups[-1] == stage.group:
            continue
        groups.append(stage.group)
    return groups


def _flow_check(timeline: CardTimeline, workflow: WorkflowConfig) -> dict[str, Any]:
    groups = _compact_groups(timeline)
    raw = _raw_groups(timeline)
    normalized = ["production" if group == "direct_production" else group for group in groups]
    used_direct_production = "direct_production" in raw
    positions = {group: index for index, group in enumerate(CANONICAL_ORDER)}
    issues: list[str] = []
    illegal_backtracks: list[dict[str, Any]] = []
    last_pos = -1
    for group in normalized:
        if group in EXCEPTION_GROUPS or group not in positions:
            continue
        pos = positions[group]
        if pos < last_pos:
            issue = f"retrocesso para {workflow.title_for_group(group)}"
            issues.append(issue)
            illegal_backtracks.append({"group": group, "title": workflow.title_for_group(group)})
        last_pos = max(last_pos, pos)

    missing_core = []
    if timeline.kind == "problem":
        test_stages = ("waiting_deploy", "waiting_test", "testing")

        if used_direct_production:
            if not DIRECT_PRODUCTION_WORK_ORIGINS.intersection(normalized):
                missing_core.append("development")
                issues.append(
                    "producao direta sem passar por Em andamento, Revisao em par ou Em revisao"
                )
        else:
            for group in ("development", *test_stages):
                if group not in normalized:
                    missing_core.append(group)
                    issues.append(f"pulou {workflow.title_for_group(group)}")

            has_production_terminal = bool({"waiting_production", "production"} & set(normalized))
            if not has_production_terminal:
                missing_core.append("waiting_production")
                issues.append(f"pulou {workflow.title_for_group('waiting_production')}")

    if timeline.return_after_terminal:
        issues.append(
            "retorno apos terminal de entrega — deve abrir novo card (producao/analise finalizada)"
        )

    return {
        "card_id": timeline.card_id,
        "card_name": timeline.card_name,
        "kind": timeline.kind,
        "desenvolvedor": timeline.desenvolvedor,
        "sistema": timeline.sistema,
        "sequence": [workflow.title_for_group(group) for group in groups],
        "missing_core_groups": missing_core,
        "illegal_backtracks": illegal_backtracks,
        "return_after_terminal": timeline.return_after_terminal,
        "used_direct_production": used_direct_production,
        "issues": issues,
        "is_compliant": not issues,
    }


def _post_terminal_return_summary(timelines: list[CardTimeline]) -> dict[str, Any]:
    rows = [
        {
            "card_id": timeline.card_id,
            "card_name": timeline.card_name,
            "kind": timeline.kind,
            "desenvolvedor": timeline.desenvolvedor,
            "sistema": timeline.sistema,
            "terminal_group": timeline.terminal_group,
            "terminal_at": isoformat(timeline.terminal_reached_at),
            "events": timeline.return_after_terminal_events[:5],
        }
        for timeline in timelines
        if timeline.return_after_terminal
    ]
    return {
        "count": len(rows),
        "note": (
            "Apos Em producao, Diretamente na producao ou Analises finalizadas o card nao "
            "deve voltar a RETORNO — abrir novo card se o problema persistir."
        ),
        "cards": rows[:30],
    }


def _compact_groups(timeline: CardTimeline) -> list[str]:
    groups: list[str] = []
    for stage in timeline.stage_timeline:
        group = stage.group
        if group in TERMINAL_GROUPS:
            group = "production" if group in {"production", "direct_production"} else group
        if groups and groups[-1] == group:
            continue
        groups.append(group)
        if group in {"production", "analysis_done"}:
            break
    return groups


def _skipped_stage_summary(
    flow_checks: list[dict[str, Any]],
    workflow: WorkflowConfig,
) -> list[dict[str, Any]]:
    skipped: dict[str, list[dict[str, str]]] = {group: [] for group in CANONICAL_ORDER}
    for check in flow_checks:
        normalized_seen = set()
        for title in check["sequence"]:
            for group in CANONICAL_ORDER:
                if workflow.title_for_group(group) == title:
                    normalized_seen.add(group)
        if "production" in normalized_seen:
            normalized_seen.add("waiting_production")
        used_direct = check.get("used_direct_production")
        for group in CANONICAL_ORDER:
            if group not in normalized_seen:
                if used_direct and group in DIRECT_PRODUCTION_SKIPPED_GROUPS:
                    continue
                skipped[group].append(
                    {
                        "card_id": check["card_id"],
                        "card_name": check["card_name"],
                    }
                )

    rows = []
    for group, cards in skipped.items():
        if not cards:
            continue
        rows.append(
            {
                "group": group,
                "title": workflow.title_for_group(group),
                "optional": group in OPTIONAL_GROUPS,
                "count": len(cards),
                "cards": cards[:20],
            }
        )
    rows.sort(key=lambda item: (item["optional"], -item["count"], item["title"]))
    return rows


def _required_fields_by_stage(
    timelines: list[CardTimeline],
    workflow: WorkflowConfig,
) -> list[dict[str, Any]]:
    rows = []
    for group, fields in REQUIRED_FIELDS_BY_STAGE.items():
        reached = [
            timeline
            for timeline in timelines
            if any(stage.group == group for stage in timeline.stage_timeline)
        ]
        missing_rows = []
        for timeline in reached:
            missing = [field for field in fields if not _has_required_field(timeline, field)]
            if missing:
                missing_rows.append(
                    {
                        "card_id": timeline.card_id,
                        "card_name": timeline.card_name,
                        "missing": missing,
                    }
                )
        rows.append(
            {
                "group": group,
                "title": workflow.title_for_group(group),
                "cards_evaluated": len(reached),
                "complete_count": len(reached) - len(missing_rows),
                "completion_pct": ratio(len(reached) - len(missing_rows), len(reached)),
                "missing": missing_rows[:30],
            }
        )
    return rows


def _has_required_field(timeline: CardTimeline, field: str) -> bool:
    key = normalize_key(field)
    if key == "DESENVOLVEDOR":
        return bool(timeline.desenvolvedor and timeline.desenvolvedor != "Nao informado")
    if key == "SISTEMA":
        return bool(timeline.sistema and timeline.sistema != "Nao informado")
    if key == "PRIORIDADE":
        return bool(timeline.prioridade and timeline.prioridade != "Nao informado")
    if key == "NIVEL":
        return timeline.fibonacci_level is not None
    if key == "SOLICITANTE":
        return bool(timeline.solicitante and timeline.solicitante != "Nao informado")
    if key == "REVISOR EM PAR":
        return bool(timeline.revisor_par and timeline.revisor_par != "Nao informado")
    if key == "REVISOR":
        return bool(timeline.revisor and timeline.revisor != "Nao informado")
    if key == "TESTER":
        return bool(timeline.tester and timeline.tester != "Nao informado")
    return True


def _cards_without_level(timelines: list[CardTimeline]) -> list[dict[str, Any]]:
    rows = []
    for timeline in timelines:
        if timeline.fibonacci_level is not None:
            continue
        rows.append(
            {
                "card_id": timeline.card_id,
                "card_name": timeline.card_name,
                "kind": timeline.kind,
                "desenvolvedor": timeline.desenvolvedor,
                "sistema": timeline.sistema,
            }
        )
    return rows


def _developer_assignment_latency(
    timelines: list[CardTimeline],
    field_changes: list[CustomFieldChange],
) -> dict[str, Any]:
    created_by_id = {
        timeline.card_id: timeline.created_at for timeline in timelines if timeline.created_at
    }
    first_assignment: dict[str, CustomFieldChange] = {}
    for change in field_changes:
        if normalize_key(change.field_name) != "DESENVOLVEDOR":
            continue
        if not change.new_value:
            continue
        if change.card_id not in first_assignment or change.at < first_assignment[change.card_id].at:
            first_assignment[change.card_id] = change

    values = []
    rows = []
    for card_id, change in first_assignment.items():
        created_at = created_by_id.get(card_id)
        if not created_at:
            continue
        hours = hours_between(created_at, change.at)
        values.append(hours)
        rows.append(
            {
                "card_id": card_id,
                "card_name": change.card_name,
                "developer": change.new_value,
                "created_at": isoformat(created_at),
                "assigned_at": isoformat(change.at),
                "latency_hours": round(hours, 2),
            }
        )
    rows.sort(key=lambda item: item["latency_hours"], reverse=True)
    return {
        **time_stats(values),
        "cards": rows[:30],
        "history_events": len(field_changes),
        "developer_assignment_events": len(first_assignment),
    }
