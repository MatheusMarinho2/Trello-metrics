from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from trello_metrics.domain.models import MovementEvent, PausaDetail, RetornoDetail, TrelloCard
from trello_metrics.domain.workflow import WorkflowConfig
from trello_metrics.utils.dates import hours_between, human_hours, isoformat
from trello_metrics.utils.fibonacci import parse_fibonacci_level
from trello_metrics.utils.period import MonthPeriod
from trello_metrics.utils.text import normalize_key, strip_accents


@dataclass
class GroupSpan:
    group: str
    hours: float = 0.0
    visits: int = 0


@dataclass
class RetornoHistoryEntry:
    numero: int
    tipo: str
    subtipo: str | None
    motivo: str
    solucao: str
    at: datetime | None
    atribuido_a: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "numero": self.numero,
            "tipo": self.tipo,
            "subtipo": self.subtipo,
            "motivo": self.motivo,
            "solucao": self.solucao,
            "at": isoformat(self.at),
            "atribuido_a": self.atribuido_a,
        }


@dataclass
class StageTimelineEntry:
    group: str
    title: str
    list_name: str
    hours: float
    start_at: datetime | None
    end_at: datetime | None
    excluded_from_flow_metrics: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "group": self.group,
            "title": self.title,
            "list_name": self.list_name,
            "hours": round(self.hours, 6),
            "hours_human": human_hours(self.hours),
            "start_at": isoformat(self.start_at),
            "end_at": isoformat(self.end_at),
            "excluded_from_flow_metrics": self.excluded_from_flow_metrics,
        }


@dataclass
class CardTimeline:
    card_id: str
    card_name: str
    kind: str
    sistema: str
    desenvolvedor: str
    revisor_par: str
    revisor: str
    tester: str
    solicitante: str
    prioridade: str
    labels: list[str]
    fibonacci_level: int | None
    delivered_at: datetime | None
    created_at: datetime | None
    closed_at: datetime | None = None
    group_hours: dict[str, float] = field(default_factory=dict)
    group_visits: dict[str, int] = field(default_factory=dict)
    peer_review_returns: int = 0
    return_dev_count: int = 0
    return_sup_count: int = 0
    pause_count: int = 0
    accepted_without_dev_return: bool = True
    peer_review_sent_back: bool = False
    transitions: list[tuple[str, str]] = field(default_factory=list)
    retornos: list[RetornoDetail] = field(default_factory=list)
    pausas: list[PausaDetail] = field(default_factory=list)
    retorno_history: list[RetornoHistoryEntry] = field(default_factory=list)
    passed_peer_review: bool = False
    passed_formal_review: bool = False
    double_review_required: bool = False
    double_review_recommended: bool = False
    return_dev_by_teste_count: int = 0
    return_dev_by_revisao_count: int = 0
    gestor_premature_approval: bool = False
    dev_to_sup_return_count: int = 0
    developer_penalty_return_count: int = 0
    test_return_missing_reason_count: int = 0
    test_cycles: int = 0
    tester_returned_dev: bool = False
    passed_test_phase: bool = False
    descricao: dict[str, str] = field(default_factory=dict)
    stage_timeline: list[StageTimelineEntry] = field(default_factory=list)
    dev_work_hours: float = 0.0
    pipeline_wait_hours: float = 0.0
    flow_hours_until_delivery: float = 0.0
    metric_cycle_hours: float | None = None
    # Vida util real do card: criacao ate fechamento (ou agora, se ainda aberto).
    lead_time_hours: float = 0.0
    terminal_reached_at: datetime | None = None
    terminal_group: str = ""
    return_after_terminal: bool = False
    return_after_terminal_events: list[dict[str, Any]] = field(default_factory=list)
    used_direct_production: bool = False

    @property
    def retest_cycles(self) -> int:
        return max(0, self.test_cycles - 1)

    @property
    def double_review_done(self) -> bool:
        return self.passed_peer_review and self.passed_formal_review

    @property
    def double_review_violation(self) -> bool:
        return self.double_review_required and not self.double_review_done

    @property
    def dev_hours(self) -> float:
        return self.group_hours.get("development", 0.0)

    @property
    def peer_review_hours(self) -> float:
        return (
            self.group_hours.get("peer_review", 0.0)
            + self.group_hours.get("waiting_peer_review", 0.0)
        )

    @property
    def test_hours(self) -> float:
        return (
            self.group_hours.get("testing", 0.0)
            + self.group_hours.get("waiting_test", 0.0)
        )

    @property
    def pause_hours(self) -> float:
        return self.group_hours.get("paused", 0.0)

    def is_delivered_in(self, period: MonthPeriod) -> bool:
        return period.contains(self.delivered_at)

    def is_created_in(self, period: MonthPeriod) -> bool:
        return period.contains(self.created_at)

    def is_active_in(self, period: MonthPeriod) -> bool:
        """Card teve atividade relevante no periodo: foi criado, entregue, teve
        retorno/pausa registrado ou foi fechado dentro do intervalo do mes."""
        if self.is_created_in(period) or self.is_delivered_in(period):
            return True
        if period.contains(self.closed_at):
            return True
        if any(period.contains(entry.at) for entry in self.retorno_history):
            return True
        if any(period.contains(pausa.momento) for pausa in self.pausas):
            return True
        return False

    @property
    def cycle_time_hours(self) -> float | None:
        if not self.delivered_at or not self.created_at:
            return None
        return hours_between(self.created_at, self.delivered_at)

    def to_dict(self) -> dict[str, Any]:
        return {
            "card_id": self.card_id,
            "card_name": self.card_name,
            "kind": self.kind,
            "sistema": self.sistema,
            "desenvolvedor": self.desenvolvedor,
            "revisor_par": self.revisor_par,
            "revisor": self.revisor,
            "tester": self.tester,
            "solicitante": self.solicitante,
            "prioridade": self.prioridade,
            "labels": list(self.labels),
            "fibonacci_level": self.fibonacci_level,
            "delivered_at": isoformat(self.delivered_at),
            "created_at": isoformat(self.created_at),
            "dev_hours": self.dev_hours,
            "peer_review_hours": self.peer_review_hours,
            "test_hours": self.test_hours,
            "pause_hours": self.pause_hours,
            "group_hours": dict(self.group_hours),
            "peer_review_returns": self.peer_review_returns,
            "return_dev_count": self.return_dev_count,
            "return_sup_count": self.return_sup_count,
            "gestor_premature_approval": self.gestor_premature_approval,
            "dev_to_sup_return_count": self.dev_to_sup_return_count,
            "accepted_without_dev_return": self.accepted_without_dev_return,
            "peer_review_sent_back": self.peer_review_sent_back,
            "lead_time_hours": self.lead_time_hours,
            "closed_at": isoformat(self.closed_at),
            "pause_count": self.pause_count,
            "passed_peer_review": self.passed_peer_review,
            "passed_formal_review": self.passed_formal_review,
            "double_review_required": self.double_review_required,
            "double_review_recommended": self.double_review_recommended,
            "double_review_done": self.double_review_done,
            "double_review_violation": self.double_review_violation,
            "return_dev_by_teste_count": self.return_dev_by_teste_count,
            "return_dev_by_revisao_count": self.return_dev_by_revisao_count,
            "developer_penalty_return_count": self.developer_penalty_return_count,
            "test_return_missing_reason_count": self.test_return_missing_reason_count,
            "test_cycles": self.test_cycles,
            "retest_cycles": self.retest_cycles,
            "tester_returned_dev": self.tester_returned_dev,
            "passed_test_phase": self.passed_test_phase,
            "descricao": dict(self.descricao),
            "etapas": [entry.to_dict() for entry in self.stage_timeline],
            "dev_work_hours": self.dev_work_hours,
            "pipeline_wait_hours": self.pipeline_wait_hours,
            "flow_hours_until_delivery": self.flow_hours_until_delivery,
            "retornos": [item.to_dict() for item in self.retorno_history],
            "pausas": [
                {"numero": item.numero, "at": isoformat(item.momento), "motivo": item.motivo}
                for item in self.pausas
            ],
        }


def build_card_timelines(
    cards: list[TrelloCard],
    events_by_card: dict[str, list[MovementEvent]],
    workflow: WorkflowConfig,
    now: datetime,
) -> list[CardTimeline]:
    timelines: list[CardTimeline] = []
    for card in cards:
        kind = workflow.classify_card(card.name, card.custom_fields, card.labels)
        events = events_by_card.get(card.id, [])
        timelines.append(_build_one(card, kind, events, workflow, now))
    return timelines


def _build_one(
    card: TrelloCard,
    kind: str,
    events: list[MovementEvent],
    workflow: WorkflowConfig,
    now: datetime,
) -> CardTimeline:
    template = workflow.template_for_kind(kind)
    level_field = template.level_field if template else "Nível"
    level_raw = _custom_field(card, level_field)
    if level_raw is None:
        level_raw = card.custom_fields.get("Nivel") or card.custom_fields.get("Nível (Analise)")

    if level_raw is None:
        level_raw = (
            _custom_field(card, "Nivel")
            or _custom_field(card, "NÃ­vel")
            or _custom_field(card, "NÃ­vel (Analise)")
            or _custom_field(card, "Nivel (Analise)")
        )

    timeline = CardTimeline(
        card_id=card.id,
        card_name=card.name,
        kind=kind,
        sistema=_field(card, "Sistema"),
        desenvolvedor=_field(card, "Desenvolvedor"),
        revisor_par=_field(card, "Revisor em Par"),
        revisor=_field(card, "Revisor"),
        tester=_field(card, "Tester"),
        solicitante=_field(card, "Solicitante"),
        prioridade=_field(card, "Prioridade"),
        labels=list(card.labels),
        fibonacci_level=parse_fibonacci_level(level_raw),
        delivered_at=None,
        created_at=card.created_at,
    )

    ordered = sorted(events, key=lambda item: item.at)
    list_spans = _list_spans(card, ordered, now)
    delivery_groups = set(workflow.delivery_groups_for_kind(kind))

    for span in list_spans:
        group = workflow.group_for_list(span["list_name"])
        hours = span["hours"]
        timeline.group_hours[group] = timeline.group_hours.get(group, 0.0) + hours
        timeline.group_visits[group] = timeline.group_visits.get(group, 0) + 1

        if timeline.delivered_at is None and group in delivery_groups:
            timeline.delivered_at = span["start"]

    if timeline.delivered_at is None:
        done_groups = set(workflow.done_groups_for_kind(kind))
        for span in list_spans:
            group = workflow.group_for_list(span["list_name"])
            if group in done_groups:
                timeline.delivered_at = span["start"]
                break

    timeline.stage_timeline = _build_stage_timeline(list_spans, workflow)
    _apply_flow_metrics(timeline, workflow)

    for index, event in enumerate(ordered):
        if event.event_type != "moved":
            continue
        source = workflow.group_for_list(event.from_list_name)
        target = workflow.group_for_list(event.to_list_name)
        timeline.transitions.append((source, target))

        if target == "return_developer":
            timeline.return_dev_count += 1
        if target == "return_support":
            timeline.return_sup_count += 1
            if source == "development":
                timeline.dev_to_sup_return_count += 1
        if target == "paused":
            timeline.pause_count += 1
        if source == "peer_review" and target == "development":
            timeline.peer_review_returns += 1
            timeline.peer_review_sent_back = True

    timeline.gestor_premature_approval = _detect_gestor_premature_approval(timeline.transitions)

    if timeline.delivered_at:
        had_dev_return_before_delivery = _had_return_before(
            ordered, workflow, "return_developer", timeline.delivered_at
        )
        timeline.accepted_without_dev_return = not had_dev_return_before_delivery

    timeline.closed_at = card.date_closed
    timeline.lead_time_hours = hours_between(card.created_at, card.date_closed or now)

    timeline.passed_peer_review = any(
        timeline.group_visits.get(group, 0) > 0 for group in workflow.peer_review_groups()
    )
    timeline.passed_formal_review = any(
        timeline.group_visits.get(group, 0) > 0 for group in workflow.formal_review_groups()
    )
    if timeline.fibonacci_level is not None:
        mandatory_level = workflow.double_review_mandatory_min_level()
        recommended_level = workflow.double_review_recommended_min_level()
        timeline.double_review_required = timeline.fibonacci_level >= mandatory_level
        timeline.double_review_recommended = (
            recommended_level <= timeline.fibonacci_level < mandatory_level
        )

    timeline.retornos = list(card.description_data.retornos)
    timeline.pausas = list(card.description_data.pausas)
    timeline.descricao = _description_fields(card, kind)
    if len(timeline.pausas) > timeline.pause_count:
        timeline.pause_count = len(timeline.pausas)
    timeline.retorno_history = _build_retorno_history(timeline.retornos, ordered, workflow)
    _apply_return_metrics(timeline, ordered, workflow)

    timeline.used_direct_production = timeline.group_visits.get("direct_production", 0) > 0
    (
        timeline.return_after_terminal,
        timeline.return_after_terminal_events,
        timeline.terminal_reached_at,
        timeline.terminal_group,
    ) = _detect_return_after_terminal(ordered, workflow)

    return timeline


def _apply_flow_metrics(timeline: CardTimeline, workflow: WorkflowConfig) -> None:
    cap = timeline.delivered_at
    work_groups = set(workflow.developer_work_groups())
    wait_groups = set(workflow.pipeline_wait_groups())
    excluded_flow = set(workflow.excluded_flow_groups())
    dev_work = 0.0
    pipeline_wait = 0.0
    total = 0.0
    for entry in timeline.stage_timeline:
        if entry.group in excluded_flow:
            continue
        hours = _clipped_stage_hours(entry, cap)
        if hours <= 0:
            continue
        total += hours
        if entry.group in work_groups:
            dev_work += hours
        elif entry.group in wait_groups:
            pipeline_wait += hours
    timeline.dev_work_hours = round(dev_work, 2)
    timeline.pipeline_wait_hours = round(pipeline_wait, 2)
    timeline.flow_hours_until_delivery = round(total, 2)
    flow_start = _metric_flow_start_at(timeline, workflow)
    if timeline.delivered_at and flow_start:
        timeline.metric_cycle_hours = hours_between(flow_start, timeline.delivered_at)
    else:
        timeline.metric_cycle_hours = timeline.cycle_time_hours


def _metric_flow_start_at(timeline: CardTimeline, workflow: WorkflowConfig) -> datetime | None:
    """Inicio do fluxo operacional: saida de planejamento ou primeira etapa fora de pre_flow."""
    pre_flow = set(workflow.pre_flow_groups())
    flow_start = timeline.created_at
    for entry in timeline.stage_timeline:
        if entry.group in pre_flow:
            if entry.end_at:
                flow_start = entry.end_at
            continue
        if entry.start_at:
            return entry.start_at
    return flow_start


def _clipped_stage_hours(entry: StageTimelineEntry, cap_at: datetime | None) -> float:
    if cap_at and entry.start_at and entry.start_at >= cap_at:
        return 0.0
    if cap_at and entry.end_at and entry.end_at > cap_at:
        return hours_between(entry.start_at, cap_at)
    return entry.hours


def _build_stage_timeline(
    list_spans: list[dict[str, Any]],
    workflow: WorkflowConfig,
) -> list[StageTimelineEntry]:
    entries: list[StageTimelineEntry] = []
    excluded_flow = set(workflow.excluded_flow_groups())
    for span in list_spans:
        list_name = span["list_name"]
        group = workflow.group_for_list(list_name)
        entries.append(
            StageTimelineEntry(
                group=group,
                title=workflow.title_for_group(group),
                list_name=list_name,
                hours=span["hours"],
                start_at=span["start"],
                end_at=span["end"],
                excluded_from_flow_metrics=group in excluded_flow,
            )
        )
    return entries


def _description_fields(card: TrelloCard, kind: str) -> dict[str, str]:
    data = card.description_data
    raw = {
        "cliente": data.cliente,
        "solicitacao": data.solicitacao,
        "solucao_dev": data.solucao_dev,
        "obs_revisor_par": data.obs_revisor_par,
        "obs_revisor": data.obs_revisor,
        "obs_tester": data.obs_tester,
        "observacoes_gerais": data.observacoes_gerais,
        "solicitacao_analise": data.solicitacao_analise,
        "analise_realizada": data.analise_realizada,
        "recomendacao": data.recomendacao,
        "analise_origem": data.analise_origem,
    }
    if kind == "analysis" and raw["solicitacao_analise"] and not raw["solicitacao"]:
        raw["solicitacao"] = raw["solicitacao_analise"]
    return {key: value for key, value in raw.items() if value}


def _build_retorno_history(
    retornos: list[RetornoDetail],
    events: list[MovementEvent],
    workflow: WorkflowConfig,
) -> list[RetornoHistoryEntry]:
    """Casa (por ordem cronologica) os blocos de retorno descritos no card com os
    movimentos reais para RETORNO (DEV)/RETORNO (SUP). E uma heuristica best-effort:
    o Trello nao linka estruturalmente um texto de retorno a uma movimentacao especifica.
    """
    dev_returns = [
        (
            event.at,
            workflow.group_for_list(event.from_list_name),
        )
        for event in events
        if event.event_type == "moved"
        and workflow.group_for_list(event.to_list_name) == "return_developer"
    ]
    sup_times = sorted(
        event.at
        for event in events
        if event.event_type == "moved" and workflow.group_for_list(event.to_list_name) == "return_support"
    )

    history: list[RetornoHistoryEntry] = []
    dev_retornos = sorted((item for item in retornos if item.tipo == "dev"), key=lambda item: item.numero)
    sup_retornos = sorted((item for item in retornos if item.tipo == "sup"), key=lambda item: item.numero)

    for index, retorno in enumerate(dev_retornos):
        at = dev_returns[index][0] if index < len(dev_returns) else None
        source_group = dev_returns[index][1] if index < len(dev_returns) else None
        history.append(
            RetornoHistoryEntry(
                numero=retorno.numero,
                tipo="dev",
                subtipo=retorno.subtipo,
                motivo=retorno.motivo,
                solucao=retorno.solucao,
                at=at,
                atribuido_a=_attribute_dev_return(retorno.subtipo, source_group, workflow),
            )
        )
    for index, retorno in enumerate(sup_retornos):
        at = sup_times[index] if index < len(sup_times) else None
        history.append(
            RetornoHistoryEntry(
                numero=retorno.numero,
                tipo="sup",
                subtipo=retorno.subtipo,
                motivo=retorno.motivo,
                solucao=retorno.solucao,
                at=at,
                atribuido_a="suporte",
            )
        )

    far_future = datetime.max.replace(tzinfo=timezone.utc)
    history.sort(key=lambda item: (item.at or far_future, item.tipo, item.numero))
    return history


def _normalize_subtipo(subtipo: str | None) -> str:
    if not subtipo:
        return ""
    return strip_accents(subtipo).lower()


def _attribute_dev_return(
    subtipo: str | None,
    source_group: str | None,
    workflow: WorkflowConfig,
) -> str:
    normalized = _normalize_subtipo(subtipo)
    if "teste" in normalized:
        return "tester"
    if "revis" in normalized:
        return "revisor"

    tester_groups = set(workflow.tester_source_groups())
    reviewer_groups = set(workflow.reviewer_source_groups())
    if source_group in tester_groups:
        return "tester"
    if source_group in reviewer_groups:
        return "revisor"
    return "desconhecido"


def _apply_return_metrics(
    timeline: CardTimeline,
    events: list[MovementEvent],
    workflow: WorkflowConfig,
) -> None:
    dev_return_attributions = _dev_return_event_attributions(
        events,
        workflow,
    )
    timeline.return_dev_by_teste_count = sum(
        1 for _, attributed in dev_return_attributions if attributed == "tester"
    )
    timeline.return_dev_by_revisao_count = sum(
        1 for _, attributed in dev_return_attributions if attributed == "revisor"
    )
    timeline.developer_penalty_return_count = timeline.return_dev_count
    timeline.test_return_missing_reason_count = _test_return_missing_reason_count(
        dev_return_attributions,
        timeline.retorno_history,
    )
    timeline.tester_returned_dev = timeline.return_dev_by_teste_count > 0
    if timeline.delivered_at:
        timeline.accepted_without_dev_return = timeline.developer_penalty_return_count == 0
    timeline.test_cycles = (
        timeline.group_visits.get("waiting_test", 0) + timeline.group_visits.get("testing", 0)
    )
    timeline.passed_test_phase = timeline.test_cycles > 0


def _test_return_missing_reason_count(
    dev_return_attributions: list[tuple[datetime, str]],
    history: list[RetornoHistoryEntry],
) -> int:
    history_by_at = {entry.at: entry for entry in history if entry.tipo == "dev" and entry.at}
    missing = 0
    for at, attributed in dev_return_attributions:
        if attributed != "tester":
            continue
        entry = history_by_at.get(at)
        if entry is None or not clean_return_text(entry.motivo):
            missing += 1
    return missing


def clean_return_text(value: str | None) -> str:
    return "" if value is None else value.strip()


def _dev_return_event_attributions(
    events: list[MovementEvent],
    workflow: WorkflowConfig,
) -> list[tuple[datetime, str]]:
    attributions: list[tuple[datetime, str]] = []
    reviewer_groups = set(workflow.reviewer_source_groups())
    for event in sorted(events, key=lambda item: item.at):
        if event.event_type != "moved":
            continue
        if workflow.group_for_list(event.to_list_name) != "return_developer":
            continue
        source_group = workflow.group_for_list(event.from_list_name)
        if source_group == "testing":
            attributed = "tester"
        elif source_group in reviewer_groups:
            attributed = "revisor"
        else:
            attributed = "desconhecido"
        attributions.append((event.at, attributed))
    return attributions


def _field(card: TrelloCard, name: str) -> str:
    value = _custom_field(card, name)
    if value:
        return value
    return "Nao informado"


def _custom_field(card: TrelloCard, name: str) -> str | None:
    value = card.custom_fields.get(name)
    if value is not None:
        return value
    normalized_name = normalize_key(name)
    for field_name, field_value in card.custom_fields.items():
        if normalize_key(field_name) == normalized_name:
            return field_value
    return None


def _list_spans(
    card: TrelloCard,
    events: list[MovementEvent],
    now: datetime,
) -> list[dict[str, Any]]:
    """Calcula permanencia em cada lista usando estado corrente (from -> to).

    Corrige tempo perdido antes da primeira movimentacao quando createCard/copyCard
    nao aparece no export: ancora em card.created_at e from_list da primeira acao.
    """
    ordered = sorted(events, key=lambda item: item.at)
    lifecycle = [event for event in ordered if event.event_type in {"created", "moved"}]
    if not lifecycle and card.created_at and card.current_list_name:
        return [
            {
                "list_name": card.current_list_name,
                "start": card.created_at,
                "end": card.date_closed or now,
                "hours": hours_between(card.created_at, card.date_closed or now),
            }
        ]

    spans: list[dict[str, Any]] = []
    current_list: str | None = None
    current_start: datetime | None = None

    if lifecycle and lifecycle[0].event_type == "created":
        current_list = lifecycle[0].to_list_name or card.current_list_name
        current_start = lifecycle[0].at
        move_events = lifecycle[1:]
    elif lifecycle:
        current_list = lifecycle[0].from_list_name or card.current_list_name
        current_start = card.created_at or lifecycle[0].at
        move_events = lifecycle
    else:
        return spans

    for event in move_events:
        if event.event_type != "moved":
            continue
        if current_list and current_start and event.at:
            spans.append(
                {
                    "list_name": current_list,
                    "start": current_start,
                    "end": event.at,
                    "hours": hours_between(current_start, event.at),
                }
            )
        current_list = event.to_list_name or current_list
        current_start = event.at

    end = card.date_closed or now
    if current_list and current_start:
        spans.append(
            {
                "list_name": current_list,
                "start": current_start,
                "end": end,
                "hours": hours_between(current_start, end),
            }
        )
    return spans


def _detect_return_after_terminal(
    events: list[MovementEvent],
    workflow: WorkflowConfig,
) -> tuple[bool, list[dict[str, Any]], datetime | None, str]:
    terminal_groups = {"production", "direct_production", "analysis_done"}
    return_groups = {"return_developer", "return_support"}
    terminal_at: datetime | None = None
    terminal_group = ""
    violations: list[dict[str, Any]] = []

    for event in sorted(events, key=lambda item: item.at):
        if event.event_type != "moved" or not event.at:
            continue
        target = workflow.group_for_list(event.to_list_name)
        if terminal_at is None and target in terminal_groups:
            terminal_at = event.at
            terminal_group = target
            continue
        if terminal_at and target in return_groups and event.at >= terminal_at:
            violations.append(
                {
                    "at": isoformat(event.at),
                    "from_list": event.from_list_name,
                    "to_list": event.to_list_name,
                    "target_group": target,
                    "terminal_group": terminal_group,
                }
            )

    return bool(violations), violations, terminal_at, terminal_group


def _detect_gestor_premature_approval(transitions: list[tuple[str, str]]) -> bool:
    """Card foi aprovado pelo gestor (approval->development) e depois voltou de
    em andamento para retorno suporte, indicando planejamento/aprovacao fraca."""
    had_gestor_approval = any(
        source == "approval" and target == "development" for source, target in transitions
    )
    had_dev_to_sup = any(
        source == "development" and target == "return_support" for source, target in transitions
    )
    return had_gestor_approval and had_dev_to_sup


def _had_return_before(
    events: list[MovementEvent],
    workflow: WorkflowConfig,
    return_group: str,
    before: datetime,
) -> bool:
    for event in events:
        if event.at >= before:
            break
        if event.event_type != "moved":
            continue
        if workflow.group_for_list(event.to_list_name) == return_group:
            return True
    return False
