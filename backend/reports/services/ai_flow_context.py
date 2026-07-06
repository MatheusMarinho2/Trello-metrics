from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any


COLUMN_RANK_LIMIT = 12
STUCK_SAMPLE_LIMIT = 10


def build_flow_column_insights(
    *,
    flow: dict[str, Any] | None,
    bottlenecks: dict[str, Any] | None,
    sla: dict[str, Any] | None,
    process_discipline: dict[str, Any] | None,
) -> dict[str, Any]:
    flow = flow or {}
    bottlenecks = bottlenecks or {}
    sla = sla or {}
    process_discipline = process_discipline or {}

    stages: dict[str, dict[str, Any]] = {}

    def row(group: str, title: str | None = None) -> dict[str, Any]:
        key = group or title or "unknown"
        if key not in stages:
            stages[key] = {
                "group": group,
                "title": title or group,
                "column_names": set(),
                "signals": [],
            }
        if title:
            stages[key]["title"] = title
        return stages[key]

    for item in flow.get("stage_time") or []:
        stage = row(str(item.get("group") or ""), item.get("title"))
        stage["median_hours"] = item.get("median_hours")
        stage["p95_hours"] = item.get("p95_hours")
        stage["avg_hours"] = item.get("avg_hours")
        stage["median_human"] = item.get("median_human")
        stage["p95_human"] = item.get("p95_human")
        stage["time_samples"] = item.get("samples")

    for item in flow.get("wip_by_stage") or []:
        stage = row(str(item.get("group") or ""), item.get("title"))
        stage["wip_now"] = item.get("count", 0)
        if item.get("title"):
            stage["column_names"].add(str(item["title"]))

    aging_by_group: Counter[str] = Counter()
    for item in flow.get("aging_wip") or []:
        group = str(item.get("group") or "")
        title = item.get("title")
        stage = row(group, title)
        if item.get("list_name"):
            stage["column_names"].add(str(item["list_name"]))
        status = item.get("status")
        if status in {"above_p85", "above_p50"}:
            aging_by_group[group] += 1
            if float(item.get("age_hours") or 0) > float(stage.get("max_age_hours") or 0):
                stage["max_age_hours"] = item.get("age_hours")
                stage["max_age_human"] = item.get("age_human")

    for group, count in aging_by_group.items():
        if group in stages:
            stages[group]["aging_cards"] = count

    for item in bottlenecks.get("by_stage") or []:
        stage = row(str(item.get("group") or ""), item.get("title"))
        stage["bottleneck_avg_hours"] = item.get("avg_hours")
        stage["bottleneck_avg_human"] = item.get("avg_human")
        stage["bottleneck_p95_hours"] = item.get("p95_hours")
        stage["bottleneck_samples"] = item.get("samples")

    for item in sla.get("by_stage") or []:
        stage = row(str(item.get("group") or ""), item.get("title"))
        stage["sla_checks"] = item.get("checks")
        stage["sla_breached_count"] = item.get("breached_count")
        stage["sla_compliance_pct"] = item.get("compliance_pct")
        stage["sla_max_breach_human"] = item.get("max_breach_human")

    for item in process_discipline.get("skipped_stages") or []:
        stage = row(str(item.get("group") or ""), item.get("title"))
        stage["skipped_stage_count"] = item.get("count")
        stage["skipped_optional"] = item.get("optional")

    for item in process_discipline.get("required_fields_by_stage") or []:
        stage = row(str(item.get("group") or ""), item.get("title"))
        missing = item.get("missing") or []
        stage["missing_required_fields_count"] = len(missing)
        stage["required_fields_completion_pct"] = item.get("completion_pct")

    backtracks = Counter()
    missing_core = Counter()
    for violation in (process_discipline.get("flow_conformity") or {}).get("violations") or []:
        for item in violation.get("illegal_backtracks") or []:
            label = item.get("title") or item.get("group") or "coluna"
            backtracks[label] += 1
            stage = row(str(item.get("group") or ""), item.get("title"))
            stage["flow_backtracks"] = stage.get("flow_backtracks", 0) + 1
        for group in violation.get("missing_core_groups") or []:
            missing_core[group] += 1

    stuck_by_column: Counter[str] = Counter()
    stuck_samples: list[dict[str, Any]] = []
    for item in bottlenecks.get("stuck_now") or []:
        column = str(item.get("list") or item.get("group") or "Coluna")
        stuck_by_column[column] += 1
        if len(stuck_samples) < STUCK_SAMPLE_LIMIT:
            stuck_samples.append(
                {
                    "card": item.get("card"),
                    "column": column,
                    "group_title": item.get("group"),
                    "days_stuck": item.get("days_stuck"),
                    "responsavel": item.get("responsavel"),
                }
            )

    ranked: list[dict[str, Any]] = []
    for stage in stages.values():
        score, signals = _inconsistency_score(stage)
        stage["inconsistency_score"] = score
        stage["signals"] = signals
        stage["column_names"] = sorted(stage.get("column_names") or [])
        ranked.append(stage)

    ranked.sort(key=lambda item: item.get("inconsistency_score", 0), reverse=True)
    top_columns = ranked[:COLUMN_RANK_LIMIT]

    flow_conformity = process_discipline.get("flow_conformity") or {}
    return {
        "top_bottleneck": bottlenecks.get("top_bottleneck"),
        "flow_conformity_pct": flow_conformity.get("compliance_pct"),
        "flow_violations_count": max(
            0,
            int(flow_conformity.get("cards_evaluated") or 0)
            - int(flow_conformity.get("compliant_count") or 0),
        ),
        "columns_ranked_by_inconsistency": top_columns,
        "stuck_cards_by_column": [
            {"column": column, "count": count}
            for column, count in stuck_by_column.most_common(8)
        ],
        "flow_backtracks_by_column": [
            {"column": column, "count": count}
            for column, count in backtracks.most_common(8)
        ],
        "skipped_core_stages": [
            {"group": group, "count": count}
            for group, count in missing_core.most_common(8)
        ],
        "stuck_cards_sample": stuck_samples,
        "principal_flow_problems": _principal_problems(top_columns, bottlenecks, flow_conformity),
    }


def _inconsistency_score(stage: dict[str, Any]) -> tuple[int, list[str]]:
    score = 0
    signals: list[str] = []

    breached = int(stage.get("sla_breached_count") or 0)
    sla_checks = int(stage.get("sla_checks") or 0)
    if breached > 0:
        score += min(12, breached * 2)
        compliance = stage.get("sla_compliance_pct")
        signals.append(f"SLA estourado em {breached} checagens ({compliance}% conformidade)")

    skipped = int(stage.get("skipped_stage_count") or 0)
    if skipped > 0:
        score += min(10, skipped)
        optional = "opcional" if stage.get("skipped_optional") else "obrigatoria"
        signals.append(f"Etapa {optional} pulada em {skipped} cards")

    backtracks = int(stage.get("flow_backtracks") or 0)
    if backtracks > 0:
        score += min(12, backtracks * 3)
        signals.append(f"Retrocesso de fluxo detectado {backtracks} vezes")

    missing_fields = int(stage.get("missing_required_fields_count") or 0)
    if missing_fields > 0:
        score += min(8, missing_fields)
        signals.append(f"Campos obrigatorios ausentes em {missing_fields} cards")

    wip = int(stage.get("wip_now") or 0)
    if wip >= 8:
        score += 6
        signals.append(f"WIP alto na coluna ({wip} cards)")
    elif wip >= 4:
        score += 3
        signals.append(f"WIP elevado ({wip} cards)")

    avg_bottleneck = float(stage.get("bottleneck_avg_hours") or 0)
    if avg_bottleneck >= 48:
        score += 8
        signals.append(f"Gargalo de tempo ({stage.get('bottleneck_avg_human') or avg_bottleneck}h medio)")
    elif avg_bottleneck >= 24:
        score += 4
        signals.append(f"Tempo medio alto ({stage.get('bottleneck_avg_human') or avg_bottleneck}h)")

    p95 = float(stage.get("p95_hours") or 0)
    median = float(stage.get("median_hours") or 0)
    if p95 and median and p95 >= median * 2.5 and p95 >= 24:
        score += 4
        signals.append(f"Alta variabilidade (P95 {stage.get('p95_human')})")

    aging = int(stage.get("aging_cards") or 0)
    if aging > 0:
        score += min(6, aging)
        signals.append(f"Cards envelhecidos na coluna ({aging})")

    return score, signals


def _principal_problems(
    top_columns: list[dict[str, Any]],
    bottlenecks: dict[str, Any],
    flow_conformity: dict[str, Any],
) -> list[str]:
    problems: list[str] = []
    top = bottlenecks.get("top_bottleneck")
    if top and top.get("title"):
        problems.append(
            f"Maior gargalo de tempo: coluna/etapa '{top['title']}' "
            f"({top.get('avg_human') or top.get('avg_hours')} medio)."
        )

    compliance = flow_conformity.get("compliance_pct")
    evaluated = flow_conformity.get("cards_evaluated")
    if compliance is not None and evaluated:
        problems.append(
            f"Conformidade de fluxo em {compliance}% dos {evaluated} cards entregues avaliados."
        )

    for stage in top_columns[:5]:
        if not stage.get("signals"):
            continue
        title = stage.get("title") or stage.get("group")
        main_signal = stage["signals"][0]
        problems.append(f"Coluna/etapa '{title}': {main_signal}.")

    return problems[:8]
