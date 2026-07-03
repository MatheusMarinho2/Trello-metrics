from __future__ import annotations

from collections import defaultdict
from typing import Any

from trello_metrics.metrics.timeline import CardTimeline
from trello_metrics.utils.dates import human_hours, isoformat
from trello_metrics.utils.period import MonthPeriod


def _card_entry(timeline: CardTimeline) -> dict[str, Any]:
    return {
        "card_id": timeline.card_id,
        "card_name": timeline.card_name,
        "kind": timeline.kind,
        "sistema": timeline.sistema,
        "fibonacci_level": timeline.fibonacci_level,
        "desenvolvedor": timeline.desenvolvedor,
        "revisor_par": timeline.revisor_par,
        "revisor": timeline.revisor,
        "tester": timeline.tester,
        "solicitante": timeline.solicitante,
        "created_at": isoformat(timeline.created_at),
        "delivered_at": isoformat(timeline.delivered_at),
        "closed_at": isoformat(timeline.closed_at),
        "lead_time_hours": timeline.lead_time_hours,
        "lead_time_human": human_hours(timeline.lead_time_hours),
        "cycle_time_hours": timeline.cycle_time_hours,
        "cycle_time_human": (
            human_hours(timeline.cycle_time_hours) if timeline.cycle_time_hours is not None else "-"
        ),
        "dev_hours": timeline.dev_hours,
        "peer_review_hours": timeline.peer_review_hours,
        "test_hours": timeline.test_hours,
        "pause_hours": timeline.pause_hours,
        "return_dev_count": timeline.return_dev_count,
        "developer_penalty_return_count": timeline.developer_penalty_return_count,
        "return_sup_count": timeline.return_sup_count,
        "pause_count": timeline.pause_count,
        "accepted_without_dev_return": timeline.accepted_without_dev_return,
        "peer_review_sent_back": timeline.peer_review_sent_back,
        "passed_peer_review": timeline.passed_peer_review,
        "passed_formal_review": timeline.passed_formal_review,
        "double_review_required": timeline.double_review_required,
        "double_review_recommended": timeline.double_review_recommended,
        "double_review_done": timeline.double_review_done,
        "double_review_violation": timeline.double_review_violation,
        "return_dev_by_teste_count": timeline.return_dev_by_teste_count,
        "return_dev_by_revisao_count": timeline.return_dev_by_revisao_count,
        "test_return_missing_reason_count": timeline.test_return_missing_reason_count,
        "test_cycles": timeline.test_cycles,
        "retest_cycles": timeline.retest_cycles,
        "tester_returned_dev": timeline.tester_returned_dev,
        "descricao": dict(timeline.descricao),
        "dev_work_hours": timeline.dev_work_hours,
        "dev_work_human": human_hours(timeline.dev_work_hours),
        "pipeline_wait_hours": timeline.pipeline_wait_hours,
        "pipeline_wait_human": human_hours(timeline.pipeline_wait_hours),
        "etapas": [entry.to_dict() for entry in timeline.stage_timeline],
        "retornos": [entry.to_dict() for entry in timeline.retorno_history],
        "pausas": [
            {
                "numero": pausa.numero,
                "at": isoformat(pausa.momento),
                "motivo": pausa.motivo,
            }
            for pausa in timeline.pausas
        ],
    }


def aggregate_card_dossier(
    timelines: list[CardTimeline],
    period: MonthPeriod,
) -> dict[str, Any]:
    """Monta um dossie descritivo por card, agrupado por desenvolvedor
    (separando tarefas normais de cards de analise), por solicitante e por
    tester. Escopo: cards com atividade no periodo (criados, entregues,
    fechados ou com retorno/pausa registrado no mes)."""
    active = [timeline for timeline in timelines if timeline.is_active_in(period)]

    by_developer: dict[str, dict[str, list[dict[str, Any]]]] = defaultdict(
        lambda: {"tarefas_normais": [], "cards_analise": []}
    )
    by_solicitante: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_tester: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for timeline in active:
        entry = _card_entry(timeline)

        if timeline.desenvolvedor != "Nao informado":
            bucket = "cards_analise" if timeline.kind == "analysis" else "tarefas_normais"
            by_developer[timeline.desenvolvedor][bucket].append(entry)

        if timeline.solicitante != "Nao informado":
            by_solicitante[timeline.solicitante].append(entry)

        if timeline.tester != "Nao informado":
            by_tester[timeline.tester].append(entry)

    def _sort(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return sorted(rows, key=lambda item: item["card_name"])

    return {
        "cards_total": len(active),
        "by_developer": {
            name: {
                "tarefas_normais": _sort(buckets["tarefas_normais"]),
                "cards_analise": _sort(buckets["cards_analise"]),
            }
            for name, buckets in sorted(by_developer.items())
        },
        "by_solicitante": {
            name: _sort(rows) for name, rows in sorted(by_solicitante.items())
        },
        "by_tester": {name: _sort(rows) for name, rows in sorted(by_tester.items())},
    }
