from __future__ import annotations

from typing import Any

from trello_metrics.domain.workflow import WorkflowConfig
from trello_metrics.metrics.aggregators.bottlenecks import aggregate_bottlenecks
from trello_metrics.metrics.aggregators.developers import aggregate_developers
from trello_metrics.metrics.timeline import CardTimeline
from trello_metrics.utils.period import MonthPeriod


def aggregate_trends(
    timelines: list[CardTimeline],
    cards: list,
    workflow: WorkflowConfig,
    periods: list[MonthPeriod],
) -> dict[str, Any]:
    months: list[dict[str, Any]] = []
    monthly_developers: list[list[dict[str, Any]]] = []

    for period in periods:
        developers = aggregate_developers(timelines, period)
        bottlenecks = aggregate_bottlenecks(timelines, cards, workflow, period)
        monthly_developers.append(developers)

        delivered = sum(item["cards_delivered"] for item in developers)
        fibonacci_normal = sum(item["fibonacci_normal"] for item in developers)
        fibonacci_analysis = sum(item["fibonacci_analysis"] for item in developers)
        returns_dev = sum(item["return_dev_count"] for item in developers)
        cards_with_rework = sum(item.get("cards_with_rework", 0) for item in developers)
        rework_rate_pct = round(100 * cards_with_rework / delivered, 1) if delivered else 0.0
        quality_rate_pct = round(100 - rework_rate_pct, 1) if delivered else 0.0

        months.append(
            {
                "month": period.label,
                "cards_delivered": delivered,
                "fibonacci_normal": fibonacci_normal,
                "fibonacci_analysis": fibonacci_analysis,
                "return_dev_count": returns_dev,
                "cards_with_rework": cards_with_rework,
                "rework_rate_pct": rework_rate_pct,
                "quality_rate_pct": quality_rate_pct,
                "top_bottleneck": bottlenecks.get("top_bottleneck"),
            }
        )

    all_names: set[str] = set()
    for developers in monthly_developers:
        for dev in developers:
            all_names.add(dev["name"])

    developer_series: dict[str, dict[str, list[int]]] = {
        name: {"fibonacci_normal": [], "fibonacci_analysis": []}
        for name in sorted(all_names)
    }

    for developers in monthly_developers:
        by_name = {dev["name"]: dev for dev in developers}
        for name in developer_series:
            dev = by_name.get(name)
            developer_series[name]["fibonacci_normal"].append(
                dev["fibonacci_normal"] if dev else 0
            )
            developer_series[name]["fibonacci_analysis"].append(
                dev["fibonacci_analysis"] if dev else 0
            )

    return {
        "months": [period.label for period in periods],
        "team": months,
        "developers": developer_series,
    }
