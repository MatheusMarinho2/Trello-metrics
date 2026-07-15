from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from trello_metrics.domain.workflow import WorkflowConfig
from trello_metrics.metrics.timeline import CardTimeline
from trello_metrics.utils.period import MonthPeriod


@dataclass
class DevPointsAccumulator:
    name: str
    cards_normal: int = 0
    cards_analysis: int = 0
    points_normal: int = 0
    points_analysis: int = 0

    def add(self, timeline: CardTimeline) -> None:
        points = timeline.fibonacci_level or 0
        if timeline.kind == "analysis":
            self.cards_analysis += 1
            self.points_analysis += points
        elif timeline.kind == "problem":
            self.cards_normal += 1
            self.points_normal += points

    def to_dict(self) -> dict[str, Any]:
        total_cards = self.cards_normal + self.cards_analysis
        total_points = self.points_normal + self.points_analysis
        return {
            "developer": self.name,
            "cards_normal": self.cards_normal,
            "cards_analysis": self.cards_analysis,
            "cards_total": total_cards,
            "points_normal": self.points_normal,
            "points_analysis": self.points_analysis,
            "points_total": total_points,
        }


def aggregate_fibonacci_points(
    timelines: list[CardTimeline],
    period: MonthPeriod,
    workflow: WorkflowConfig | None = None,
) -> dict[str, Any]:
    """Pontos Fibonacci creditados exclusivamente ao desenvolvedor do card entregue."""
    by_dev: dict[str, DevPointsAccumulator] = {}
    team_normal = 0
    team_analysis = 0
    cards_normal = 0
    cards_analysis = 0

    for timeline in timelines:
        if not timeline.is_delivered_in(period):
            continue
        dev = timeline.desenvolvedor
        if dev == "Nao informado" or not dev.startswith("D-"):
            continue
        if workflow is not None and workflow.should_ignore_person(dev):
            continue
        if dev not in by_dev:
            by_dev[dev] = DevPointsAccumulator(name=dev)
        by_dev[dev].add(timeline)
        points = timeline.fibonacci_level or 0
        if timeline.kind == "analysis":
            cards_analysis += 1
            team_analysis += points
        elif timeline.kind == "problem":
            cards_normal += 1
            team_normal += points

    developers = sorted(
        [item.to_dict() for item in by_dev.values()],
        key=lambda row: (row["points_total"], row["cards_total"]),
        reverse=True,
    )
    return {
        "policy": (
            "Pontos Fibonacci sao creditados somente ao desenvolvedor (prefixo D-) "
            "do card entregue. Revisor, revisor em par, tester e solicitante nao acumulam pontos."
        ),
        "team": {
            "cards_normal": cards_normal,
            "cards_analysis": cards_analysis,
            "cards_total": cards_normal + cards_analysis,
            "points_normal": team_normal,
            "points_analysis": team_analysis,
            "points_total": team_normal + team_analysis,
        },
        "by_developer": developers,
    }
