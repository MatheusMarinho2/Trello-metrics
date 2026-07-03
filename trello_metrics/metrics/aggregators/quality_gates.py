from __future__ import annotations

from typing import Any

from trello_metrics.metrics.timeline import CardTimeline
from trello_metrics.utils.period import MonthPeriod


def aggregate_quality_gates(
    timelines: list[CardTimeline],
    period: MonthPeriod,
) -> dict[str, Any]:
    """Conformidade da regra de dupla revisao (revisao em par + revisao formal).

    Nivel 8/13: dupla revisao e obrigatoria -> violacoes sao listadas nominalmente.
    Nivel 5: dupla revisao e recomendada (bom tom), mas nao obrigatoria -> so informativo.
    """
    delivered = [timeline for timeline in timelines if timeline.is_delivered_in(period)]

    mandatory = [timeline for timeline in delivered if timeline.double_review_required]
    violations = [timeline for timeline in mandatory if timeline.double_review_violation]
    recommended = [timeline for timeline in delivered if timeline.double_review_recommended]
    recommended_done = [timeline for timeline in recommended if timeline.double_review_done]

    violation_rows = [
        {
            "card_name": timeline.card_name,
            "desenvolvedor": timeline.desenvolvedor,
            "sistema": timeline.sistema,
            "fibonacci_level": timeline.fibonacci_level,
            "passed_peer_review": timeline.passed_peer_review,
            "passed_formal_review": timeline.passed_formal_review,
        }
        for timeline in violations
    ]

    return {
        "mandatory_total": len(mandatory),
        "mandatory_violations_count": len(violations),
        "mandatory_compliance_pct": (
            round(100 * (len(mandatory) - len(violations)) / len(mandatory), 1)
            if mandatory
            else 100.0
        ),
        "mandatory_violations": violation_rows,
        "recommended_total": len(recommended),
        "recommended_done_count": len(recommended_done),
        "recommended_done_pct": (
            round(100 * len(recommended_done) / len(recommended), 1) if recommended else 0.0
        ),
    }
