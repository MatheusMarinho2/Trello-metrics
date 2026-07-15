from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from trello_metrics.domain.workflow import WorkflowConfig
from trello_metrics.metrics.timeline import CardTimeline
from trello_metrics.utils.dates import human_hours, isoformat
from trello_metrics.utils.period import MonthPeriod


@dataclass
class DevAccumulator:
    name: str
    cards_delivered: int = 0
    cards_delivered_normal: int = 0
    cards_delivered_analysis: int = 0
    fibonacci_normal: int = 0
    fibonacci_analysis: int = 0
    dev_work_hours_total: float = 0.0
    pipeline_wait_hours_total: float = 0.0
    peer_review_returns: int = 0
    return_dev_count: int = 0
    tester_quality_returns: int = 0
    cards_with_rework: int = 0
    accepted_count: int = 0
    peer_reviews_done: int = 0
    double_review_mandatory_total: int = 0
    double_review_mandatory_violations: int = 0
    cards: list[dict[str, Any]] = field(default_factory=list)

    def add_delivery(self, timeline: CardTimeline) -> None:
        self.cards_delivered += 1
        points = timeline.fibonacci_level or 0
        if timeline.kind == "analysis":
            self.fibonacci_analysis += points
            self.cards_delivered_analysis += 1
        elif timeline.kind == "problem":
            self.fibonacci_normal += points
            self.cards_delivered_normal += 1
        self.dev_work_hours_total += timeline.dev_work_hours
        self.pipeline_wait_hours_total += timeline.pipeline_wait_hours
        # peer_review → development = sugestão aceita (colaboração), não penalidade
        self.peer_review_returns += timeline.peer_review_returns
        self.return_dev_count += timeline.developer_penalty_return_count
        self.tester_quality_returns += timeline.return_dev_by_teste_legitimate_count
        if timeline.developer_penalty_return_count > 0:
            self.cards_with_rework += 1
        if timeline.accepted_without_dev_return:
            self.accepted_count += 1
        if timeline.double_review_required:
            self.double_review_mandatory_total += 1
            if timeline.double_review_violation:
                self.double_review_mandatory_violations += 1
        self.cards.append(_developer_card_entry(timeline))

    def add_peer_review(self) -> None:
        self.peer_reviews_done += 1

    def to_dict(self) -> dict[str, Any]:
        avg_dev_work = self.dev_work_hours_total / self.cards_delivered if self.cards_delivered else 0.0
        avg_wait = self.pipeline_wait_hours_total / self.cards_delivered if self.cards_delivered else 0.0
        total_points = self.fibonacci_normal + self.fibonacci_analysis
        avg_per_point = self.dev_work_hours_total / total_points if total_points else 0.0
        acceptance_rate = (
            round(100 * self.accepted_count / self.cards_delivered, 1)
            if self.cards_delivered
            else 0.0
        )
        rework_rate = (
            round(100 * self.cards_with_rework / self.cards_delivered, 1)
            if self.cards_delivered
            else 0.0
        )
        quality_rate = round(100 - rework_rate, 1) if self.cards_delivered else 0.0
        wait_ratio = (
            round(100 * self.pipeline_wait_hours_total / (self.dev_work_hours_total + self.pipeline_wait_hours_total), 1)
            if (self.dev_work_hours_total + self.pipeline_wait_hours_total) > 0
            else 0.0
        )
        return {
            "name": self.name,
            "cards_delivered": self.cards_delivered,
            "cards_delivered_normal": self.cards_delivered_normal,
            "cards_delivered_analysis": self.cards_delivered_analysis,
            "fibonacci_normal": self.fibonacci_normal,
            "fibonacci_analysis": self.fibonacci_analysis,
            "fibonacci_total": total_points,
            "dev_work_hours_total": round(self.dev_work_hours_total, 2),
            "dev_work_hours_human": human_hours(self.dev_work_hours_total),
            "pipeline_wait_hours_total": round(self.pipeline_wait_hours_total, 2),
            "pipeline_wait_hours_human": human_hours(self.pipeline_wait_hours_total),
            "avg_dev_work_hours": round(avg_dev_work, 2),
            "avg_dev_work_human": human_hours(avg_dev_work),
            "avg_pipeline_wait_hours": round(avg_wait, 2),
            "avg_pipeline_wait_human": human_hours(avg_wait),
            "pipeline_wait_ratio_pct": wait_ratio,
            "avg_hours_per_point": round(avg_per_point, 2),
            "avg_dev_hours": round(avg_dev_work, 2),
            "avg_dev_human": human_hours(avg_dev_work),
            "suggestions_accepted": self.peer_review_returns,
            "peer_review_returns": self.peer_review_returns,
            "return_dev_count": self.return_dev_count,
            "tester_quality_returns": self.tester_quality_returns,
            "cards_with_rework": self.cards_with_rework,
            "rework_rate_pct": rework_rate,
            "quality_rate_pct": quality_rate,
            "acceptance_rate_pct": acceptance_rate,
            "peer_reviews_done": self.peer_reviews_done,
            "double_review_mandatory_total": self.double_review_mandatory_total,
            "double_review_mandatory_violations": self.double_review_mandatory_violations,
        }


def _developer_card_entry(timeline: CardTimeline) -> dict[str, Any]:
    work = timeline.dev_work_hours
    wait = timeline.pipeline_wait_hours
    total_flow = work + wait
    wait_ratio = round(100 * wait / total_flow, 1) if total_flow > 0 else 0.0
    return {
        "card_id": timeline.card_id,
        "card_name": timeline.card_name,
        "kind": timeline.kind,
        "sistema": timeline.sistema,
        "fibonacci_level": timeline.fibonacci_level,
        "delivered_at": isoformat(timeline.delivered_at),
        "cycle_time_human": (
            human_hours(timeline.metric_cycle_hours)
            if timeline.metric_cycle_hours is not None
            else (human_hours(timeline.cycle_time_hours) if timeline.cycle_time_hours is not None else "-")
        ),
        "metric_cycle_hours": timeline.metric_cycle_hours,
        "dev_work_hours": work,
        "dev_work_human": human_hours(work),
        "pipeline_wait_hours": wait,
        "pipeline_wait_human": human_hours(wait),
        "pipeline_wait_ratio_pct": wait_ratio,
        "return_dev_count": timeline.developer_penalty_return_count,
        "raw_return_dev_count": timeline.return_dev_count,
        "prevented_problems": timeline.return_dev_by_teste_legitimate_count,
        "tester_quality_returns": timeline.return_dev_by_teste_legitimate_count,
        "accepted_without_dev_return": timeline.accepted_without_dev_return,
        "etapas_count": len(timeline.stage_timeline),
    }


def aggregate_developers(
    timelines: list[CardTimeline],
    period: MonthPeriod,
    workflow: WorkflowConfig | None = None,
) -> list[dict[str, Any]]:
    accumulators: dict[str, DevAccumulator] = {}

    for timeline in timelines:
        if not timeline.is_delivered_in(period):
            continue
        dev = timeline.desenvolvedor
        if dev == "Nao informado" or not dev.startswith("D-"):
            continue
        if workflow is not None and workflow.should_ignore_person(dev):
            continue
        if dev not in accumulators:
            accumulators[dev] = DevAccumulator(name=dev)
        accumulators[dev].add_delivery(timeline)

    rows = [item.to_dict() for item in accumulators.values()]
    rows.sort(key=lambda row: (row["fibonacci_total"], row["cards_delivered"]), reverse=True)
    return rows


def aggregate_developer_profiles(
    timelines: list[CardTimeline],
    period: MonthPeriod,
    workflow: WorkflowConfig | None = None,
) -> list[dict[str, Any]]:
    accumulators: dict[str, DevAccumulator] = {}

    for timeline in timelines:
        if not timeline.is_delivered_in(period):
            continue
        if timeline.desenvolvedor == "Nao informado":
            continue
        if not timeline.desenvolvedor.startswith("D-"):
            continue
        dev = timeline.desenvolvedor
        if workflow is not None and workflow.should_ignore_person(dev):
            continue
        if dev not in accumulators:
            accumulators[dev] = DevAccumulator(name=dev)
        accumulators[dev].add_delivery(timeline)

    profiles = []
    for acc in accumulators.values():
        profile = acc.to_dict()
        profile["cards"] = sorted(acc.cards, key=lambda item: item["card_name"])
        profiles.append(profile)
    profiles.sort(key=lambda row: (row["fibonacci_total"], row["cards_delivered"]), reverse=True)
    return profiles
