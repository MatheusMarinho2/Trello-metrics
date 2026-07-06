from __future__ import annotations

from collections import Counter
from typing import Any

from trello_metrics.metrics.aggregators.common import ratio, time_stats
from trello_metrics.metrics.timeline import CardTimeline
from trello_metrics.utils.dates import human_hours, isoformat
from trello_metrics.utils.period import MonthPeriod


def aggregate_analysis_workflow(
    timelines: list[CardTimeline],
    period: MonthPeriod,
) -> dict[str, Any]:
    analysis_cards = [timeline for timeline in timelines if timeline.kind == "analysis"]
    active = [timeline for timeline in analysis_cards if timeline.is_active_in(period)]
    delivered = [timeline for timeline in analysis_cards if timeline.is_delivered_in(period)]

    planning_hours: list[float] = []
    planning_wip = 0
    complete_desc = 0
    returned_dev = 0
    post_terminal = 0
    by_developer: Counter[str] = Counter()
    by_solicitante: Counter[str] = Counter()
    cards_sample: list[dict[str, Any]] = []

    for timeline in active:
        descricao = timeline.descricao or {}
        has_realizada = bool((descricao.get("analise_realizada") or "").strip())
        has_recomendacao = bool((descricao.get("recomendacao") or "").strip())
        if has_realizada and has_recomendacao:
            complete_desc += 1

        planning_hours_value = timeline.group_hours.get("analysis_planning", 0.0)
        if planning_hours_value > 0:
            planning_hours.append(planning_hours_value)

        visits_planning = timeline.group_visits.get("analysis_planning", 0)
        if visits_planning and not timeline.is_delivered_in(period):
            planning_wip += 1

        if timeline.return_dev_count > 0:
            returned_dev += 1
        if timeline.return_after_terminal:
            post_terminal += 1

        if timeline.desenvolvedor and timeline.desenvolvedor != "Nao informado":
            by_developer[timeline.desenvolvedor] += 1
        if timeline.solicitante and timeline.solicitante != "Nao informado":
            by_solicitante[timeline.solicitante] += 1

        if len(cards_sample) < 25:
            cards_sample.append(_card_row(timeline, has_realizada, has_recomendacao))

    delivered_ids = {timeline.card_id for timeline in delivered}
    return {
        "note": (
            "Fluxo: dev realiza analise -> Analises para planejamento -> solicitante decide "
            "-> Analises finalizadas ou novo card de analise. Retorno apos finalizado e violacao."
        ),
        "cards_active_in_period": len(active),
        "analysis_delivered": len(delivered),
        "analysis_in_planning_wip": planning_wip,
        "planning_wait": time_stats(planning_hours),
        "descricao_completa_pct": ratio(complete_desc, len(active)),
        "descricao_completa_count": complete_desc,
        "returned_to_dev_count": returned_dev,
        "post_terminal_return_count": post_terminal,
        "by_developer": _counter_rows(by_developer),
        "by_solicitante": _counter_rows(by_solicitante),
        "highlight_cards": cards_sample,
        "delivered_card_ids": sorted(delivered_ids),
    }


def _card_row(
    timeline: CardTimeline,
    has_realizada: bool,
    has_recomendacao: bool,
) -> dict[str, Any]:
    descricao = timeline.descricao or {}
    flags: list[str] = []
    if not has_realizada:
        flags.append("analise_realizada vazia")
    if not has_recomendacao:
        flags.append("recomendacao vazia")
    if timeline.return_dev_count:
        flags.append(f"retornos DEV ({timeline.return_dev_count})")
    if timeline.return_after_terminal:
        flags.append("retorno apos analise finalizada")
    if timeline.group_visits.get("analysis_planning", 0) == 0:
        flags.append("nao passou por Analises para planejamento")

    return {
        "card_id": timeline.card_id,
        "card_name": timeline.card_name,
        "desenvolvedor": timeline.desenvolvedor,
        "solicitante": timeline.solicitante,
        "sistema": timeline.sistema,
        "planning_hours": timeline.group_hours.get("analysis_planning", 0.0),
        "planning_hours_human": human_hours(timeline.group_hours.get("analysis_planning", 0.0)),
        "delivered_at": isoformat(timeline.delivered_at),
        "flags": flags,
        "solicitacao_analise": (descricao.get("solicitacao_analise") or "")[:120],
    }


def _counter_rows(counter: Counter[str]) -> list[dict[str, Any]]:
    return [{"name": name, "count": count} for name, count in counter.most_common()]
