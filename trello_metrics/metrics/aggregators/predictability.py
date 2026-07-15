from __future__ import annotations

from collections import defaultdict
from typing import Any

from trello_metrics.domain.models import DueChangeEvent, MemberEvent, TrelloCard
from trello_metrics.metrics.aggregators.common import time_stats
from trello_metrics.metrics.timeline import CardTimeline
from trello_metrics.utils.business_hours import duration_hours
from trello_metrics.domain.workflow import WorkflowConfig
from trello_metrics.utils.period import MonthPeriod
from trello_metrics.utils.text import normalize_key


def aggregate_member_assignment(
    timelines: list[CardTimeline],
    cards: list[TrelloCard],
    member_events: list[MemberEvent],
    workflow: WorkflowConfig,
    period: MonthPeriod,
) -> dict[str, Any]:
    card_by_id = {card.id: card for card in cards}
    adds_by_card: dict[str, list[MemberEvent]] = defaultdict(list)
    for event in member_events:
        if event.op == "add" and period.contains(event.at):
            adds_by_card[event.card_id].append(event)

    latencies: list[float] = []
    inconsistent = 0
    compared = 0
    for timeline in timelines:
        if not timeline.is_created_in(period) and not timeline.is_delivered_in(period):
            continue
        card = card_by_id.get(timeline.card_id)
        if not card:
            continue
        first_add = min(adds_by_card.get(card.id, []), key=lambda item: item.at, default=None)
        if first_add and timeline.created_at:
            latencies.append(
                duration_hours(
                    timeline.created_at,
                    first_add.at,
                    workflow,
                    person=first_add.member_name or timeline.desenvolvedor,
                )
            )

        developer = timeline.desenvolvedor
        if developer and card.member_names:
            compared += 1
            if not _names_match(developer, card.member_names):
                inconsistent += 1

    return {
        "assign_latency": time_stats(latencies),
        "inconsistent_pct": round(100 * inconsistent / compared, 1) if compared else None,
        "compared": compared,
        "inconsistent": inconsistent,
        "note": (
            "Latencia = criacao ate primeiro addMemberToCard. "
            "Inconsistencia = campo Desenvolvedor nao casa com idMembers do card."
        ),
    }


def aggregate_due_predictability(
    timelines: list[CardTimeline],
    cards: list[TrelloCard],
    due_changes: list[DueChangeEvent],
    workflow: WorkflowConfig,
    period: MonthPeriod,
) -> dict[str, Any]:
    card_by_id = {card.id: card for card in cards}
    changes_by_card: dict[str, list[DueChangeEvent]] = defaultdict(list)
    for event in due_changes:
        changes_by_card[event.card_id].append(event)

    on_time = 0
    with_due = 0
    deviations: list[float] = []
    replan_cards = 0
    due_cards = 0
    for timeline in timelines:
        if not timeline.is_delivered_in(period) or not timeline.delivered_at:
            continue
        card = card_by_id.get(timeline.card_id)
        if not card:
            continue
        due = _due_at_delivery(card, changes_by_card.get(card.id, []), timeline.delivered_at)
        if due is None:
            continue
        with_due += 1
        due_cards += 1
        if len(changes_by_card.get(card.id, [])) >= 2:
            replan_cards += 1
        delta = duration_hours(due, timeline.delivered_at, workflow, calendar=True)
        # Negativo = adiantado (entregue antes do due): inverter sinal de horas uteis signed
        if timeline.delivered_at <= due:
            on_time += 1
            deviations.append(-abs(duration_hours(timeline.delivered_at, due, workflow)))
        else:
            deviations.append(abs(duration_hours(due, timeline.delivered_at, workflow)))

    return {
        "compliance_pct": round(100 * on_time / with_due, 1) if with_due else None,
        "with_due": with_due,
        "on_time": on_time,
        "delay_stats": time_stats(deviations),
        "replan_rate_pct": round(100 * replan_cards / due_cards, 1) if due_cards else None,
        "note": "Compliance = entregue no due vigente (ultima mudanca de due antes da entrega).",
    }


def aggregate_board_moves(
    board_move_events: list,
    period: MonthPeriod,
) -> dict[str, Any]:
    moved_in = sum(
        1 for event in board_move_events if event.direction == "in" and period.contains(event.at)
    )
    moved_out = sum(
        1 for event in board_move_events if event.direction == "out" and period.contains(event.at)
    )
    return {
        "cards_in": moved_in,
        "cards_out": moved_out,
        "net": moved_in - moved_out,
    }


def _due_at_delivery(card: TrelloCard, changes: list[DueChangeEvent], delivered_at):
    applicable = [event for event in changes if event.at <= delivered_at]
    if applicable:
        return applicable[-1].new_due
    return card.due


def _names_match(developer: str, member_names: list[str]) -> bool:
    dev_key = normalize_key(developer)
    for name in member_names:
        mem_key = normalize_key(name)
        if not mem_key:
            continue
        if dev_key == mem_key or dev_key.endswith(mem_key) or mem_key.endswith(dev_key):
            return True
        # Remove prefixos D-/T-/...
        for prefix in ("D-", "T-", "R-", "RP-", "S-"):
            if dev_key.startswith(normalize_key(prefix)):
                stripped = dev_key[len(normalize_key(prefix)) :]
                if stripped and (stripped in mem_key or mem_key in stripped):
                    return True
    return False
