from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from trello_metrics.domain.workflow import WorkflowConfig
from trello_metrics.metrics.timeline import CardTimeline
from trello_metrics.utils.dates import human_hours
from trello_metrics.utils.period import MonthPeriod


@dataclass
class FormalReviewerAccumulator:
    name: str
    formal_reviews_done: int = 0
    formal_review_passed: int = 0
    review_return_events: int = 0
    escaped_to_test: int = 0
    review_hours_total: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        reviews = self.formal_reviews_done
        avg = self.review_hours_total / reviews if reviews else 0.0
        approval_rate = round(100 * self.formal_review_passed / reviews, 1) if reviews else 0.0
        return {
            "name": self.name,
            "formal_reviews_done": self.formal_reviews_done,
            "formal_review_passed": self.formal_review_passed,
            "review_return_events": self.review_return_events,
            "escaped_to_test": self.escaped_to_test,
            "approval_rate_pct": approval_rate,
            "avg_review_human": human_hours(avg),
            "avg_review_hours": round(avg, 2),
        }


def aggregate_formal_reviewers(
    timelines: list[CardTimeline],
    period: MonthPeriod,
    workflow: WorkflowConfig | None = None,
) -> list[dict[str, Any]]:
    accumulators: dict[str, FormalReviewerAccumulator] = {}

    for timeline in timelines:
        if timeline.revisor == "Nao informado":
            continue
        if not timeline.is_delivered_in(period):
            continue
        if workflow is not None and workflow.should_ignore_person(timeline.revisor):
            continue

        reviewer = timeline.revisor
        if reviewer not in accumulators:
            accumulators[reviewer] = FormalReviewerAccumulator(name=reviewer)

        acc = accumulators[reviewer]
        acc.formal_reviews_done += 1
        acc.review_hours_total += timeline.group_hours.get("review", 0.0)
        acc.review_return_events += timeline.return_dev_by_revisao_count
        # Escape só com retorno de teste legítimo (indevido não prejudica o revisor)
        if timeline.return_dev_by_teste_legitimate_count > 0:
            acc.escaped_to_test += 1
        elif timeline.passed_formal_review:
            acc.formal_review_passed += 1

    rows = [item.to_dict() for item in accumulators.values()]
    rows.sort(key=lambda row: row["formal_reviews_done"], reverse=True)
    return rows
