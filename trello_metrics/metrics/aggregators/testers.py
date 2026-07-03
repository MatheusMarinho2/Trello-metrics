from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from trello_metrics.metrics.timeline import CardTimeline
from trello_metrics.utils.dates import human_hours
from trello_metrics.utils.period import MonthPeriod


@dataclass
class TesterAccumulator:
    name: str
    cards_tested: int = 0
    approved_first_pass: int = 0
    prevented_problems: int = 0
    returns_missing_reason: int = 0
    retest_cycles_total: int = 0
    wait_test_hours_total: float = 0.0
    testing_hours_total: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        avg_wait = self.wait_test_hours_total / self.cards_tested if self.cards_tested else 0.0
        avg_test = self.testing_hours_total / self.cards_tested if self.cards_tested else 0.0
        return {
            "name": self.name,
            "cards_tested": self.cards_tested,
            "tests_started": self.cards_tested,
            "approved_first_pass": self.approved_first_pass,
            "prevented_problems": self.prevented_problems,
            "returned_dev_for_quality": self.prevented_problems,
            "returns_missing_reason": self.returns_missing_reason,
            "retest_cycles_total": self.retest_cycles_total,
            "tester_return_rate_pct": 0.0,
            "returned_dev": self.prevented_problems,
            "avg_wait_test_hours": round(avg_wait, 2),
            "avg_wait_test_human": human_hours(avg_wait),
            "avg_testing_hours": round(avg_test, 2),
            "avg_testing_human": human_hours(avg_test),
        }


def aggregate_testers(
    timelines: list[CardTimeline],
    period: MonthPeriod,
) -> list[dict[str, Any]]:
    accumulators: dict[str, TesterAccumulator] = {}
    cards_with_tester_return: dict[str, int] = {}

    for timeline in timelines:
        if timeline.tester == "Nao informado":
            continue
        if not timeline.is_delivered_in(period):
            continue
        if timeline.kind != "problem":
            continue
        if not timeline.passed_test_phase:
            continue

        tester = timeline.tester
        if tester not in accumulators:
            accumulators[tester] = TesterAccumulator(name=tester)
            cards_with_tester_return[tester] = 0

        acc = accumulators[tester]
        acc.cards_tested += 1
        acc.wait_test_hours_total += timeline.group_hours.get("waiting_test", 0.0)
        acc.testing_hours_total += timeline.group_hours.get("testing", 0.0)
        acc.prevented_problems += timeline.return_dev_by_teste_count
        acc.returns_missing_reason += timeline.test_return_missing_reason_count
        acc.retest_cycles_total += timeline.retest_cycles

        if timeline.tester_returned_dev:
            cards_with_tester_return[tester] += 1
        if not timeline.tester_returned_dev:
            acc.approved_first_pass += 1

    rows: list[dict[str, Any]] = []
    for name, acc in accumulators.items():
        row = acc.to_dict()
        tested = acc.cards_tested
        row["tester_return_rate_pct"] = (
            round(100 * cards_with_tester_return[name] / tested, 1) if tested else 0.0
        )
        rows.append(row)

    rows.sort(key=lambda row: row["cards_tested"], reverse=True)
    return rows
