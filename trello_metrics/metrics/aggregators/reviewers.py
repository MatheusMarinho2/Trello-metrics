from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from trello_metrics.domain.workflow import WorkflowConfig
from trello_metrics.metrics.timeline import CardTimeline
from trello_metrics.utils.dates import human_hours
from trello_metrics.utils.period import MonthPeriod


@dataclass
class ReviewerAccumulator:
    name: str
    reviews_done: int = 0
    approved: int = 0
    sent_back: int = 0
    escaped_to_test: int = 0
    review_hours_total: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        avg = self.review_hours_total / self.reviews_done if self.reviews_done else 0.0
        approval_rate = round(100 * self.approved / self.reviews_done, 1) if self.reviews_done else 0.0
        suggestion_rate = (
            round(100 * self.sent_back / self.reviews_done, 1) if self.reviews_done else 0.0
        )
        return {
            "name": self.name,
            "reviews_done": self.reviews_done,
            "suggestions_accepted": self.sent_back,
            "suggestion_rate_pct": suggestion_rate,
            "approved": self.approved,
            "escaped_to_test": self.escaped_to_test,
            "approval_rate_pct": approval_rate,
            "avg_review_human": human_hours(avg),
            # compat com exports/AI antigos
            "sent_back": self.sent_back,
            "avg_review_hours": round(avg, 2),
        }


def aggregate_reviewers(
    timelines: list[CardTimeline],
    period: MonthPeriod,
    workflow: WorkflowConfig | None = None,
) -> list[dict[str, Any]]:
    accumulators: dict[str, ReviewerAccumulator] = {}

    for timeline in timelines:
        if timeline.revisor_par == "Nao informado":
            continue
        if not timeline.is_delivered_in(period):
            continue
        if workflow is not None and workflow.should_ignore_person(timeline.revisor_par):
            continue

        reviewer = timeline.revisor_par
        if reviewer not in accumulators:
            accumulators[reviewer] = ReviewerAccumulator(name=reviewer)

        acc = accumulators[reviewer]
        acc.reviews_done += 1
        acc.review_hours_total += timeline.peer_review_hours
        # peer_review → development = sugestões do revisor (benefício / garantia de qualidade)
        if timeline.peer_review_sent_back:
            acc.sent_back += 1
        # Escape: retorno de revisão formal ou teste legítimo (nunca indevido)
        if (
            timeline.return_dev_by_revisao_count > 0
            or timeline.return_dev_by_teste_legitimate_count > 0
        ):
            acc.escaped_to_test += 1
        else:
            acc.approved += 1

    rows = [item.to_dict() for item in accumulators.values()]
    rows.sort(key=lambda row: (row["suggestions_accepted"], row["reviews_done"]), reverse=True)
    return rows
