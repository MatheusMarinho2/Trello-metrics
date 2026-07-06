from __future__ import annotations

import json
from collections import Counter
from typing import Any

from reports.services.ai_flow_context import build_flow_column_insights
from reports.services.ai_returns_context import (
    build_returns_pauses_insights,
    highlights_for_people,
)


MAX_CONTEXT_CHARS = 120_000
COLLABORATOR_BATCH_SIZE = 6


def build_ai_context(
    filtered: dict[str, Any],
    full_metrics: dict[str, Any] | None = None,
) -> dict[str, Any]:
    full_metrics = full_metrics or filtered
    context: dict[str, Any] = {
        "board": _pick(filtered, "board") or _pick(full_metrics, "board"),
        "period": _pick(filtered, "period") or _pick(full_metrics, "period"),
        "report_type": filtered.get("report_type"),
        "individual_target": filtered.get("individual_target"),
        "overview": _pick(filtered, "overview") or _pick(full_metrics, "overview"),
    }

    for key in (
        "team_summary",
        "role_summary",
        "individual_summary",
        "role_metrics",
        "flow",
        "priority",
        "dora",
        "sla",
        "bottlenecks",
        "quality_gates",
        "process_discipline",
        "analysis_workflow",
        "risk_board",
        "fibonacci_points",
        "projects",
    ):
        value = _pick(filtered, key) or _pick(full_metrics, key)
        if value is not None:
            context[key] = _summarize_section(key, value)

    trends = _pick(full_metrics, "trends_6m")
    if trends:
        context["trends_6m"] = _summarize_trends(trends)

    collaborator_rows = (
        filtered.get("collaborators")
        or full_metrics.get("collaborators")
        or []
    )
    violations_by_dev = _violations_by_developer(context.get("process_discipline") or {})
    context["collaborators"] = _summarize_collaborators(collaborator_rows, violations_by_dev)
    context["collaborators_total"] = len(context["collaborators"])
    context["collaborators_names"] = [row["name"] for row in context["collaborators"] if row.get("name")]

    context["developers"] = _summarize_people_rows(
        filtered.get("developers") or full_metrics.get("developers") or [],
    )
    context["testers"] = _summarize_people_rows(
        filtered.get("testers") or full_metrics.get("testers") or [],
    )
    context["requesters"] = _summarize_people_rows(
        filtered.get("requesters") or full_metrics.get("requesters") or [],
    )
    context["reviewers"] = _summarize_people_rows(
        filtered.get("reviewers") or full_metrics.get("reviewers") or [],
    )

    dossier = filtered.get("card_dossier") or full_metrics.get("card_dossier")
    context["returns_pauses_insights"] = build_returns_pauses_insights(
        card_dossier=dossier if isinstance(dossier, dict) else None,
        team_summary=context.get("team_summary") or _pick(full_metrics, "team_summary"),
        quality_gates=context.get("quality_gates") or _pick(full_metrics, "quality_gates"),
    )
    context["flow_column_insights"] = build_flow_column_insights(
        flow=_pick(full_metrics, "flow"),
        bottlenecks=_pick(full_metrics, "bottlenecks"),
        sla=_pick(full_metrics, "sla"),
        process_discipline=_pick(full_metrics, "process_discipline"),
    )

    return _truncate_if_needed(context)


def to_json(context: dict[str, Any]) -> str:
    return json.dumps(context, ensure_ascii=False, indent=2)


def collaborator_names(context: dict[str, Any]) -> list[str]:
    return list(context.get("collaborators_names") or [])


def context_for_collaborator_batch(
    context: dict[str, Any],
    names: list[str],
    *,
    batch_index: int,
    batch_total: int,
) -> dict[str, Any]:
    name_set = set(names)
    rows = [
        row for row in (context.get("collaborators") or [])
        if row.get("name") in name_set
    ]
    return {
        "period": context.get("period"),
        "report_type": context.get("report_type"),
        "collaborators_total": context.get("collaborators_total"),
        "batch_index": batch_index,
        "batch_total": batch_total,
        "batch_names": names,
        "collaborators_batch": rows,
        "returns_pauses_highlights": highlights_for_people(
            context.get("returns_pauses_insights") or {},
            names,
        ),
        "questionable_returns_for_batch": [
            item
            for item in (context.get("returns_pauses_insights") or {}).get("questionable_returns") or []
            if any(
                person in names
                for person in (
                    item.get("desenvolvedor"),
                    item.get("tester"),
                    item.get("revisor_par"),
                    item.get("revisor"),
                )
                if person
            )
        ][:8],
    }


def _pick(source: dict[str, Any], key: str) -> Any:
    if key not in source:
        return None
    return source[key]


def _violations_by_developer(process_discipline: dict[str, Any]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    violations = (process_discipline.get("flow_conformity") or {}).get("violations") or []
    for item in violations:
        developer = item.get("desenvolvedor")
        if developer:
            counts[str(developer)] += 1
    return dict(counts)


def _summarize_section(key: str, value: Any) -> Any:
    if key == "flow" and isinstance(value, dict):
        team = value.get("team") or {}
        return {
            "team": {
                "lead_time": team.get("lead_time"),
                "cycle_time": team.get("cycle_time"),
                "flow_efficiency": team.get("flow_efficiency"),
                "wip_total": team.get("wip_total"),
                "little_law": team.get("little_law"),
            },
            "wip_by_stage": (value.get("wip_by_stage") or [])[:8],
            "stage_time": (value.get("stage_time") or [])[:10],
            "aging_wip": (value.get("aging_wip") or [])[:8],
        }
    if key == "sla" and isinstance(value, dict):
        return {
            "team": value.get("team"),
            "by_stage": (value.get("by_stage") or [])[:10],
            "by_developer": (value.get("by_developer") or [])[:20],
            "current_alerts": (value.get("current_alerts") or [])[:10],
        }
    if key == "bottlenecks" and isinstance(value, dict):
        return {
            "top_bottleneck": value.get("top_bottleneck"),
            "by_stage": (value.get("by_stage") or [])[:10],
            "by_sistema": (value.get("by_sistema") or [])[:8],
        }
    if key == "dora" and isinstance(value, dict):
        return {
            "note": value.get("note"),
            "deployment_frequency": value.get("deployment_frequency"),
            "change_failure_rate": {
                "failed_deployments": (value.get("change_failure_rate") or {}).get("failed_deployments"),
                "deployments_evaluated": (value.get("change_failure_rate") or {}).get("deployments_evaluated"),
                "rate_pct": (value.get("change_failure_rate") or {}).get("rate_pct"),
            },
            "lead_time_deploy": value.get("lead_time_deploy"),
        }
    if key == "process_discipline" and isinstance(value, dict):
        flow = value.get("flow_conformity") or {}
        return {
            "flow_conformity": {
                "cards_evaluated": flow.get("cards_evaluated"),
                "compliant_count": flow.get("compliant_count"),
                "compliance_pct": flow.get("compliance_pct"),
                "violations_sample": (flow.get("violations") or [])[:15],
            },
            "skipped_stages": (value.get("skipped_stages") or [])[:8],
        }
    if key == "risk_board" and isinstance(value, dict):
        return {
            "high_or_critical_count": value.get("high_or_critical_count"),
            "cards_that_need_attention": (value.get("cards_that_need_attention") or [])[:10],
        }
    return value


def _summarize_trends(trends: dict[str, Any]) -> dict[str, Any]:
    return {
        "months": trends.get("months") or [],
        "team": trends.get("team") or [],
        "developers": {
            name: series
            for name, series in list((trends.get("developers") or {}).items())[:15]
        },
    }


def _summarize_collaborators(
    rows: list[dict[str, Any]],
    violations_by_dev: dict[str, int],
) -> list[dict[str, Any]]:
    summarized: list[dict[str, Any]] = []
    for row in rows:
        if not row.get("name"):
            continue
        summary = row.get("summary") or {}
        role_metrics = []
        for role in row.get("role_metrics") or []:
            role_metrics.append(
                {
                    "role_label": role.get("role_label"),
                    "cards_active": role.get("cards_active"),
                    "cards_created": role.get("cards_created"),
                    "cards_delivered": role.get("cards_delivered"),
                    "fibonacci_total": role.get("fibonacci_total"),
                    "acceptance_rate_pct": role.get("acceptance_rate_pct"),
                    "quality_rate_pct": role.get("quality_rate_pct"),
                    "rework_rate_pct": role.get("rework_rate_pct"),
                    "peer_review_returns": role.get("peer_review_returns"),
                    "reviews_done": role.get("reviews_done"),
                    "formal_reviews_done": role.get("formal_reviews_done"),
                    "cards_tested": role.get("cards_tested"),
                    "approved_first_pass": role.get("approved_first_pass"),
                    "prevented_problems": role.get("prevented_problems"),
                    "retest_cycles_total": role.get("retest_cycles_total"),
                    "planning_ok_rate_pct": role.get("planning_ok_rate_pct"),
                    "double_review_mandatory_violations": role.get("double_review_mandatory_violations"),
                    "workflow_compliance_violations": violations_by_dev.get(row.get("name"), 0),
                }
            )
        summarized.append(
            {
                "name": row.get("name"),
                "roles": row.get("roles") or [],
                "cards_active": summary.get("cards_active"),
                "cards_delivered": summary.get("cards_delivered"),
                "cards_created": summary.get("cards_created"),
                "fibonacci_total": summary.get("fibonacci_total"),
                "quality_rate_pct": _best_quality_rate(role_metrics),
                "rework_rate_pct": _best_rework_rate(role_metrics),
                "time_human": summary.get("time_human"),
                "role_metrics": role_metrics,
            }
        )
    return summarized


def _best_quality_rate(role_metrics: list[dict[str, Any]]) -> float | None:
    values = [
        float(item["quality_rate_pct"])
        for item in role_metrics
        if item.get("quality_rate_pct") is not None
    ]
    return max(values) if values else None


def _best_rework_rate(role_metrics: list[dict[str, Any]]) -> float | None:
    values = [
        float(item["rework_rate_pct"])
        for item in role_metrics
        if item.get("rework_rate_pct") is not None
    ]
    return max(values) if values else None


def _summarize_people_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    keys = (
        "name",
        "cards_delivered",
        "cards_created",
        "cards_tested",
        "fibonacci_normal",
        "fibonacci_analysis",
        "fibonacci_total",
        "acceptance_rate_pct",
        "quality_rate_pct",
        "rework_rate_pct",
        "peer_review_returns",
        "approved_first_pass",
        "prevented_problems",
        "retest_cycles_total",
        "planning_ok_rate_pct",
        "in_production",
        "double_review_mandatory_violations",
    )
    return [{key: row.get(key) for key in keys if row.get(key) is not None} for row in rows]


def _truncate_if_needed(context: dict[str, Any]) -> dict[str, Any]:
    text = json.dumps(context, ensure_ascii=False)
    if len(text) <= MAX_CONTEXT_CHARS:
        return context

    compact = {
        "truncated": True,
        "board": context.get("board"),
        "period": context.get("period"),
        "report_type": context.get("report_type"),
        "overview": context.get("overview"),
        "team_summary": context.get("team_summary"),
        "role_summary": context.get("role_summary"),
        "individual_summary": context.get("individual_summary"),
        "trends_6m": context.get("trends_6m"),
        "collaborators_total": context.get("collaborators_total"),
        "collaborators_names": context.get("collaborators_names"),
        "collaborators": context.get("collaborators") or [],
        "developers": (context.get("developers") or [])[:20],
        "testers": (context.get("testers") or [])[:20],
        "requesters": (context.get("requesters") or [])[:20],
        "bottlenecks": context.get("bottlenecks"),
        "sla": context.get("sla"),
        "dora": context.get("dora"),
        "process_discipline": context.get("process_discipline"),
        "returns_pauses_insights": context.get("returns_pauses_insights"),
        "flow_column_insights": context.get("flow_column_insights"),
    }
    return compact
