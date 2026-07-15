from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any

from trello_metrics.config import load_json
from trello_metrics.domain.models import (
    BoardData,
    BoardMoveEvent,
    CustomFieldChange,
    DueChangeEvent,
    MemberEvent,
    MovementEvent,
    TrelloCard,
    TrelloList,
)
from trello_metrics.parsers.description_parser import parse_card_description
from trello_metrics.utils.dates import parse_trello_datetime, trello_id_datetime
from trello_metrics.utils.text import clean_spaces, first_non_empty


def load_board_export(path: str | Path) -> BoardData:
    payload = load_json(path)
    return parse_board_export(payload)


def parse_board_export(payload: dict[str, Any]) -> BoardData:
    lists = _parse_lists(payload.get("lists", []))
    labels_by_id = {
        item.get("id"): clean_spaces(item.get("name"))
        for item in payload.get("labels", [])
        if item.get("id")
    }
    members_by_id = {
        item.get("id"): clean_spaces(item.get("fullName") or item.get("username"))
        for item in payload.get("members", [])
        if item.get("id")
    }
    custom_field_names, custom_field_options = _build_custom_field_indexes(
        payload.get("customFields", [])
    )
    create_dates = _create_dates_by_card(payload.get("actions", []))
    checklists_by_card = _checklists_by_card(payload.get("checklists", []))

    cards = [
        _parse_card(
            card,
            lists,
            labels_by_id,
            custom_field_names,
            custom_field_options,
            create_dates,
            members_by_id,
            checklists_by_card,
        )
        for card in payload.get("cards", [])
    ]
    actions = payload.get("actions", [])
    movements = _parse_movements(actions, lists)
    custom_field_changes = _parse_custom_field_changes(
        actions,
        custom_field_names,
        custom_field_options,
    )
    member_events = _parse_member_events(actions, members_by_id)
    due_changes = _parse_due_changes(actions)
    board_move_events = _parse_board_move_events(actions)
    for event in board_move_events:
        if event.direction != "out":
            continue
        movements.append(
            MovementEvent(
                card_id=event.card_id,
                card_name="",
                at=event.at,
                event_type="archived",
            )
        )
    movements = sorted(movements, key=lambda item: item.at)

    return BoardData(
        id=payload.get("id", ""),
        name=payload.get("name", ""),
        url=payload.get("url", ""),
        lists=lists,
        cards=cards,
        movements=movements,
        custom_field_changes=custom_field_changes,
        member_events=member_events,
        due_changes=due_changes,
        board_move_events=board_move_events,
        raw=payload,
    )


def _parse_lists(raw_lists: list[dict[str, Any]]) -> dict[str, TrelloList]:
    parsed: dict[str, TrelloList] = {}
    for item in raw_lists:
        list_id = item.get("id")
        if not list_id:
            continue
        parsed[list_id] = TrelloList(
            id=list_id,
            name=clean_spaces(item.get("name")),
            closed=bool(item.get("closed", False)),
            pos=item.get("pos"),
            color=item.get("color"),
        )
    return parsed


def _build_custom_field_indexes(
    custom_fields: list[dict[str, Any]],
) -> tuple[dict[str, str], dict[tuple[str, str], str]]:
    field_names: dict[str, str] = {}
    options: dict[tuple[str, str], str] = {}
    for field in custom_fields:
        field_id = field.get("id")
        if not field_id:
            continue
        field_names[field_id] = clean_spaces(field.get("name"))
        for option in field.get("options") or []:
            option_id = option.get("id")
            value = option.get("value") or {}
            if option_id:
                options[(field_id, option_id)] = clean_spaces(value.get("text"))
    return field_names, options


def _create_dates_by_card(actions: list[dict[str, Any]]) -> dict[str, Any]:
    dates: dict[str, Any] = {}
    for action in actions:
        if action.get("type") not in {"createCard", "copyCard"}:
            continue
        card_id = (action.get("data") or {}).get("card", {}).get("id")
        if card_id and card_id not in dates:
            dates[card_id] = parse_trello_datetime(action.get("date"))
    return dates


def _parse_card(
    raw: dict[str, Any],
    lists: dict[str, TrelloList],
    labels_by_id: dict[str, str],
    field_names: dict[str, str],
    field_options: dict[tuple[str, str], str],
    create_dates: dict[str, Any],
    members_by_id: dict[str, str],
    checklists_by_card: dict[str, list[dict[str, Any]]],
) -> TrelloCard:
    list_id = raw.get("idList")
    current_list = lists.get(list_id or "")
    label_names = [
        clean_spaces(label.get("name"))
        for label in raw.get("labels", [])
        if clean_spaces(label.get("name"))
    ]
    for label_id in raw.get("idLabels", []):
        label_name = labels_by_id.get(label_id)
        if label_name and label_name not in label_names:
            label_names.append(label_name)

    member_ids = [str(mid) for mid in (raw.get("idMembers") or []) if mid]
    member_names = [
        members_by_id.get(mid) or mid for mid in member_ids if members_by_id.get(mid) or mid
    ]
    desc = raw.get("desc") or ""
    card_id = raw.get("id", "")
    return TrelloCard(
        id=card_id,
        name=clean_spaces(raw.get("name")),
        current_list_id=list_id,
        current_list_name=current_list.name if current_list else "",
        closed=bool(raw.get("closed", False)),
        is_template=bool(raw.get("isTemplate", False)),
        created_at=create_dates.get(card_id) or trello_id_datetime(card_id),
        date_closed=parse_trello_datetime(raw.get("dateClosed") or raw.get("dateCompleted")),
        date_last_activity=parse_trello_datetime(raw.get("dateLastActivity")),
        url=raw.get("url") or raw.get("shortUrl") or "",
        id_short=raw.get("idShort"),
        labels=label_names,
        custom_fields=_parse_custom_field_items(raw, field_names, field_options),
        description_data=parse_card_description(desc),
        raw=raw,
        member_ids=member_ids,
        member_names=member_names,
        due=parse_trello_datetime(raw.get("due")),
        start=parse_trello_datetime(raw.get("start")),
        checklists=checklists_by_card.get(card_id, []),
        desc_length=len(clean_spaces(desc)),
    )


def _checklists_by_card(raw_checklists: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    by_card: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for checklist in raw_checklists or []:
        card_id = checklist.get("idCard")
        if not card_id:
            continue
        items = []
        for item in checklist.get("checkItems") or []:
            items.append(
                {
                    "name": clean_spaces(item.get("name")),
                    "state": item.get("state") or "incomplete",
                }
            )
        by_card[card_id].append(
            {
                "name": clean_spaces(checklist.get("name")),
                "items": items,
            }
        )
    return by_card


def _parse_custom_field_items(
    card: dict[str, Any],
    field_names: dict[str, str],
    field_options: dict[tuple[str, str], str],
) -> dict[str, str]:
    values: dict[str, str] = {}
    for item in card.get("customFieldItems") or []:
        field_id = item.get("idCustomField")
        field_name = field_names.get(field_id or "")
        if not field_name:
            continue

        id_value = item.get("idValue")
        option_text = field_options.get((field_id, id_value)) if id_value else None
        value = option_text or _value_from_custom_field_item(item)
        if value:
            values[field_name] = value
            # Store an accentless alias because Trello exports can vary by source.
            if field_name == "Nível":
                values.setdefault("Nivel", value)
            if field_name == "Nível (Analise)":
                values.setdefault("Nivel (Analise)", value)
    return values


def _value_from_custom_field_item(item: dict[str, Any]) -> str:
    value = item.get("value") or {}
    return first_non_empty(
        value.get("text"),
        value.get("number"),
        value.get("date"),
        value.get("checked"),
    )


def _parse_movements(
    actions: list[dict[str, Any]],
    lists: dict[str, TrelloList],
) -> list[MovementEvent]:
    movements: list[MovementEvent] = []
    for action in actions:
        action_type = action.get("type")
        data = action.get("data") or {}
        card = data.get("card") or {}
        card_id = card.get("id")
        action_at = parse_trello_datetime(action.get("date"))
        if not card_id or not action_at:
            continue

        if action_type == "createCard":
            target = _list_from_action_ref(data.get("list"), lists)
            movements.append(
                _movement_from_action(
                    action,
                    event_type="created",
                    at=action_at,
                    card=card,
                    to_list=target,
                )
            )
            continue

        if action_type == "convertToCardFromCheckItem":
            target = _list_from_action_ref(data.get("list"), lists)
            movements.append(
                _movement_from_action(
                    action,
                    event_type="created",
                    at=action_at,
                    card=card,
                    to_list=target,
                )
            )
            continue

        if action_type == "copyCard":
            target = _list_from_action_ref(data.get("list"), lists)
            source = data.get("cardSource") or {}
            movements.append(
                _movement_from_action(
                    action,
                    event_type="copied",
                    at=action_at,
                    card=card,
                    to_list=target,
                    source_card_id=source.get("id"),
                    source_card_name=clean_spaces(source.get("name")),
                )
            )
            continue

        if action_type == "deleteCard":
            target = _list_from_action_ref(data.get("list"), lists)
            movements.append(
                _movement_from_action(
                    action,
                    event_type="deleted",
                    at=action_at,
                    card=card,
                    to_list=target,
                    from_list=target,
                )
            )
            continue

        if action_type == "updateCard" and "closed" in (data.get("old") or {}):
            target = _list_from_action_ref(data.get("list"), lists)
            card_closed = bool(card.get("closed", False))
            movements.append(
                _movement_from_action(
                    action,
                    event_type="archived" if card_closed else "unarchived",
                    at=action_at,
                    card=card,
                    to_list=target,
                    from_list=target,
                )
            )
            continue

        if action_type != "updateCard" or not _is_list_movement(data):
            continue

        source = _list_from_action_ref(data.get("listBefore"), lists)
        target = _list_from_action_ref(data.get("listAfter"), lists)

        old_id = (data.get("old") or {}).get("idList")
        if not source and old_id:
            source = _list_from_id(old_id, lists)

        if not target:
            target = _list_from_action_ref(data.get("list"), lists)
        if not target and card.get("idList"):
            target = _list_from_id(card.get("idList"), lists)

        if not source and not target:
            continue

        movements.append(
            _movement_from_action(
                action,
                event_type="moved",
                at=action_at,
                card=card,
                from_list=source,
                to_list=target,
            )
        )

    return sorted(movements, key=lambda item: item.at)


def _parse_custom_field_changes(
    actions: list[dict[str, Any]],
    field_names: dict[str, str],
    field_options: dict[tuple[str, str], str],
) -> list[CustomFieldChange]:
    changes: list[CustomFieldChange] = []
    for action in actions:
        if action.get("type") != "updateCustomFieldItem":
            continue
        data = action.get("data") or {}
        card = data.get("card") or {}
        card_id = card.get("id")
        action_at = parse_trello_datetime(action.get("date"))
        if not card_id or not action_at:
            continue

        field_ref = data.get("customField") or {}
        field_id = field_ref.get("id")
        field_name = field_names.get(field_id or "") or clean_spaces(field_ref.get("name"))
        if not field_name:
            continue

        member = action.get("memberCreator") or {}
        changes.append(
            CustomFieldChange(
                card_id=card_id,
                card_name=clean_spaces(card.get("name")),
                field_name=field_name,
                at=action_at,
                old_value=_custom_field_change_value(
                    data.get("old") or {},
                    field_id,
                    field_options,
                ),
                new_value=_custom_field_change_value(
                    data.get("customFieldItem") or {},
                    field_id,
                    field_options,
                ),
                actor_id=member.get("id") or action.get("idMemberCreator"),
                actor_name=first_non_empty(member.get("fullName"), member.get("username")),
                action_id=action.get("id"),
            )
        )
    return sorted(changes, key=lambda item: item.at)


def _custom_field_change_value(
    item: dict[str, Any],
    field_id: str | None,
    field_options: dict[tuple[str, str], str],
) -> str | None:
    id_value = item.get("idValue")
    if field_id and id_value:
        option = field_options.get((field_id, id_value))
        if option:
            return option
    value = _value_from_custom_field_item(item)
    return value or None


def _parse_member_events(
    actions: list[dict[str, Any]],
    members_by_id: dict[str, str],
) -> list[MemberEvent]:
    events: list[MemberEvent] = []
    for action in actions:
        action_type = action.get("type")
        if action_type not in {"addMemberToCard", "removeMemberFromCard"}:
            continue
        data = action.get("data") or {}
        card_id = (data.get("card") or {}).get("id")
        at = parse_trello_datetime(action.get("date"))
        member = data.get("member") or {}
        member_id = member.get("id") or ""
        member_name = clean_spaces(member.get("name")) or members_by_id.get(member_id, "")
        if not card_id or not at:
            continue
        member_creator = action.get("memberCreator") or {}
        events.append(
            MemberEvent(
                card_id=card_id,
                at=at,
                member_id=member_id,
                member_name=member_name,
                op="add" if action_type == "addMemberToCard" else "remove",
                actor_id=member_creator.get("id"),
                actor_name=clean_spaces(member_creator.get("fullName")),
            )
        )
    return sorted(events, key=lambda item: item.at)


def _parse_due_changes(actions: list[dict[str, Any]]) -> list[DueChangeEvent]:
    events: list[DueChangeEvent] = []
    for action in actions:
        if action.get("type") != "updateCard":
            continue
        data = action.get("data") or {}
        old = data.get("old") or {}
        if "due" not in old and "due" not in (data.get("card") or {}):
            continue
        if "due" not in old:
            continue
        card = data.get("card") or {}
        card_id = card.get("id")
        at = parse_trello_datetime(action.get("date"))
        if not card_id or not at:
            continue
        member_creator = action.get("memberCreator") or {}
        events.append(
            DueChangeEvent(
                card_id=card_id,
                at=at,
                old_due=parse_trello_datetime(old.get("due")),
                new_due=parse_trello_datetime(card.get("due")),
                actor_id=member_creator.get("id"),
                actor_name=clean_spaces(member_creator.get("fullName")),
            )
        )
    return sorted(events, key=lambda item: item.at)


def _parse_board_move_events(actions: list[dict[str, Any]]) -> list[BoardMoveEvent]:
    events: list[BoardMoveEvent] = []
    for action in actions:
        action_type = action.get("type")
        if action_type not in {"moveCardToBoard", "moveCardFromBoard"}:
            continue
        data = action.get("data") or {}
        card_id = (data.get("card") or {}).get("id")
        at = parse_trello_datetime(action.get("date"))
        if not card_id or not at:
            continue
        board = data.get("board") or data.get("boardTarget") or data.get("boardSource") or {}
        events.append(
            BoardMoveEvent(
                card_id=card_id,
                at=at,
                direction="in" if action_type == "moveCardToBoard" else "out",
                other_board_id=board.get("id") or "",
                other_board_name=clean_spaces(board.get("name")),
            )
        )
    return sorted(events, key=lambda item: item.at)


def _is_list_movement(data: dict[str, Any]) -> bool:
    old = data.get("old") or {}
    return bool(
        data.get("listBefore")
        or data.get("listAfter")
        or old.get("idList")
        or (data.get("card") or {}).get("idList")
    )


def _list_from_action_ref(
    ref: dict[str, Any] | None,
    lists: dict[str, TrelloList],
) -> TrelloList | None:
    if not ref:
        return None
    list_id = ref.get("id")
    if list_id and list_id in lists:
        return lists[list_id]
    if list_id or ref.get("name"):
        return TrelloList(id=list_id or "", name=clean_spaces(ref.get("name")))
    return None


def _list_from_id(list_id: str | None, lists: dict[str, TrelloList]) -> TrelloList | None:
    if not list_id:
        return None
    return lists.get(list_id) or TrelloList(id=list_id, name="")


def _movement_from_action(
    action: dict[str, Any],
    event_type: str,
    at: Any,
    card: dict[str, Any],
    from_list: TrelloList | None = None,
    to_list: TrelloList | None = None,
    source_card_id: str | None = None,
    source_card_name: str | None = None,
) -> MovementEvent:
    member = action.get("memberCreator") or {}
    return MovementEvent(
        card_id=card.get("id", ""),
        card_name=clean_spaces(card.get("name")),
        at=at,
        event_type=event_type,
        from_list_id=from_list.id if from_list else None,
        from_list_name=from_list.name if from_list else None,
        to_list_id=to_list.id if to_list else None,
        to_list_name=to_list.name if to_list else None,
        actor_id=member.get("id") or action.get("idMemberCreator"),
        actor_name=first_non_empty(member.get("fullName"), member.get("username")),
        action_id=action.get("id"),
        source_card_id=source_card_id or None,
        source_card_name=source_card_name or None,
    )


def movements_by_card(movements: list[MovementEvent]) -> dict[str, list[MovementEvent]]:
    grouped: dict[str, list[MovementEvent]] = defaultdict(list)
    for movement in movements:
        grouped[movement.card_id].append(movement)
    return dict(grouped)
