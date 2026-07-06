from __future__ import annotations

from collections import Counter
from datetime import timedelta
from typing import Any

from trello_metrics.metrics.aggregators.common import (
    is_correction,
    is_high_priority,
    ratio,
    time_stats,
    week_key,
)
from trello_metrics.metrics.timeline import CardTimeline, StageTimelineEntry
from trello_metrics.utils.dates import hours_between, isoformat
from trello_metrics.utils.period import MonthPeriod


PRODUCTION_GROUPS = {"production", "direct_production"}
HOMOLOG_DEPLOY_GROUPS = {"waiting_deploy", "cicd_homologacao"}
PRODUCTION_DEPLOY_QUEUE_GROUPS = {"waiting_production"}


def aggregate_dora_metrics(
    timelines: list[CardTimeline],
    period: MonthPeriod,
    failure_window_days: int = 7,
) -> dict[str, Any]:
    deployments = [
        (timeline, stage)
        for timeline in timelines
        if timeline.kind == "problem"
        for stage in timeline.stage_timeline
        if stage.group in PRODUCTION_GROUPS and period.contains(stage.start_at)
    ]
    deployed_timelines = [timeline for timeline, _ in deployments]
    deploy_frequency = Counter(week_key(stage.start_at) for _, stage in deployments)
    deploy_by_system = Counter(timeline.sistema for timeline, _ in deployments)
    deploy_by_path = Counter(stage.group for _, stage in deployments)
    deploy_lead_values = [
        hours_between(start, stage.start_at)
        for timeline, stage in deployments
        if (start := _production_deploy_window_start(timeline, stage))
    ]

    failures = _change_failures(
        deployments,
        timelines,
        timedelta(days=failure_window_days),
    )
    restore_values = [
        hours_between(timeline.created_at, timeline.delivered_at)
        for timeline in timelines
        if timeline.kind == "problem"
        and timeline.is_delivered_in(period)
        and is_correction(timeline)
        and is_high_priority(timeline.prioridade)
        and timeline.created_at
        and timeline.delivered_at
    ]

    return {
        "note": (
            "Frequencia e falhas de deploy usam apenas Em producao / Diretamente na producao. "
            "Aguardando deploy e CI/CD Homologacao sao etapas de homologacao antes do teste, "
            "nao entram como deploy em producao."
        ),
        "cfr_note": (
            "Change failure rate e um PROXY: conta card corretivo (label CORRECAO) do mesmo "
            "sistema ate 7 dias apos o deploy. Nao mede falha real de pipeline/rollback."
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
        "change_failure_rate": {
            "failed_deployments": len(failures),
            "deployments_evaluated": len(deployed_timelines),
            "rate_pct": ratio(len(failures), len(deployed_timelines)),
            "window_days": failure_window_days,
            "failures": failures[:20],
        },
        "time_to_restore": time_stats(restore_values),
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


def _change_failures(
    deployments: list[tuple[CardTimeline, StageTimelineEntry]],
    timelines: list[CardTimeline],
    window: timedelta,
) -> list[dict[str, Any]]:
    corrections = [
        timeline
        for timeline in timelines
        if timeline.kind == "problem" and is_correction(timeline) and timeline.created_at
    ]
    rows: list[dict[str, Any]] = []
    for deployed, production_stage in deployments:
        production_at = production_stage.start_at
        if not deployed.sistema or not production_at:
            continue
        follow_up = [
            correction
            for correction in corrections
            if correction.card_id != deployed.card_id
            and correction.sistema == deployed.sistema
            and correction.created_at
            and production_at <= correction.created_at <= production_at + window
        ]
        if not follow_up:
            continue
        first = min(follow_up, key=lambda item: item.created_at)
        rows.append(
            {
                "deployment_card_id": deployed.card_id,
                "deployment_card_name": deployed.card_name,
                "sistema": deployed.sistema,
                "deployed_at": isoformat(production_at),
                "correction_card_id": first.card_id,
                "correction_card_name": first.card_name,
                "correction_created_at": isoformat(first.created_at),
            }
        )
    rows.sort(key=lambda item: item["deployed_at"] or "")
    return rows
