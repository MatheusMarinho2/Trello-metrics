from __future__ import annotations

from typing import Any

from trello_metrics.metrics.aggregators.common import is_high_priority
from trello_metrics.metrics.timeline import CardTimeline
from trello_metrics.utils.dates import isoformat


def aggregate_risk_board(
    timelines: list[CardTimeline],
    aging_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    aging_by_card = {row["card_id"]: row for row in aging_rows}
    rows: list[dict[str, Any]] = []
    for timeline in timelines:
        aging = aging_by_card.get(timeline.card_id)
        if not aging:
            continue
        score, reasons = _risk_score(timeline, aging)
        rows.append(
            {
                "card_id": timeline.card_id,
                "card_name": timeline.card_name,
                "sistema": timeline.sistema,
                "desenvolvedor": timeline.desenvolvedor,
                "prioridade": timeline.prioridade,
                "fibonacci_level": timeline.fibonacci_level,
                "current_stage": aging.get("title"),
                "current_group": aging.get("group"),
                "current_list": aging.get("list_name"),
                "age_hours": aging.get("age_hours"),
                "age_human": aging.get("age_human"),
                "p85_hours": aging.get("p85_hours"),
                "status": aging.get("status"),
                "return_dev_count": timeline.developer_penalty_return_count,
                "return_sup_count": timeline.return_sup_count,
                "pause_count": timeline.pause_count,
                "score": score,
                "level": _risk_level(score),
                "reasons": reasons,
                "created_at": isoformat(timeline.created_at),
                "url": aging.get("url"),
            }
        )
    rows.sort(key=lambda item: (item["score"], item["age_hours"] or 0), reverse=True)
    return {
        "high_or_critical_count": sum(1 for row in rows if row["level"] in {"alto", "critico"}),
        "cards_that_need_attention": [
            row for row in rows if row["level"] in {"alto", "critico"}
        ][:20],
        "cards": rows,
    }


def _risk_score(timeline: CardTimeline, aging: dict[str, Any]) -> tuple[int, list[str]]:
    score = 0
    reasons: list[str] = []

    status = aging.get("status")
    if status == "above_p85":
        score += 3
        reasons.append("idade acima do P85 historico da etapa")
    elif status == "above_p50":
        score += 1
        reasons.append("idade acima do P50 historico da etapa")

    if is_high_priority(timeline.prioridade):
        score += 2
        reasons.append("prioridade urgente/critica")

    returns = timeline.developer_penalty_return_count + timeline.return_sup_count
    if returns >= 2:
        score += 2
        reasons.append(f"{returns} retornos")
    elif returns == 1:
        score += 1
        reasons.append("1 retorno")

    if aging.get("group") == "paused":
        score += 2
        reasons.append("card pausado agora")
    elif timeline.pause_count > 0:
        score += 1
        reasons.append("ja teve pausa")

    return score, reasons


def _risk_level(score: int) -> str:
    if score >= 5:
        return "critico"
    if score >= 3:
        return "alto"
    if score >= 1:
        return "medio"
    return "baixo"
