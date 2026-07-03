from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class TrelloList:
    id: str
    name: str
    closed: bool = False
    pos: float | int | None = None
    color: str | None = None


@dataclass(frozen=True)
class RetornoDetail:
    numero: int
    tipo: str
    subtipo: str | None
    motivo: str
    solucao: str


@dataclass(frozen=True)
class PausaDetail:
    numero: int
    momento: datetime | None
    motivo: str


@dataclass
class CardDescriptionData:
    cliente: str = ""
    solicitacao: str = ""
    solucao_dev: str = ""
    obs_revisor_par: str = ""
    obs_revisor: str = ""
    obs_tester: str = ""
    observacoes_gerais: str = ""
    analise_origem: str = ""
    solicitacao_analise: str = ""
    analise_realizada: str = ""
    recomendacao: str = ""
    retornos: list[RetornoDetail] = field(default_factory=list)
    pausas: list[PausaDetail] = field(default_factory=list)


@dataclass
class TrelloCard:
    id: str
    name: str
    current_list_id: str | None
    current_list_name: str
    closed: bool = False
    is_template: bool = False
    created_at: datetime | None = None
    date_closed: datetime | None = None
    date_last_activity: datetime | None = None
    url: str = ""
    id_short: int | None = None
    labels: list[str] = field(default_factory=list)
    custom_fields: dict[str, str] = field(default_factory=dict)
    description_data: CardDescriptionData = field(default_factory=CardDescriptionData)
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class MovementEvent:
    card_id: str
    card_name: str
    at: datetime
    event_type: str
    from_list_id: str | None = None
    from_list_name: str | None = None
    to_list_id: str | None = None
    to_list_name: str | None = None
    actor_id: str | None = None
    actor_name: str | None = None
    action_id: str | None = None


@dataclass(frozen=True)
class CustomFieldChange:
    card_id: str
    card_name: str
    field_name: str
    at: datetime
    old_value: str | None = None
    new_value: str | None = None
    actor_id: str | None = None
    actor_name: str | None = None
    action_id: str | None = None


@dataclass
class BoardData:
    id: str
    name: str
    url: str
    lists: dict[str, TrelloList]
    cards: list[TrelloCard]
    movements: list[MovementEvent]
    custom_field_changes: list[CustomFieldChange] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)
