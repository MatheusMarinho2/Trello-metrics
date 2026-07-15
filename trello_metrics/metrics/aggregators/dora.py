from __future__ import annotations

from collections import Counter
from typing import Any

from trello_metrics.domain.workflow import WorkflowConfig
from trello_metrics.metrics.aggregators.common import calendar_person_for_timeline, time_stats, week_key
from trello_metrics.metrics.timeline import CardTimeline, StageTimelineEntry
from trello_metrics.utils.business_hours import duration_hours
from trello_metrics.utils.period import MonthPeriod


PRODUCTION_GROUPS = {"production", "direct_production"}
PRODUCTION_DEPLOY_QUEUE_GROUPS = {"waiting_production"}

# DORA parcial: so frequencia de deploy e lead time (sem CFR / time to restore).
DORA_METRICS_ENABLED = True


def aggregate_dora_metrics(
    timelines: list[CardTimeline],
    period: MonthPeriod,
    workflow: WorkflowConfig,
    failure_window_days: int = 7,
) -> dict[str, Any]:
    del failure_window_days  # mantido na assinatura por compatibilidade; CFR desativado
    deployments = [
        (timeline, stage)
        for timeline in timelines
        if timeline.kind == "problem"
        for stage in timeline.stage_timeline
        if stage.group in PRODUCTION_GROUPS and period.contains(stage.start_at)
    ]
    deploy_frequency = Counter(week_key(stage.start_at) for _, stage in deployments)
    deploy_by_system = Counter(timeline.sistema for timeline, _ in deployments)
    deploy_by_path = Counter(stage.group for _, stage in deployments)
    deploy_lead_values = [
        duration_hours(
            start,
            stage.start_at,
            workflow,
            person=calendar_person_for_timeline(timeline, "development"),
        )
        for timeline, stage in deployments
        if (start := _production_deploy_window_start(timeline, stage))
    ]

    return {
        "note": (
            "DORA parcial: apenas frequencia de deploy e lead time de mudanca. "
            "Change failure rate e time to restore estao desativados ate revalidacao. "
            "Deploy = entrada em Em producao ou Diretamente na producao."
        ),
        "deployment_frequency": {
            "total": len(deployments),
            "by_week": dict(sorted(deploy_frequency.items())),
            "by_system": [
                {"sistema": sistema, "count": count}
                for sistema, count in deploy_by_system.most_common()
            ],
            "by_path": {
                "standard_production": deploy_by_path.get("production", 0),
                "direct_production": deploy_by_path.get("direct_production", 0),
            },
        },
        "lead_time_deploy": time_stats(deploy_lead_values),
    }


def _production_deploy_window_start(
    timeline: CardTimeline,
    production_stage: StageTimelineEntry,
):
    """Lead time de deploy produtivo: da fila de producao ate Em producao."""
    for stage in timeline.stage_timeline:
        if stage.group in PRODUCTION_DEPLOY_QUEUE_GROUPS:
            return stage.start_at
    if production_stage.group == "direct_production":
        return production_stage.start_at
    return None
