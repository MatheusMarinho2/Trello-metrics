from __future__ import annotations

from copy import deepcopy
from typing import Any

from trello_metrics.metrics.aggregators.collaborators import collaborator_identity

METRIC_KEY_BUNDLES: dict[str, set[str]] = {
    "team_summary": {"team_summary", "board", "period", "overview"},
    "flow": {"flow"},
    "developers": {"developers", "developer_profiles"},
    "testers": {"testers"},
    "requesters": {"requesters"},
    "sla": {"sla"},
    "bottlenecks": {"bottlenecks"},
    "card_dossier": {"card_dossier"},
    "priority": {"priority"},
    "quality_gates": {"quality_gates"},
    "discipline": {"process_discipline"},
    "analysis_workflow": {"analysis_workflow"},
    "fibonacci": {"fibonacci_points"},
    "collaborators": {"collaborators"},
    "reviewers": {"reviewers"},
    "formal_reviewers": {"formal_reviewers"},
    "projects": {"projects", "project_profiles", "systems"},
    "risk": {"risk_board"},
    "trends": {"trends_6m"},
    "antifraud": {"antifraud"},
    "dora": {"dora"},
    "first_time_right": {"first_time_right"},
    "member_assignment": {"member_assignment"},
    "board_moves": {"board_moves"},
}

REPORT_TYPE_PRESETS: dict[str, set[str] | None] = {
    "general": None,
    "management": {
        "board",
        "period",
        "overview",
        "team_summary",
        "flow",
        "priority",
        "dora",
        "process_discipline",
        "analysis_workflow",
        "quality_gates",
        "projects",
        "sla",
        "bottlenecks",
        "risk_board",
        "trends_6m",
        "antifraud",
        "card_dossier",
        "first_time_right",
        "member_assignment",
        "board_moves",
    },
    "developers": {
        "board",
        "period",
        "overview",
        "team_summary",
        "developers",
        "developer_profiles",
        "flow",
        "fibonacci_points",
        "sla",
        "quality_gates",
        "card_dossier",
    },
    "requesters": {
        "board",
        "period",
        "overview",
        "requesters",
        "projects",
        "card_dossier",
    },
    "testers": {
        "board",
        "period",
        "overview",
        "testers",
        "quality_gates",
        "card_dossier",
    },
    "reviewers": {
        "board",
        "period",
        "overview",
        "reviewers",
        "quality_gates",
        "card_dossier",
    },
    "formal_reviewers": {
        "board",
        "period",
        "overview",
        "formal_reviewers",
        "quality_gates",
        "card_dossier",
    },
    "individual": {
        "board",
        "period",
        "overview",
        "collaborators",
        "card_dossier",
    },
    "by_system": {
        "board",
        "period",
        "overview",
        "project_summary",
        "team_summary",
        "flow",
        "priority",
        "dora",
        "process_discipline",
        "analysis_workflow",
        "quality_gates",
        "projects",
        "sla",
        "bottlenecks",
        "risk_board",
        "trends_6m",
        "antifraud",
        "collaborators",
        "developers",
        "requesters",
        "testers",
        "card_dossier",
        "fibonacci_points",
        "systems",
        "sistema_filter",
    },
}

ROLE_REPORT_SCOPES = {
    "developers": "developers",
    "requesters": "requesters",
    "testers": "testers",
    "reviewers": "reviewers",
    "formal_reviewers": "formal_reviewers",
}


def metric_keys_for_report_type(report_type: str, metric_keys: list[str] | None = None) -> set[str] | None:
    if report_type == "specific_metrics":
        if not metric_keys:
            return set(METRIC_KEY_BUNDLES["team_summary"])
        selected: set[str] = set()
        for key in metric_keys:
            selected.update(METRIC_KEY_BUNDLES.get(key, {key}))
        selected.update({"board", "period"})
        return selected
    return REPORT_TYPE_PRESETS.get(report_type)


def filter_metrics(
    metrics: dict[str, Any],
    *,
    report_type: str,
    metric_keys: list[str] | None = None,
    collaborator_name: str | None = None,
    ai_analysis: str | None = None,
) -> dict[str, Any]:
    allowed = metric_keys_for_report_type(report_type, metric_keys)
    filtered = _pick_keys(metrics, allowed)
    filtered["report_type"] = report_type
    if report_type == "specific_metrics" and metric_keys:
        filtered["metric_keys"] = list(metric_keys)

    if report_type == "individual" and collaborator_name:
        _apply_individual_filter(filtered, metrics, collaborator_name)
    elif report_type in ROLE_REPORT_SCOPES:
        _apply_role_filter(filtered, metrics, ROLE_REPORT_SCOPES[report_type])
    elif report_type == "specific_metrics" and metric_keys:
        _trim_card_dossier_for_metrics(filtered, metric_keys)
        for role_scope in ("developers", "testers", "requesters"):
            if role_scope in metric_keys:
                _apply_role_filter(filtered, metrics, role_scope)

    if ai_analysis:
        filtered["ai_analysis"] = ai_analysis
    return filtered


def _pick_keys(metrics: dict[str, Any], allowed: set[str] | None) -> dict[str, Any]:
    if allowed is None:
        return deepcopy(metrics)
    return {key: deepcopy(value) for key, value in metrics.items() if key in allowed}


def _apply_individual_filter(
    filtered: dict[str, Any],
    full_metrics: dict[str, Any],
    collaborator_name: str,
) -> None:
    collaborators = full_metrics.get("collaborators") or []
    identity = collaborator_identity(collaborator_name)
    if identity is None:
        filtered["collaborators"] = []
        filtered["individual_summary"] = {"name": collaborator_name, "cards_active": 0}
        filtered["card_dossier"] = {"cards": []}
        return

    key, display_name = identity
    match = next(
        (
            item
            for item in collaborators
            if collaborator_identity(item.get("name", "")) == (key, display_name)
            or key == normalize_collaborator_key(item.get("name", ""))
        ),
        None,
    )
    if not match:
        filtered["collaborators"] = []
        filtered["individual_summary"] = {"name": display_name, "cards_active": 0}
        filtered["card_dossier"] = {"cards": []}
        return

    filtered["collaborators"] = [match]
    summary = match.get("summary") or {}
    filtered["individual_summary"] = {
        "name": match.get("name", display_name),
        "cards_delivered": summary.get("cards_delivered", 0),
        "cards_active": summary.get("cards_active", 0),
        "fibonacci_total": summary.get("fibonacci_total", 0),
        "time_human": summary.get("time_human", "-"),
    }
    filtered["role_metrics"] = match.get("role_metrics") or []
    cards = match.get("cards") or []
    filtered["card_dossier"] = {"cards": cards}


def _apply_role_filter(
    filtered: dict[str, Any],
    full_metrics: dict[str, Any],
    scope: str,
) -> None:
    rows_key = scope
    rows = full_metrics.get(rows_key) or []
    filtered[rows_key] = rows
    filtered["role_summary"] = _build_role_summary(scope, rows, full_metrics)


def _build_role_summary(
    scope: str,
    rows: list[dict[str, Any]],
    full_metrics: dict[str, Any],
) -> dict[str, Any]:
    people_count = len(rows)
    if scope == "developers":
        delivered = sum(int(row.get("cards_delivered", 0)) for row in rows)
        rework = sum(int(row.get("cards_with_rework", 0)) for row in rows)
        rework_rate = round(100 * rework / delivered, 1) if delivered else 0.0
        return {
            "scope": scope,
            "people_count": people_count,
            "cards_delivered": delivered,
            "quality_rate_pct": round(100 - rework_rate, 1) if delivered else 0.0,
            "rework_rate_pct": rework_rate,
        }
    if scope == "testers":
        tested = sum(int(row.get("cards_tested", 0)) for row in rows)
        first_pass = sum(int(row.get("approved_first_pass", 0)) for row in rows)
        retests = sum(int(row.get("retest_cycles_total", 0)) for row in rows)
        return {
            "scope": scope,
            "people_count": people_count,
            "cards_tested": tested,
            "approved_first_pass": first_pass,
            "retest_cycles_total": retests,
        }
    if scope == "requesters":
        created = sum(int(row.get("cards_created", 0)) for row in rows)
        delivered = sum(int(row.get("cards_delivered", 0)) for row in rows)
        in_production = sum(int(row.get("in_production", 0)) for row in rows)
        gestor_premature = sum(int(row.get("gestor_premature_approvals", 0)) for row in rows)
        return {
            "scope": scope,
            "people_count": people_count,
            "cards_created": created,
            "cards_delivered": delivered,
            "in_production": in_production,
            "gestor_premature_approvals": gestor_premature,
        }
    if scope == "reviewers":
        reviews = sum(int(row.get("reviews_done", 0)) for row in rows)
        suggestions = sum(int(row.get("suggestions_accepted", row.get("sent_back", 0))) for row in rows)
        approved = sum(int(row.get("approved", 0)) for row in rows)
        escapes = sum(int(row.get("escaped_to_test", 0)) for row in rows)
        return {
            "scope": scope,
            "people_count": people_count,
            "reviews_done": reviews,
            "suggestions_accepted": suggestions,
            "approved": approved,
            "escaped_to_test": escapes,
            "approval_rate_pct": round(100 * approved / reviews, 1) if reviews else 0.0,
        }
    if scope == "formal_reviewers":
        reviews = sum(int(row.get("formal_reviews_done", 0)) for row in rows)
        passed = sum(int(row.get("formal_review_passed", 0)) for row in rows)
        returns = sum(int(row.get("review_return_events", 0)) for row in rows)
        escapes = sum(int(row.get("escaped_to_test", 0)) for row in rows)
        return {
            "scope": scope,
            "people_count": people_count,
            "formal_reviews_done": reviews,
            "formal_review_passed": passed,
            "review_return_events": returns,
            "escaped_to_test": escapes,
            "approval_rate_pct": round(100 * passed / reviews, 1) if reviews else 0.0,
        }
    team = full_metrics.get("team_summary") or {}
    return {"scope": scope, "people_count": people_count, **team}


def _trim_card_dossier_for_metrics(filtered: dict[str, Any], metric_keys: list[str]) -> None:
    if "card_dossier" not in metric_keys:
        filtered.pop("card_dossier", None)


def normalize_collaborator_key(name: str) -> str:
    identity = collaborator_identity(name)
    return identity[0] if identity else ""
