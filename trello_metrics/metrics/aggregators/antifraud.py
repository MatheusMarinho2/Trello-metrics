from __future__ import annotations

from collections import defaultdict
from typing import Any

from trello_metrics.domain.models import MovementEvent, TrelloCard
from trello_metrics.domain.workflow import WorkflowConfig
from trello_metrics.metrics.timeline import CardTimeline
from trello_metrics.utils.dates import isoformat
from trello_metrics.utils.period import MonthPeriod
from trello_metrics.utils.text import normalize_key

_DISPOSAL_EVENTS = frozenset({"deleted", "archived"})
_DISPOSED_STATUSES = frozenset(
    {
        "deleted",
        "deleted_partial_history",
        "archived",
        "archived_partial_history",
        "missing_history",
    }
)


def aggregate_antifraud(
    timelines: list[CardTimeline],
    cards: list[TrelloCard],
    all_cards: list[TrelloCard],
    movements: list[MovementEvent],
    workflow: WorkflowConfig,
    period: MonthPeriod,
    *,
    focus_card_ids: set[str] | None = None,
) -> dict[str, Any]:
    cards_by_id = {card.id: card for card in all_cards}
    timelines_by_id = {timeline.card_id: timeline for timeline in timelines}
    events_by_card: dict[str, list[MovementEvent]] = defaultdict(list)
    for event in movements:
        events_by_card[event.card_id].append(event)

    copies = [
        event
        for event in movements
        if event.event_type == "copied"
        and period.contains(event.at)
        and (focus_card_ids is None or event.card_id in focus_card_ids)
    ]

    delivered_names = {
        normalize_key(timeline.card_name)
        for timeline in timelines
        if timeline.is_delivered_in(period) and normalize_key(timeline.card_name)
    }

    alerts: list[dict[str, Any]] = []
    whitelisted = 0
    cross_board_copies = 0

    for event in copies:
        source_id = event.source_card_id
        source_name = event.source_card_name or ""
        dest_group = workflow.group_for_list(event.to_list_name)
        source_card = cards_by_id.get(source_id or "")
        source_events = events_by_card.get(source_id or "", [])
        same_board = _source_known_on_board(source_id, source_card, source_events)

        if _is_whitelisted_copy(source_card, source_name, workflow):
            whitelisted += 1
            continue

        # Copia de outro board para este: fluxo legitimo de entrada — nao antifrauda.
        if not same_board:
            whitelisted += 1
            cross_board_copies += 1
            continue

        lineage = _source_lineage(
            source_id=source_id,
            source_name=source_name,
            source_card=source_card,
            timeline=timelines_by_id.get(source_id or ""),
            source_events=source_events,
            workflow=workflow,
            copy_at=event.at,
        )
        lineage["source_origin"] = "same_board"

        flags: list[str] = []
        reasons: list[str] = []
        score = "low"

        restart_dest = dest_group in workflow.antifraud_restart_dest_groups()
        if restart_dest:
            flags.append("dest_restart")

        if lineage.get("passed_terminal"):
            flags.append("src_was_terminal")
        if lineage.get("status") in _DISPOSED_STATUSES:
            flags.append(f"src_{lineage['status']}")
        if lineage.get("rapid_copy_dispose"):
            flags.append("rapid_copy_dispose")
            if lineage.get("disposal") == "archived":
                flags.append("rapid_copy_archive")
            else:
                flags.append("rapid_copy_delete")
        if lineage.get("last_list_at_dispose") or lineage.get("last_list_at_copy"):
            flags.append("last_list_known")

        same_name = bool(
            normalize_key(event.card_name)
            and normalize_key(event.card_name) == normalize_key(source_name)
        )
        if same_name:
            flags.append("same_name_as_source")

        name_matches_delivered = normalize_key(event.card_name) in delivered_names
        if name_matches_delivered:
            flags.append("name_matches_delivered")

        dispose_noun = "arquivamento" if lineage.get("disposal") == "archived" else "exclusao"
        dispose_adj = "arquivada" if lineage.get("disposal") == "archived" else "excluida"
        last_dispose_list = lineage.get("last_list_at_dispose") or lineage.get("last_list_at_copy")

        if lineage.get("passed_terminal") and restart_dest:
            score = "high"
            reasons.append(
                "Fonte ja passou por etapa terminal e a copia entrou em lista de reinicio (planejamento/backlog)."
            )
        elif lineage.get("rapid_copy_dispose") and restart_dest:
            score = "high"
            last_list = last_dispose_list or "?"
            secs = lineage.get("seconds_copy_to_dispose")
            reasons.append(
                f"Padrao copia->{dispose_noun} em {secs}s; fonte estava em '{last_list}' "
                "e a copia foi para reinicio."
            )
        elif lineage.get("status") in _DISPOSED_STATUSES and restart_dest:
            score = "high"
            if last_dispose_list:
                reasons.append(
                    f"Copia para reinicio com fonte {dispose_adj}; "
                    f"ultima coluna conhecida da fonte: '{last_dispose_list}'."
                )
            else:
                reasons.append(
                    "Copia nao-template para planejamento/backlog cuja fonte foi excluida/arquivada "
                    "ou sem historico recuperavel."
                )
        elif same_name or name_matches_delivered:
            score = "medium"
            if same_name:
                reasons.append("Copia nao-template com o mesmo nome da fonte.")
            if name_matches_delivered:
                reasons.append("Nome igual a um card ja entregue no periodo.")
        elif restart_dest:
            score = "medium"
            reasons.append("Copia nao-template destinada a lista de reinicio.")
        else:
            reasons.append("Copia nao-template sem padrao forte de reset.")

        if lineage.get("recovery_note"):
            reasons.append(lineage["recovery_note"])

        alerts.append(
            {
                "score": score,
                "card_id": event.card_id,
                "card_name": event.card_name,
                "source_card_id": source_id,
                "source_card_name": source_name or (source_card.name if source_card else ""),
                "dest_list": event.to_list_name,
                "dest_group": dest_group,
                "actor_name": event.actor_name,
                "copied_at": isoformat(event.at),
                "flags": flags,
                "reason": " ".join(reasons),
                "source_lineage": lineage,
            }
        )

    alerts.sort(
        key=lambda item: (
            {"high": 0, "medium": 1, "low": 2}.get(item["score"], 9),
            item.get("copied_at") or "",
        )
    )

    summary = {
        "copies_in_period": len(copies),
        "whitelisted_copies_count": whitelisted,
        "cross_board_copies_count": cross_board_copies,
        "same_board_copies_evaluated": max(0, len(copies) - whitelisted),
        "alerts_count": len(alerts),
        "high_count": sum(1 for item in alerts if item["score"] == "high"),
        "medium_count": sum(1 for item in alerts if item["score"] == "medium"),
        "low_count": sum(1 for item in alerts if item["score"] == "low"),
    }

    return {
        "summary": summary,
        "alerts": alerts,
        "whitelisted_copies_count": whitelisted,
        "cross_board_copies_count": cross_board_copies,
    }


def _source_known_on_board(
    source_id: str | None,
    source_card: TrelloCard | None,
    source_events: list[MovementEvent],
) -> bool:
    """True se a fonte ja existiu neste board (card vivo/arquivado ou actions locais)."""
    if source_card is not None:
        return True
    if not source_id:
        return False
    return any(
        event.event_type in {"created", "copied", "moved", "deleted", "archived", "unarchived"}
        for event in source_events
    )


def _is_whitelisted_copy(
    source_card: TrelloCard | None,
    source_name: str,
    workflow: WorkflowConfig,
) -> bool:
    if source_card and source_card.is_template:
        return True
    if workflow.is_antifraud_template_name(source_name):
        return True
    if source_card and workflow.is_antifraud_template_name(source_card.name):
        return True
    return False


def _source_lineage(
    source_id: str | None,
    source_name: str,
    source_card: TrelloCard | None,
    timeline: CardTimeline | None,
    source_events: list[MovementEvent],
    workflow: WorkflowConfig,
    copy_at: Any,
) -> dict[str, Any]:
    terminal_groups = workflow.antifraud_terminal_groups()
    ordered = sorted(source_events, key=lambda item: item.at)
    dispose_event = next(
        (event for event in ordered if event.event_type in _DISPOSAL_EVENTS),
        None,
    )
    disposed_at = dispose_event.at if dispose_event else None
    disposal = dispose_event.event_type if dispose_event else None
    if disposal is None and source_card and source_card.closed:
        disposal = "archived"
        disposed_at = source_card.date_closed

    # Inclui movimentos ate a copia + exclusao/arquivamento posterior.
    relevant: list[MovementEvent] = []
    for event in ordered:
        if event.event_type in _DISPOSAL_EVENTS:
            relevant.append(event)
            continue
        if copy_at and event.at and event.at > copy_at:
            continue
        relevant.append(event)
    relevant = sorted(relevant, key=lambda item: item.at)

    visits: list[dict[str, Any]] = []
    groups_seen: list[str] = []
    last_list_at_or_before_copy: str | None = None
    last_group_at_or_before_copy: str | None = None

    for event in relevant:
        list_name = event.to_list_name or event.from_list_name
        group = workflow.group_for_list(list_name) if list_name else None
        if group and (not groups_seen or groups_seen[-1] != group):
            groups_seen.append(group)
        if list_name and (not copy_at or not event.at or event.at <= copy_at):
            last_list_at_or_before_copy = list_name
            last_group_at_or_before_copy = group
        visits.append(
            {
                "at": isoformat(event.at),
                "event_type": event.event_type,
                "list_name": list_name,
                "group": group,
                "actor_name": event.actor_name,
                "after_copy": bool(copy_at and event.at and event.at > copy_at),
            }
        )

    last_list_at_dispose = None
    last_group_at_dispose = None
    if dispose_event:
        last_list_at_dispose = dispose_event.to_list_name or dispose_event.from_list_name
        if last_list_at_dispose:
            last_group_at_dispose = workflow.group_for_list(last_list_at_dispose)
            if not last_list_at_or_before_copy:
                last_list_at_or_before_copy = last_list_at_dispose
                last_group_at_or_before_copy = last_group_at_dispose
            if last_group_at_dispose and last_group_at_dispose not in groups_seen:
                groups_seen.append(last_group_at_dispose)
    elif source_card and source_card.closed and source_card.current_list_name:
        last_list_at_dispose = source_card.current_list_name
        last_group_at_dispose = workflow.group_for_list(last_list_at_dispose)
        if not last_list_at_or_before_copy:
            last_list_at_or_before_copy = last_list_at_dispose
            last_group_at_or_before_copy = last_group_at_dispose

    seconds_copy_to_dispose = None
    if copy_at and disposed_at:
        seconds_copy_to_dispose = max(0, int((disposed_at - copy_at).total_seconds()))

    passed_terminal = False
    if timeline:
        for stage in timeline.stage_timeline:
            if stage.group in terminal_groups:
                if not copy_at or not stage.start_at or stage.start_at <= copy_at:
                    passed_terminal = True
                    break
    if not passed_terminal:
        passed_terminal = any(group in terminal_groups for group in groups_seen)

    history_complete = bool(
        any(event.event_type in {"created", "copied", "moved"} for event in relevant)
    )
    if disposal == "deleted":
        status = "deleted" if history_complete else "deleted_partial_history"
    elif disposal == "archived":
        status = "archived" if history_complete or (source_card and source_card.closed) else "archived_partial_history"
    elif source_card:
        status = "alive"
    elif visits:
        status = "missing_from_snapshot"
    else:
        status = "missing_history"

    recovery_note = None
    if status in {"deleted_partial_history", "archived_partial_history"}:
        action_name = "deleteCard" if disposal == "deleted" else "updateCard:closed"
        recovery_note = (
            f"Trello nao reteve updateCard:idList da fonte; recuperamos a ultima coluna "
            f"pelo {action_name} (lista no momento da {('exclusao' if disposal == 'deleted' else 'arquivamento')}) "
            "e a janela copia->descarte."
        )
    elif status == "missing_history":
        recovery_note = (
            "Nao ha actions residuais da fonte no board; impossivel reconstruir colunas anteriores."
        )

    rapid = bool(seconds_copy_to_dispose is not None and seconds_copy_to_dispose <= 120)
    disposed_iso = isoformat(disposed_at) if disposed_at else None

    return {
        "status": status,
        "source_card_id": source_id,
        "source_card_name": source_name or (source_card.name if source_card else ""),
        "passed_terminal": passed_terminal,
        "groups_visited": groups_seen,
        "last_list_at_copy": last_list_at_or_before_copy,
        "last_group_at_copy": last_group_at_or_before_copy,
        "disposal": disposal,
        "last_list_at_dispose": last_list_at_dispose,
        "last_group_at_dispose": last_group_at_dispose,
        "disposed_at": disposed_iso,
        "seconds_copy_to_dispose": seconds_copy_to_dispose,
        "rapid_copy_dispose": rapid,
        # Aliases legados (UI/PDF/IA)
        "last_list_at_delete": last_list_at_dispose,
        "last_group_at_delete": last_group_at_dispose,
        "deleted_at": disposed_iso if disposal == "deleted" else None,
        "archived_at": disposed_iso if disposal == "archived" else None,
        "seconds_copy_to_delete": seconds_copy_to_dispose,
        "rapid_copy_delete": rapid,
        "recovery_note": recovery_note,
        "visits": visits[:40],
        "visits_count": len(visits),
    }
