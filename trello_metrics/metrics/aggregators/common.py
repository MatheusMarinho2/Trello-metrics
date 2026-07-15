from __future__ import annotations

import math
import statistics
from datetime import datetime
from typing import Any, Iterable

from trello_metrics.domain.workflow import WorkflowConfig
from trello_metrics.metrics.timeline import CardTimeline, StageTimelineEntry
from trello_metrics.utils.business_hours import duration_hours
from trello_metrics.utils.dates import human_hours, isoformat
from trello_metrics.utils.text import normalize_key


HIGH_PRIORITY_KEYS = {"URGENTE", "CRITICA"}
CORRECTION_LABEL_KEYS = {"CORRECAO"}


def percentile(values: list[float], pct: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return round(ordered[0], 2)
    rank = (pct / 100) * (len(ordered) - 1)
    lower = math.floor(rank)
    upper = math.ceil(rank)
    if lower == upper:
        return round(ordered[int(rank)], 2)
    fraction = rank - lower
    return round(ordered[lower] + (ordered[upper] - ordered[lower]) * fraction, 2)


def time_stats(values: Iterable[float], min_sample: int = 10) -> dict[str, Any]:
    clean = [float(value) for value in values if value is not None and value >= 0]
    if not clean:
        return {
            "samples": 0,
            "median_hours": None,
            "p85_hours": None,
            "p95_hours": None,
            "avg_hours": None,
            "min_hours": None,
            "max_hours": None,
            "total_hours": 0.0,
            "median_human": "-",
            "p85_human": "-",
            "p95_human": "-",
            "insufficient_data": True,
        }

    median = round(statistics.median(clean), 2)
    p85 = percentile(clean, 85)
    p95 = percentile(clean, 95)
    avg = round(statistics.fmean(clean), 2)
    total = round(sum(clean), 2)
    return {
        "samples": len(clean),
        "median_hours": median,
        "p85_hours": p85,
        "p95_hours": p95,
        "avg_hours": avg,
        "min_hours": round(min(clean), 2),
        "max_hours": round(max(clean), 2),
        "total_hours": total,
        "median_human": human_hours(median),
        "p85_human": human_hours(p85 or 0),
        "p95_human": human_hours(p95 or 0),
        "avg_human": human_hours(avg),
        "total_human": human_hours(total),
        "insufficient_data": len(clean) < min_sample,
    }


def ratio(numerator: int | float, denominator: int | float) -> float:
    return round(100 * numerator / denominator, 1) if denominator else 0.0


def is_high_priority(value: str | None) -> bool:
    return normalize_key(value) in HIGH_PRIORITY_KEYS


def priority_rank(value: str | None) -> int:
    key = normalize_key(value)
    order = {
        "URGENTE": 0,
        "CRITICA": 1,
        "ALTA": 2,
        "MEDIA": 3,
        "BAIXA": 4,
        "SEM PRIORIDADE": 5,
    }
    return order.get(key, 6)


def is_correction(timeline: CardTimeline) -> bool:
    return any(normalize_key(label) in CORRECTION_LABEL_KEYS for label in timeline.labels)


def first_stage_start(timeline: CardTimeline, *groups: str) -> datetime | None:
    group_set = set(groups)
    for stage in timeline.stage_timeline:
        if stage.group in group_set:
            return stage.start_at
    return None


def first_stage_entry(timeline: CardTimeline, *groups: str) -> StageTimelineEntry | None:
    group_set = set(groups)
    for stage in timeline.stage_timeline:
        if stage.group in group_set:
            return stage
    return None


def stage_duration_until(
    stage: StageTimelineEntry,
    cap_at: datetime | None,
    workflow: WorkflowConfig,
    *,
    person: str | None = None,
) -> float:
    if not stage.start_at:
        return 0.0
    end_at = stage.end_at or cap_at
    if cap_at and end_at and end_at > cap_at:
        end_at = cap_at
    return duration_hours(stage.start_at, end_at, workflow, person=person)


def calendar_person_for_timeline(
    timeline: CardTimeline,
    group: str | None = None,
) -> str | None:
    """Pessoa cujo calendario (HE/excecao por colaborador) vale para o trecho de tempo."""
    group_people = {
        "analysis_planning": "solicitante",
        "planning": "solicitante",
        "approval": "solicitante",
        "development": "desenvolvedor",
        "return_developer": "desenvolvedor",
        "peer_review": "revisor_par",
        "review": "revisor",
        "testing": "tester",
        "waiting_test": "tester",
    }
    if group:
        attr = group_people.get(group)
        if attr:
            person = str(getattr(timeline, attr, "") or "").strip()
            if person and person.lower() not in {"nao informado", "não informado", "-"}:
                return person
    for attr in ("desenvolvedor", "tester", "solicitante", "revisor", "revisor_par"):
        person = str(getattr(timeline, attr, "") or "").strip()
        if person and person.lower() not in {"nao informado", "não informado", "-"}:
            return person
    return None


def timeline_card_ref(timeline: CardTimeline) -> dict[str, Any]:
    return {
        "card_id": timeline.card_id,
        "card_name": timeline.card_name,
        "kind": timeline.kind,
        "sistema": timeline.sistema,
        "desenvolvedor": timeline.desenvolvedor,
        "prioridade": timeline.prioridade,
        "fibonacci_level": timeline.fibonacci_level,
        "created_at": isoformat(timeline.created_at),
        "delivered_at": isoformat(timeline.delivered_at),
    }


def week_key(moment: datetime | None, timezone_name: str = "America/Sao_Paulo") -> str:
    if moment is None:
        return "sem-data"
    from zoneinfo import ZoneInfo

    local = moment.astimezone(ZoneInfo(timezone_name))
    year, week, _ = local.isocalendar()
    return f"{year:04d}-W{week:02d}"
