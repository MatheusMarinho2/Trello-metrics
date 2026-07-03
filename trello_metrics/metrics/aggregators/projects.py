from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from trello_metrics.metrics.timeline import CardTimeline
from trello_metrics.utils.period import MonthPeriod


@dataclass
class ProjectAccumulator:
    name: str
    cards_delivered: int = 0
    fibonacci_normal: int = 0
    fibonacci_analysis: int = 0
    dev_scores: dict[str, float] = field(default_factory=dict)

    def add(self, timeline: CardTimeline) -> None:
        self.cards_delivered += 1
        points = timeline.fibonacci_level or 0
        if timeline.kind == "analysis":
            self.fibonacci_analysis += points
        elif timeline.kind == "problem":
            self.fibonacci_normal += points

        if timeline.desenvolvedor != "Nao informado":
            quality_bonus = 1.0 if timeline.accepted_without_dev_return else 0.7
            score = points * quality_bonus
            self.dev_scores[timeline.desenvolvedor] = (
                self.dev_scores.get(timeline.desenvolvedor, 0.0) + score
            )

    def to_dict(self) -> dict[str, Any]:
        top_dev = None
        if self.dev_scores:
            top_dev = max(self.dev_scores.items(), key=lambda item: item[1])[0]
        return {
            "name": self.name,
            "cards_delivered": self.cards_delivered,
            "fibonacci_normal": self.fibonacci_normal,
            "fibonacci_analysis": self.fibonacci_analysis,
            "top_developer": top_dev,
            "developer_scores": dict(
                sorted(self.dev_scores.items(), key=lambda item: item[1], reverse=True)
            ),
        }


def aggregate_projects(
    timelines: list[CardTimeline],
    period: MonthPeriod,
) -> list[dict[str, Any]]:
    accumulators: dict[str, ProjectAccumulator] = {}

    for timeline in timelines:
        if not timeline.is_delivered_in(period):
            continue
        sistema = timeline.sistema
        if sistema not in accumulators:
            accumulators[sistema] = ProjectAccumulator(name=sistema)
        accumulators[sistema].add(timeline)

    rows = [item.to_dict() for item in accumulators.values()]
    rows.sort(key=lambda row: row["fibonacci_normal"] + row["fibonacci_analysis"], reverse=True)
    return rows
