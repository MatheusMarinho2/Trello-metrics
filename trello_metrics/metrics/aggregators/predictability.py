from __future__ import annotations

from collections import defaultdict
from typing import Any

from trello_metrics.domain.models import MemberEvent, TrelloCard
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
