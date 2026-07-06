from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from trello_metrics.metrics.timeline import CardTimeline
from trello_metrics.utils.dates import human_hours
from trello_metrics.utils.period import MonthPeriod


@dataclass
class RequesterAccumulator:
    name: str
    cards_created: int = 0
    cards_delivered: int = 0
    in_production: int = 0
    without_sup_return: int = 0
    gestor_premature_approvals: int = 0
    planning_hours_total: float = 0.0
    approval_hours_total: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        planning_ok_rate = (
            round(100 * self.without_sup_return / self.cards_delivered, 1)
            if self.cards_delivered
            else 0.0
        )
        gestor_quality_rate = (
            round(
                100
                * (self.cards_delivered - self.gestor_premature_approvals)
                / self.cards_delivered,
                1,
            )
            if self.cards_delivered
            else 0.0
        )
        avg_planning = self.planning_hours_total / self.cards_created if self.cards_created else 0.0
        avg_approval = self.approval_hours_total / self.cards_created if self.cards_created else 0.0
        return {
            "name": self.name,
            "cards_created": self.cards_created,
            "cards_delivered": self.cards_delivered,
            "in_production": self.in_production,
            "gestor_premature_approvals": self.gestor_premature_approvals,
            "gestor_approval_quality_pct": gestor_quality_rate,
            "planning_ok_rate_pct": planning_ok_rate,
            "avg_planning_hours": round(avg_planning, 2),
            "avg_planning_human": human_hours(avg_planning),
            "avg_approval_hours": round(avg_approval, 2),
            "avg_approval_human": human_hours(avg_approval),
        }


def aggregate_requesters(
    timelines: list[CardTimeline],
    period: MonthPeriod,
) -> list[dict[str, Any]]:
    accumulators: dict[str, RequesterAccumulator] = {}

    for timeline in timelines:
        if timeline.solicitante == "Nao informado":
            continue

        requester = timeline.solicitante
        if requester not in accumulators:
            accumulators[requester] = RequesterAccumulator(name=requester)

        acc = accumulators[requester]
        if timeline.is_created_in(period):
            acc.cards_created += 1
            acc.planning_hours_total += timeline.group_hours.get("planning", 0.0)
            acc.approval_hours_total += timeline.group_hours.get("approval", 0.0)

        if timeline.is_delivered_in(period):
            acc.cards_delivered += 1
            if timeline.gestor_premature_approval:
                acc.gestor_premature_approvals += 1
            if timeline.return_sup_count == 0 and not timeline.gestor_premature_approval:
                acc.without_sup_return += 1
            if timeline.group_hours.get("production", 0) > 0 or timeline.kind == "problem":
                acc.in_production += 1

    rows = [item.to_dict() for item in accumulators.values()]
    rows.sort(key=lambda row: row["cards_delivered"], reverse=True)
    return rows
