from __future__ import annotations

import json
from collections import Counter
from typing import Any

from reports.services.ai_flow_context import build_flow_column_insights
from reports.services.ai_returns_context import (
    batch_name_keys,
    build_returns_pauses_insights,
    highlights_for_people,
    names_match,
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
        "project_summary",
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
    # Uma unica chave de antifraude para o prompt (evita duplicar e perder no truncate)
    antifraud_src = _pick(filtered, "antifraud") or _pick(full_metrics, "antifraud")
    context["antifraud_insights"] = _build_antifraud_insights(antifraud_src)
    context.pop("antifraud", None)

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
    insights = context.get("returns_pauses_insights") or {}
    return {
        "period": context.get("period"),
        "report_type": context.get("report_type"),
        "collaborators_total": context.get("collaborators_total"),
        "batch_index": batch_index,
        "batch_total": batch_total,
        "batch_names": names,
        "collaborators_batch": rows,
        "team_summary": context.get("team_summary"),
        "team_comparison": _team_comparison_baseline(context),
        "returns_pauses_summary": _returns_pauses_summary(insights),
        "returns_pauses_highlights": highlights_for_people(insights, names),
        "returns_by_person": _returns_by_person_for_names(insights, names),
        "questionable_returns_for_batch": _questionable_returns_for_names(insights, names),
    }


def _team_comparison_baseline(context: dict[str, Any]) -> dict[str, Any]:
    team = context.get("team_summary") or {}
    developers = context.get("developers") or []
    quality_values = [
        float(row["quality_rate_pct"])
        for row in developers
        if row.get("quality_rate_pct") is not None
    ]
    rework_values = [
        float(row["rework_rate_pct"])
        for row in developers
        if row.get("rework_rate_pct") is not None
    ]
    acceptance_values = [
        float(row["acceptance_rate_pct"])
        for row in developers
        if row.get("acceptance_rate_pct") is not None
    ]
    return {
        "team_cards_delivered": team.get("cards_delivered"),
        "team_quality_rate_pct": team.get("quality_rate_pct"),
        "team_rework_rate_pct": team.get("rework_rate_pct"),
        "team_acceptance_rate_pct": team.get("acceptance_rate_pct"),
        "team_return_dev_events": team.get("total_return_dev_events"),
        "developers_avg_quality_rate_pct": (
            round(sum(quality_values) / len(quality_values), 1) if quality_values else None
        ),
        "developers_avg_rework_rate_pct": (
            round(sum(rework_values) / len(rework_values), 1) if rework_values else None
        ),
        "developers_avg_acceptance_rate_pct": (
            round(sum(acceptance_values) / len(acceptance_values), 1)
            if acceptance_values
            else None
        ),
    }


def _returns_pauses_summary(insights: dict[str, Any]) -> dict[str, Any]:
    if not insights:
        return {"available": False}
    fairness = insights.get("return_fairness_summary") or {}
    return {
        "available": True,
        "cards_with_returns": insights.get("cards_with_returns"),
        "cards_with_pauses": insights.get("cards_with_pauses"),
        "total_return_events": insights.get("total_return_events"),
        "total_pause_events": insights.get("total_pause_events"),
        "questionable_returns_count": len(insights.get("questionable_returns") or []),
        "possibly_unfair_count": fairness.get("possibly_unfair_count"),
        "team_totals": insights.get("team_totals"),
    }


def _returns_by_person_for_names(
    insights: dict[str, Any],
    names: list[str],
) -> dict[str, Any]:
    by_person = insights.get("by_person") or {}
    name_keys = batch_name_keys(names)
    matched: dict[str, Any] = {}
    for person_name, payload in by_person.items():
        if names_match(str(person_name), name_keys):
            matched[str(person_name)] = payload
    return matched


def _questionable_returns_for_names(
    insights: dict[str, Any],
    names: list[str],
) -> list[dict[str, Any]]:
    name_keys = batch_name_keys(names)
    rows = []
    for item in insights.get("questionable_returns") or []:
        people = (
            item.get("desenvolvedor"),
            item.get("tester"),
            item.get("revisor_par"),
            item.get("revisor"),
            item.get("solicitante"),
        )
        if any(names_match(person, name_keys) for person in people):
            rows.append(item)
        if len(rows) >= 8:
            break
    return rows


def _pick(source: dict[str, Any], key: str) -> Any:
    if key not in source:
        return None
    return source[key]


def _build_antifraud_insights(antifraud: Any) -> dict[str, Any] | None:
    if not isinstance(antifraud, dict) or not antifraud:
        return None
    summary = antifraud.get("summary") or {}
    alerts = []
    for item in antifraud.get("alerts") or []:
        if item.get("score") not in {"high", "medium"}:
            continue
        lineage = item.get("source_lineage") or {}
        alerts.append(
            {
                "score": item.get("score"),
                "card_id": item.get("card_id"),
                "card_name": item.get("card_name"),
                "source_card_id": item.get("source_card_id"),
                "source_card_name": item.get("source_card_name"),
                "dest_list": item.get("dest_list"),
                "dest_group": item.get("dest_group"),
                "actor_name": item.get("actor_name"),
                "flags": item.get("flags") or [],
                "reason": item.get("reason"),
                "source_status": lineage.get("status"),
                "passed_terminal": lineage.get("passed_terminal"),
                "last_list_at_copy": lineage.get("last_list_at_copy"),
                "disposal": lineage.get("disposal"),
                "last_list_at_delete": lineage.get("last_list_at_dispose")
                or lineage.get("last_list_at_delete"),
                "seconds_copy_to_delete": lineage.get("seconds_copy_to_dispose")
                if lineage.get("seconds_copy_to_dispose") is not None
                else lineage.get("seconds_copy_to_delete"),
                "rapid_copy_delete": lineage.get("rapid_copy_dispose")
                if lineage.get("rapid_copy_dispose") is not None
                else lineage.get("rapid_copy_delete"),
                "recovery_note": lineage.get("recovery_note"),
                "groups_visited": (lineage.get("groups_visited") or [])[:12],
                "deleted_at": lineage.get("disposed_at")
                or lineage.get("deleted_at")
                or lineage.get("archived_at"),
                "visits": (lineage.get("visits") or [])[:15],
            }
        )
        if len(alerts) >= 20:
            break
    return {
        "summary": summary,
        "whitelisted_copies_count": antifraud.get("whitelisted_copies_count"),
        "alerts": alerts,
    }


def _violations_by_developer(process_discipline: dict[str, Any]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    violations = (process_discipline.get("flow_conformity") or {}).get("violations") or []
    for item in violations:
        developer = item.get("desenvolvedor")
        if developer:
            counts[str(developer)] += 1
    return dict(counts)


def _summarize_section(key: str, value: Any) -> Any:
    if key == "antifraud" and isinstance(value, dict):
        return _build_antifraud_insights(value) or value
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
            "post_terminal_returns": value.get("post_terminal_returns"),
        }
    if key == "priority" and isinstance(value, dict):
        return _shrink_priority(value)
    if key == "analysis_workflow" and isinstance(value, dict):
        return _shrink_analysis_workflow(value)
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

    antifraud = context.get("antifraud_insights") or context.get("antifraud")
    compact: dict[str, Any] = {
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
        "reviewers": (context.get("reviewers") or [])[:20],
        "bottlenecks": context.get("bottlenecks"),
        "sla": _shrink_sla(context.get("sla")),
        "dora": context.get("dora"),
        "flow": context.get("flow"),
        "priority": _shrink_priority(context.get("priority")),
        "quality_gates": context.get("quality_gates"),
        "process_discipline": _shrink_process_discipline(context.get("process_discipline")),
        "analysis_workflow": _shrink_analysis_workflow(context.get("analysis_workflow")),
        "risk_board": context.get("risk_board"),
        "fibonacci_points": context.get("fibonacci_points"),
        "projects": (context.get("projects") or [])[:15],
        "antifraud_insights": antifraud,
        "returns_pauses_insights": _shrink_returns_insights(context.get("returns_pauses_insights")),
        "flow_column_insights": context.get("flow_column_insights"),
    }

    text = json.dumps(compact, ensure_ascii=False)
    if len(text) <= MAX_CONTEXT_CHARS:
        return compact

    # Segundo corte: prioriza antifraude + colaboradores; reduz blocos pesados.
    compact["flow_column_insights"] = _shrink_flow_column_insights(compact.get("flow_column_insights"))
    compact["returns_pauses_insights"] = _shrink_returns_insights(
        compact.get("returns_pauses_insights"),
        limit=6,
    )
    compact["process_discipline"] = _shrink_process_discipline(
        compact.get("process_discipline"),
        violations_limit=5,
    )
    compact.pop("priority", None)
    compact.pop("analysis_workflow", None)
    compact.pop("risk_board", None)
    compact.pop("trends_6m", None)

    text = json.dumps(compact, ensure_ascii=False)
    if len(text) <= MAX_CONTEXT_CHARS:
        return compact

    # Ultimo recurso: nucleo + antifraude + TODOS os colaboradores (lotes dependem disso).
    return {
        "truncated": True,
        "hard_truncated": True,
        "board": compact.get("board"),
        "period": compact.get("period"),
        "report_type": compact.get("report_type"),
        "team_summary": compact.get("team_summary"),
        "collaborators_total": compact.get("collaborators_total"),
        "collaborators_names": compact.get("collaborators_names"),
        "collaborators": compact.get("collaborators") or [],
        "developers": (compact.get("developers") or [])[:20],
        "testers": (compact.get("testers") or [])[:20],
        "requesters": (compact.get("requesters") or [])[:20],
        "reviewers": (compact.get("reviewers") or [])[:20],
        "sla": compact.get("sla"),
        "dora": compact.get("dora"),
        "quality_gates": compact.get("quality_gates"),
        "bottlenecks": compact.get("bottlenecks"),
        "antifraud_insights": antifraud,
        "returns_pauses_insights": _shrink_returns_insights(
            compact.get("returns_pauses_insights"),
            limit=8,
        ),
    }


def _shrink_returns_insights(insights: Any, limit: int = 8) -> Any:
    if not isinstance(insights, dict):
        return insights
    shrunk = dict(insights)
    for key in ("highlight_cards", "questionable_returns", "cards_with_returns"):
        if isinstance(shrunk.get(key), list):
            shrunk[key] = shrunk[key][:limit]
    for key in ("top_return_motives", "top_return_solutions", "top_motive_subtype_pairs"):
        if isinstance(shrunk.get(key), list):
            shrunk[key] = shrunk[key][:8]
    return shrunk


def _shrink_process_discipline(value: Any, violations_limit: int = 8) -> Any:
    if not isinstance(value, dict):
        return value
    flow = value.get("flow_conformity") or {}
    violations = flow.get("violations_sample") or flow.get("violations") or []
    return {
        "flow_conformity": {
            "cards_evaluated": flow.get("cards_evaluated"),
            "compliant_count": flow.get("compliant_count"),
            "compliance_pct": flow.get("compliance_pct"),
            "violations_sample": violations[:violations_limit],
        },
        "skipped_stages": (value.get("skipped_stages") or [])[:6],
        "post_terminal_returns": value.get("post_terminal_returns"),
    }


def _shrink_priority(value: Any) -> Any:
    if not isinstance(value, dict):
        return value
    return {
        "urgent_critical_pct": value.get("urgent_critical_pct"),
        "priority_inflation_alert": value.get("priority_inflation_alert"),
        "queue_jumps_count": value.get("queue_jumps_count"),
        "urgent_aging_count": value.get("urgent_aging_count"),
        "distribution": (value.get("distribution") or [])[:6],
        "lead_time_by_priority": (value.get("lead_time_by_priority") or [])[:6],
        "queue_jumps": (value.get("queue_jumps") or [])[:5],
        "urgent_aging": (value.get("urgent_aging") or [])[:5],
    }


def _shrink_sla(value: Any) -> Any:
    if not isinstance(value, dict):
        return value
    return {
        "team": value.get("team"),
        "by_stage": (value.get("by_stage") or [])[:8],
        "by_developer": (value.get("by_developer") or [])[:12],
        "current_alerts": (value.get("current_alerts") or [])[:8],
    }


def _shrink_analysis_workflow(value: Any) -> Any:
    if not isinstance(value, dict):
        return value
    return {
        "summary": value.get("summary") or {
            k: value.get(k)
            for k in (
                "cards_created",
                "cards_delivered",
                "cards_in_progress",
                "avg_lead_time_human",
            )
            if k in value
        },
        "highlight_cards": (value.get("highlight_cards") or [])[:6],
    }


def _shrink_flow_column_insights(value: Any) -> Any:
    if not isinstance(value, dict):
        return value
    shrunk = dict(value)
    if isinstance(shrunk.get("worst_columns"), list):
        shrunk["worst_columns"] = shrunk["worst_columns"][:4]
    if isinstance(shrunk.get("columns"), list):
        shrunk["columns"] = shrunk["columns"][:6]
    return shrunk
