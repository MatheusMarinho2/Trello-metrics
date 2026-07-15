from __future__ import annotations

from typing import Any

from trello_metrics.domain.workflow import WorkflowConfig
from trello_metrics.metrics.timeline import CardTimeline
from trello_metrics.utils.period import MonthPeriod


def aggregate_first_time_right(
    timelines: list[CardTimeline],
    period: MonthPeriod,
    workflow: WorkflowConfig | None = None,
) -> dict[str, Any]:
    delivered = [
        timeline
        for timeline in timelines
        if timeline.is_delivered_in(period) and timeline.kind == "problem"
    ]

    peer_passed = [
        timeline
        for timeline in delivered
        if timeline.passed_peer_review or timeline.group_visits.get("peer_review", 0) > 0
    ]
    peer_ftr = [
        timeline
        for timeline in peer_passed
        # Sugestão par→andamento não é falha; só retorno atribuído à revisão formal
        if timeline.return_dev_by_revisao_count == 0
    ]

    test_passed = [
        timeline
        for timeline in delivered
        if timeline.passed_test_phase or timeline.group_visits.get("testing", 0) > 0
    ]
    test_ftr = [
        timeline
        for timeline in test_passed
        if timeline.return_dev_by_teste_legitimate_count == 0
    ]

    by_developer: dict[str, dict[str, int]] = {}
    for timeline in delivered:
        name = timeline.desenvolvedor or "Sem desenvolvedor"
        if workflow is not None and workflow.should_ignore_person(name):
            continue
        row = by_developer.setdefault(
            name,
            {"peer_passed": 0, "peer_ftr": 0, "test_passed": 0, "test_ftr": 0},
        )
        if timeline in peer_passed:
            row["peer_passed"] += 1
            if timeline in peer_ftr:
                row["peer_ftr"] += 1
        if timeline in test_passed:
            row["test_passed"] += 1
            if timeline in test_ftr:
                row["test_ftr"] += 1

    return {
        "peer_review": _gate_stats(len(peer_ftr), len(peer_passed)),
        "testing": _gate_stats(len(test_ftr), len(test_passed)),
        "by_developer": [
            {
                "name": name,
                "peer_review_ftr_pct": _pct(row["peer_ftr"], row["peer_passed"]),
                "testing_ftr_pct": _pct(row["test_ftr"], row["test_passed"]),
                "peer_passed": row["peer_passed"],
                "test_passed": row["test_passed"],
            }
            for name, row in sorted(by_developer.items())
        ],
    }


def _gate_stats(ok: int, total: int) -> dict[str, Any]:
    if total <= 0:
        return {"pct": None, "ok": 0, "total": 0, "insufficient_data": True}
    return {
        "pct": round(100 * ok / total, 1),
        "ok": ok,
        "total": total,
        "insufficient_data": False,
    }


def _pct(ok: int, total: int) -> float | None:
    if total <= 0:
        return None
    return round(100 * ok / total, 1)
