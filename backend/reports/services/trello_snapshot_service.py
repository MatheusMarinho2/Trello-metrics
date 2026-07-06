from __future__ import annotations

from dataclasses import asdict
from typing import Any

from reports.models import (
    Collaborator,
    GeneratedReport,
    TrelloBoardSnapshot,
    TrelloCardRecord,
    TrelloCustomFieldChangeRecord,
    TrelloListRecord,
    TrelloMovementRecord,
)
from reports.utils.text import normalize_name
from trello_metrics.domain.models import (
    BoardData,
    CardDescriptionData,
    CustomFieldChange,
    MovementEvent,
    PausaDetail,
    RetornoDetail,
    TrelloCard,
    TrelloList,
)
from trello_metrics.utils.dates import isoformat, parse_trello_datetime


COLLABORATOR_FIELDS = (
    "Solicitante",
    "Desenvolvedor",
    "Revisor em Par",
    "Revisor",
    "Tester",
)


class TrelloSnapshotService:
    def persist_board(self, board: BoardData, source: str = "api") -> TrelloBoardSnapshot:
        snapshot = TrelloBoardSnapshot.objects.create(
            board_id=board.id,
            name=board.name,
            url=board.url,
            source=source,
            raw_payload=board.raw,
            cards_count=len(board.cards),
            movements_count=len(board.movements),
            custom_field_changes_count=len(board.custom_field_changes),
        )

        TrelloListRecord.objects.bulk_create(
            [
                TrelloListRecord(
                    snapshot=snapshot,
                    trello_id=item.id,
                    name=item.name,
                    closed=item.closed,
                    pos=float(item.pos) if item.pos is not None else None,
                    color=item.color or "",
                )
                for item in board.lists.values()
            ],
            batch_size=500,
        )
        TrelloCardRecord.objects.bulk_create(
            [
                TrelloCardRecord(
                    snapshot=snapshot,
                    trello_id=card.id,
                    name=card.name,
                    current_list_id=card.current_list_id or "",
                    current_list_name=card.current_list_name or "",
                    closed=card.closed,
                    is_template=card.is_template,
                    created_at_trello=card.created_at,
                    date_closed=card.date_closed,
                    date_last_activity=card.date_last_activity,
                    url=card.url,
                    id_short=card.id_short,
                    labels=card.labels,
                    custom_fields=card.custom_fields,
                    description_data=_description_to_json(card.description_data),
                    raw=card.raw,
                )
                for card in board.cards
            ],
            batch_size=500,
        )
        TrelloMovementRecord.objects.bulk_create(
            [
                TrelloMovementRecord(
                    snapshot=snapshot,
                    card_id=event.card_id,
                    card_name=event.card_name,
                    at=event.at,
                    event_type=event.event_type,
                    from_list_id=event.from_list_id or "",
                    from_list_name=event.from_list_name or "",
                    to_list_id=event.to_list_id or "",
                    to_list_name=event.to_list_name or "",
                    actor_id=event.actor_id or "",
                    actor_name=event.actor_name or "",
                    action_id=event.action_id or "",
                )
                for event in board.movements
            ],
            batch_size=1000,
        )
        TrelloCustomFieldChangeRecord.objects.bulk_create(
            [
                TrelloCustomFieldChangeRecord(
                    snapshot=snapshot,
                    card_id=change.card_id,
                    card_name=change.card_name,
                    field_name=change.field_name,
                    at=change.at,
                    old_value=change.old_value or "",
                    new_value=change.new_value or "",
                    actor_id=change.actor_id or "",
                    actor_name=change.actor_name or "",
                    action_id=change.action_id or "",
                )
                for change in board.custom_field_changes
            ],
            batch_size=1000,
        )
        sync_collaborators_from_board(board)
        return snapshot

    def load_board(self, snapshot: TrelloBoardSnapshot) -> BoardData:
        lists = {
            item.trello_id: TrelloList(
                id=item.trello_id,
                name=item.name,
                closed=item.closed,
                pos=item.pos,
                color=item.color or None,
            )
            for item in snapshot.lists.all()
        }
        cards = [
            TrelloCard(
                id=item.trello_id,
                name=item.name,
                current_list_id=item.current_list_id or None,
                current_list_name=item.current_list_name,
                closed=item.closed,
                is_template=item.is_template,
                created_at=item.created_at_trello,
                date_closed=item.date_closed,
                date_last_activity=item.date_last_activity,
                url=item.url,
                id_short=item.id_short,
                labels=item.labels or [],
                custom_fields=item.custom_fields or {},
                description_data=_description_from_json(item.description_data or {}),
                raw=item.raw or {},
            )
            for item in snapshot.cards.all()
        ]
        movements = [
            MovementEvent(
                card_id=item.card_id,
                card_name=item.card_name,
                at=item.at,
                event_type=item.event_type,
                from_list_id=item.from_list_id or None,
                from_list_name=item.from_list_name or None,
                to_list_id=item.to_list_id or None,
                to_list_name=item.to_list_name or None,
                actor_id=item.actor_id or None,
                actor_name=item.actor_name or None,
                action_id=item.action_id or None,
            )
            for item in snapshot.movements.all()
        ]
        changes = [
            CustomFieldChange(
                card_id=item.card_id,
                card_name=item.card_name,
                field_name=item.field_name,
                at=item.at,
                old_value=item.old_value or None,
                new_value=item.new_value or None,
                actor_id=item.actor_id or None,
                actor_name=item.actor_name or None,
                action_id=item.action_id or None,
            )
            for item in snapshot.custom_field_changes.all()
        ]
        return BoardData(
            id=snapshot.board_id,
            name=snapshot.name,
            url=snapshot.url,
            lists=lists,
            cards=cards,
            movements=movements,
            custom_field_changes=changes,
            raw=snapshot.raw_payload or {},
        )


def sync_collaborators_from_saved_reports() -> None:
    discovered: dict[str, set[str]] = {}
    name_keys = ("name", "desenvolvedor", "developer", "tester", "solicitante", "requester", "revisor", "revisor_par")

    for report in GeneratedReport.objects.only("metrics"):
        metrics = report.metrics or {}
        for section in ("collaborators", "developers", "testers", "requesters", "reviewers"):
            for row in metrics.get(section) or []:
                if not isinstance(row, dict):
                    continue
                for key in name_keys:
                    _add_discovered(discovered, row.get(key))
                for alias in row.get("aliases") or []:
                    _add_discovered(discovered, alias)

    for card in TrelloCardRecord.objects.only("custom_fields").iterator(chunk_size=500):
        for field in COLLABORATOR_FIELDS:
            _add_discovered(discovered, (card.custom_fields or {}).get(field))

    _upsert_discovered_collaborators(discovered)


def sync_collaborators_from_trello(
    *,
    board_id: str,
    api_key: str,
    token: str,
) -> dict[str, Any]:
    from django.conf import settings

    from reports.clients.trello_client import TrelloApiClient
    from reports.dataclasses.report_config import TrelloSourceConfig
    from trello_metrics.parsers.export_loader import parse_board_export

    resolved_board_id = (board_id or settings.DEFAULT_TRELLO_BOARD_ID or "").strip()
    if not resolved_board_id:
        raise ValueError("Informe o board_id do Trello.")

    config = TrelloSourceConfig(
        board_id=resolved_board_id,
        api_key=(api_key or "").strip(),
        token=(token or "").strip(),
        use_live_api=True,
    )
    payload = TrelloApiClient().fetch_board_export(config)
    board = parse_board_export(payload)
    stats = sync_collaborators_from_board(board)
    collaborators = Collaborator.objects.all()

    return {
        **stats,
        "total": collaborators.count(),
        "board_id": board.id,
        "board_name": board.name,
        "collaborators": collaborators,
    }


def sync_collaborators_from_board(board: BoardData) -> dict[str, int]:
    discovered: dict[str, set[str]] = {}
    for member in (board.raw or {}).get("members") or []:
        for value in (member.get("fullName"), member.get("username")):
            _add_discovered(discovered, value)
    for card in board.cards:
        for field in COLLABORATOR_FIELDS:
            _add_discovered(discovered, card.custom_fields.get(field))

    return _upsert_discovered_collaborators(discovered)


def _upsert_discovered_collaborators(discovered: dict[str, set[str]]) -> dict[str, int]:
    created = 0
    updated = 0
    for normalized, aliases in discovered.items():
        name = sorted(aliases, key=len, reverse=True)[0]
        collaborator, was_created = Collaborator.objects.get_or_create(
            name=name,
            defaults={"aliases": sorted(aliases), "source": "trello", "active": True},
        )
        if was_created:
            created += 1
            continue
        current_aliases = set(collaborator.aliases or [])
        current_aliases.update(aliases)
        if current_aliases != set(collaborator.aliases or []):
            collaborator.aliases = sorted(current_aliases)
            collaborator.save(update_fields=["aliases", "updated_at"])
            updated += 1
    return {"created": created, "updated": updated, "discovered": len(discovered)}


def active_collaborator_names() -> set[str]:
    names: set[str] = set()
    for collaborator in Collaborator.objects.filter(active=True):
        names.add(normalize_name(collaborator.name))
        for alias in collaborator.aliases or []:
            names.add(normalize_name(alias))
    return {name for name in names if name}


def inactive_collaborator_names() -> set[str]:
    names: set[str] = set()
    for collaborator in Collaborator.objects.filter(active=False):
        names.add(normalize_name(collaborator.name))
        for alias in collaborator.aliases or []:
            names.add(normalize_name(alias))
    return {name for name in names if name}


def _add_discovered(discovered: dict[str, set[str]], value: str | None) -> None:
    normalized = normalize_name(value)
    if not normalized or normalized.startswith("nao informado") or normalized.startswith("sem "):
        return
    discovered.setdefault(normalized, set()).add((value or "").strip())


def _description_to_json(description: CardDescriptionData) -> dict[str, Any]:
    data = asdict(description)
    for pausa in data.get("pausas", []):
        pausa["momento"] = isoformat(pausa.get("momento"))
    return data


def _description_from_json(data: dict[str, Any]) -> CardDescriptionData:
    return CardDescriptionData(
        cliente=data.get("cliente", ""),
        solicitacao=data.get("solicitacao", ""),
        solucao_dev=data.get("solucao_dev", ""),
        obs_revisor_par=data.get("obs_revisor_par", ""),
        obs_revisor=data.get("obs_revisor", ""),
        obs_tester=data.get("obs_tester", ""),
        observacoes_gerais=data.get("observacoes_gerais", ""),
        analise_origem=data.get("analise_origem", ""),
        solicitacao_analise=data.get("solicitacao_analise", ""),
        analise_realizada=data.get("analise_realizada", ""),
        recomendacao=data.get("recomendacao", ""),
        retornos=[
            RetornoDetail(
                numero=int(item.get("numero", 0)),
                tipo=item.get("tipo", ""),
                subtipo=item.get("subtipo"),
                motivo=item.get("motivo", ""),
                solucao=item.get("solucao", ""),
            )
            for item in data.get("retornos", [])
        ],
        pausas=[
            PausaDetail(
                numero=int(item.get("numero", 0)),
                momento=parse_trello_datetime(item.get("momento")),
                motivo=item.get("motivo", ""),
            )
            for item in data.get("pausas", [])
        ],
    )
