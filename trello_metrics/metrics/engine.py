from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from trello_metrics.domain.models import BoardData, MovementEvent, TrelloCard
from trello_metrics.domain.workflow import WorkflowConfig
from trello_metrics.metrics.aggregators.analysis_workflow import aggregate_analysis_workflow
from trello_metrics.metrics.aggregators.bottlenecks import aggregate_bottlenecks
from trello_metrics.metrics.aggregators.card_dossier import aggregate_card_dossier
from trello_metrics.metrics.aggregators.collaborators import aggregate_collaborators
from trello_metrics.metrics.aggregators.developers import aggregate_developer_profiles, aggregate_developers
from trello_metrics.metrics.aggregators.dora import aggregate_dora_metrics
from trello_metrics.metrics.aggregators.fibonacci_points import aggregate_fibonacci_points
from trello_metrics.metrics.aggregators.flow import aggregate_flow_metrics
from trello_metrics.metrics.aggregators.priority import aggregate_priority_metrics
from trello_metrics.metrics.aggregators.process_discipline import aggregate_process_discipline
from trello_metrics.metrics.aggregators.projects import aggregate_projects
from trello_metrics.metrics.aggregators.quality_gates import aggregate_quality_gates
from trello_metrics.metrics.aggregators.requesters import aggregate_requesters
from trello_metrics.metrics.aggregators.reviewers import aggregate_reviewers
from trello_metrics.metrics.aggregators.risk import aggregate_risk_board
from trello_metrics.metrics.aggregators.sla import aggregate_sla
from trello_metrics.metrics.aggregators.testers import aggregate_testers
from trello_metrics.metrics.aggregators.trends import aggregate_trends
from trello_metrics.metrics.timeline import build_card_timelines
from trello_metrics.parsers.export_loader import movements_by_card
from trello_metrics.utils.business_hours import duration_hours
from trello_metrics.utils.dates import human_hours, isoformat
from trello_metrics.utils.period import MonthPeriod, month_range, parse_month


@dataclass
class MetricsResult:
    data: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return self.data


class MetricsEngine:
    tracked_fields = (
        "Solicitante",
        "Prioridade",
        "Sistema",
        "Desenvolvedor",
        "Nível",
        "Nivel",
        "Nível (Analise)",
        "Nivel (Analise)",
        "Revisor em Par",
        "Revisor",
        "Tester",
    )

    def __init__(
        self,
        workflow: WorkflowConfig,
        now: datetime | None = None,
        include_templates: bool = False,
        month: str | None = None,
        history_months: int = 6,
        timezone_name: str = "America/Sao_Paulo",
    ) -> None:
        self.workflow = workflow
        self.now = now or datetime.now(timezone.utc)
        self.include_templates = include_templates
        self.month = month
        self.history_months = history_months
        self.timezone_name = timezone_name

    def calculate(self, board: BoardData) -> MetricsResult:
        cards = [
            card
            for card in board.cards
            if self.include_templates
            or (
                not card.is_template
                and not self.workflow.should_ignore_card(
                    card.name,
                    card.custom_fields,
                    card.labels,
                )
            )
        ]
        card_by_id = {card.id: card for card in cards}
        events_by_card = movements_by_card(
            [event for event in board.movements if event.card_id in card_by_id]
        )

        timelines = build_card_timelines(cards, events_by_card, self.workflow, self.now)

        card_kinds = {card.id: timeline.kind for card, timeline in zip(cards, timelines)}

        overview = self._overview(board, cards, card_kinds)
        fields = self._custom_field_metrics(cards)
        movements = self._movement_metrics(cards, card_by_id, events_by_card)
        card_details = self._card_details(cards, card_kinds, events_by_card, timelines)
        data_quality = self._data_quality(cards, card_kinds)

        payload: dict[str, Any] = {
            "board": {
                "id": board.id,
                "name": board.name,
                "url": board.url,
                "generated_at": isoformat(self.now),
            },
            "overview": overview,
            "custom_fields": fields,
            "movements": movements,
            "cards": card_details,
            "data_quality": data_quality,
        }

        if self.month:
            period = parse_month(self.month, self.timezone_name)
            periods = month_range(self.month, self.history_months, self.timezone_name)
            developers = aggregate_developers(timelines, period)
            flow = aggregate_flow_metrics(timelines, cards, self.workflow, period, self.now)
            priority = aggregate_priority_metrics(timelines, period, flow["aging_wip"], self.workflow)
            dora = aggregate_dora_metrics(timelines, period, self.workflow)
            risk_board = aggregate_risk_board(timelines, flow["aging_wip"])
            payload["period"] = {
                "month": self.month,
                "timezone": self.timezone_name,
                "start": isoformat(period.start),
                "end": isoformat(period.end),
            }
            testers = aggregate_testers(timelines, period)
            payload["team_summary"] = _team_summary(
                developers, testers, timelines, self.workflow, period
            )
            payload["flow"] = flow
            payload["priority"] = priority
            payload["dora"] = dora
            payload["fibonacci_points"] = aggregate_fibonacci_points(timelines, period)
            payload["developers"] = developers
            payload["developer_profiles"] = aggregate_developer_profiles(timelines, period)
            payload["reviewers"] = aggregate_reviewers(timelines, period)
            payload["testers"] = testers
            payload["requesters"] = aggregate_requesters(timelines, period)
            payload["projects"] = aggregate_projects(timelines, period)
            payload["bottlenecks"] = aggregate_bottlenecks(
                timelines, cards, self.workflow, period
            )
            payload["sla"] = aggregate_sla(
                timelines,
                cards,
                self.workflow,
                period,
                self.now,
                self.timezone_name,
            )
            payload["quality_gates"] = aggregate_quality_gates(timelines, period)
            payload["process_discipline"] = aggregate_process_discipline(
                timelines,
                board.custom_field_changes,
                self.workflow,
                period,
            )
            payload["analysis_workflow"] = aggregate_analysis_workflow(timelines, period)
            payload["risk_board"] = risk_board
            payload["card_dossier"] = aggregate_card_dossier(timelines, period)
            payload["collaborators"] = aggregate_collaborators(
                timelines,
                period,
                self.workflow,
            )
            payload["trends_6m"] = aggregate_trends(
                timelines, cards, self.workflow, periods
            )

        return MetricsResult(payload)

    def _overview(
        self,
        board: BoardData,
        cards: list[TrelloCard],
        card_kinds: dict[str, str],
    ) -> dict[str, Any]:
        by_kind = Counter(card_kinds.values())
        by_current_list = Counter(card.current_list_name or "Sem lista" for card in cards)
        by_current_group = Counter(
            self.workflow.group_for_list(card.current_list_name) for card in cards
        )
        return {
            "total_lists": len(board.lists),
            "total_cards_raw": len(board.cards),
            "total_cards_metricados": len(cards),
            "total_templates_ignorados": sum(1 for card in board.cards if card.is_template),
            "total_placeholders_ignorados": sum(
                1
                for card in board.cards
                if not card.is_template
                and self.workflow.should_ignore_card(
                    card.name,
                    card.custom_fields,
                    card.labels,
                )
            ),
            "total_movements": len(board.movements),
            "cards_by_kind": _counter_to_rows(by_kind),
            "cards_by_current_list": _counter_to_rows(by_current_list),
            "cards_by_current_group": [
                {"name": self.workflow.title_for_group(group), "count": count}
                for group, count in by_current_group.most_common()
            ],
        }

    def _custom_field_metrics(self, cards: list[TrelloCard]) -> dict[str, list[dict[str, Any]]]:
        output: dict[str, list[dict[str, Any]]] = {}
        for field in self.tracked_fields:
            counter = Counter(
                card.custom_fields.get(field, "Nao informado")
                for card in cards
                if field in card.custom_fields or field in ("Prioridade", "Sistema")
            )
            if counter:
                output[field] = _counter_to_rows(counter)
        return output

    def _movement_metrics(
        self,
        cards: list[TrelloCard],
        card_by_id: dict[str, TrelloCard],
        events_by_card: dict[str, list[MovementEvent]],
    ) -> dict[str, Any]:
        transition_counter: Counter[str] = Counter()
        target_group_counter: Counter[str] = Counter()
        attributed: dict[str, Counter[str]] = defaultdict(Counter)
        returns_by_responsible: dict[str, Counter[str]] = defaultdict(Counter)
        time_by_list: dict[str, dict[str, float]] = defaultdict(
            lambda: {"total_hours": 0.0, "spans": 0}
        )

        for card in cards:
            events = events_by_card.get(card.id, [])
            for event in events:
                if event.event_type != "moved":
                    continue
                source_group = self.workflow.group_for_list(event.from_list_name)
                target_group = self.workflow.group_for_list(event.to_list_name)
                transition_counter[
                    f"{self.workflow.title_for_group(source_group)} -> "
                    f"{self.workflow.title_for_group(target_group)}"
                ] += 1
                target_group_counter[self.workflow.title_for_group(target_group)] += 1

                field = self.workflow.attribution_field_for_group(target_group)
                if field:
                    responsible = card.custom_fields.get(field) or f"Sem {field}"
                    role = self.workflow.role_for_group(target_group)
                    attributed[role][responsible] += 1
                    if target_group in {"return_developer", "return_support"}:
                        returns_by_responsible[role][responsible] += 1

            for span in self._timeline_spans(card, events):
                list_name = span["list_name"]
                hours = span["hours"]
                time_by_list[list_name]["total_hours"] += hours
                time_by_list[list_name]["spans"] += 1

        time_rows = []
        for list_name, values in time_by_list.items():
            spans = int(values["spans"])
            total = round(values["total_hours"], 2)
            avg = round(total / spans, 2) if spans else 0.0
            time_rows.append(
                {
                    "list": list_name,
                    "total_hours": total,
                    "avg_hours": avg,
                    "avg_human": human_hours(avg),
                    "spans": spans,
                }
            )

        return {
            "transitions": _counter_to_rows(transition_counter),
            "target_groups": _counter_to_rows(target_group_counter),
            "attributed_movements": {
                role: _counter_to_rows(counter) for role, counter in attributed.items()
            },
            "returns_by_responsible": {
                role: _counter_to_rows(counter)
                for role, counter in returns_by_responsible.items()
            },
            "time_by_list": sorted(
                time_rows,
                key=lambda item: item["total_hours"],
                reverse=True,
            ),
        }

    def _card_details(
        self,
        cards: list[TrelloCard],
        card_kinds: dict[str, str],
        events_by_card: dict[str, list[MovementEvent]],
        timelines: list,
    ) -> list[dict[str, Any]]:
        timeline_by_id = {timeline.card_id: timeline for timeline in timelines}
        details = []
        for card in sorted(cards, key=lambda item: (item.current_list_name, item.name)):
            events = events_by_card.get(card.id, [])
            groups_seen = [
                self.workflow.group_for_list(event.to_list_name)
                for event in events
                if event.to_list_name
            ]
            kind = card_kinds.get(card.id, "unknown")
            timeline = timeline_by_id.get(card.id)
            detail = {
                "id": card.id,
                "id_short": card.id_short,
                "name": card.name,
                "kind": kind,
                "current_list": card.current_list_name,
                "current_group": self.workflow.title_for_group(
                    self.workflow.group_for_list(card.current_list_name)
                ),
                "labels": card.labels,
                "custom_fields": card.custom_fields,
                "created_at": isoformat(card.created_at),
                "date_last_activity": isoformat(card.date_last_activity),
                "url": card.url,
                "movement_count": sum(1 for event in events if event.event_type == "moved"),
                "return_developer_count": timeline.return_dev_count if timeline else 0,
                "return_support_count": timeline.return_sup_count if timeline else 0,
                "pause_count": timeline.pause_count if timeline else 0,
                "cycle_time_hours": self._cycle_time_hours(card, kind, events),
                "flow_flags": self._flow_flags(
                    kind,
                    groups_seen,
                    timeline.pause_count if timeline else 0,
                ),
                "delivered_at": isoformat(timeline.delivered_at) if timeline else None,
                "fibonacci_level": timeline.fibonacci_level if timeline else None,
            }
            detail["cycle_time_human"] = human_hours(detail["cycle_time_hours"])
            details.append(detail)
        return details

    def _data_quality(
        self,
        cards: list[TrelloCard],
        card_kinds: dict[str, str],
    ) -> dict[str, Any]:
        if not cards:
            return {"cards_with_required_fields_pct": 0.0, "by_kind": []}

        by_kind: dict[str, dict[str, int]] = defaultdict(lambda: {"ok": 0, "total": 0})
        for card in cards:
            kind = card_kinds.get(card.id, "unknown")
            if kind not in {"problem", "analysis"}:
                continue
            required = self.workflow.required_fields_for_kind(kind)
            by_kind[kind]["total"] += 1
            if all(card.custom_fields.get(field) for field in required):
                by_kind[kind]["ok"] += 1

        total_ok = sum(values["ok"] for values in by_kind.values())
        total = sum(values["total"] for values in by_kind.values())
        return {
            "cards_with_required_fields_pct": round(100 * total_ok / total, 1) if total else 0.0,
            "by_kind": [
                {
                    "kind": kind,
                    "complete": values["ok"],
                    "total": values["total"],
                    "pct": round(100 * values["ok"] / values["total"], 1) if values["total"] else 0.0,
                }
                for kind, values in by_kind.items()
            ],
        }

    def _timeline_spans(
        self,
        card: TrelloCard,
        events: list[MovementEvent],
    ) -> list[dict[str, Any]]:
        points = [event for event in sorted(events, key=lambda item: item.at) if event.to_list_name]
        if not points and card.created_at and card.current_list_name:
            return [
                {
                    "list_name": card.current_list_name,
                    "start": card.created_at,
                    "end": card.date_closed or self.now,
                    "hours": duration_hours(card.created_at, card.date_closed or self.now, self.workflow),
                }
            ]

        spans: list[dict[str, Any]] = []
        for index, point in enumerate(points):
            next_point = points[index + 1] if index + 1 < len(points) else None
            end = next_point.at if next_point else card.date_closed or self.now
            list_name = point.to_list_name or "Sem lista"
            spans.append(
                {
                    "list_name": list_name,
                    "start": point.at,
                    "end": end,
                    "hours": duration_hours(point.at, end, self.workflow),
                }
            )
        return spans

    def _cycle_time_hours(
        self,
        card: TrelloCard,
        kind: str,
        events: list[MovementEvent],
    ) -> float:
        ordered = sorted(events, key=lambda item: item.at)
        start = card.created_at or (ordered[0].at if ordered else None)
        done_groups = set(self.workflow.done_groups_for_kind(kind))
        end = None
        for event in ordered:
            if self.workflow.group_for_list(event.to_list_name) in done_groups:
                end = event.at
                break
        end = end or card.date_closed or self.now
        return duration_hours(start, end, self.workflow)

    @staticmethod
    def _flow_flags(kind: str, groups_seen: list[str], pause_count: int = 0) -> list[str]:
        flags = []
        if "return_developer" in groups_seen:
            flags.append("teve_retorno_dev")
        if "return_support" in groups_seen:
            flags.append("teve_retorno_sup")
        if "paused" in groups_seen or pause_count > 0:
            flags.append("teve_pausa")

        if kind == "problem":
            reached_delivery = any(
                group
                in {
                    "waiting_deploy",
                    "waiting_test",
                    "testing",
                    "waiting_production",
                    "production",
                    "direct_production",
                }
                for group in groups_seen
            )
            has_review = any(
                group in {"waiting_peer_review", "peer_review", "waiting_review", "review"}
                for group in groups_seen
            )
            if reached_delivery and not has_review:
                flags.append("atalho_sem_revisao")
        return flags or ["sem_alertas"]


def _team_summary(
    developers: list[dict[str, Any]],
    testers: list[dict[str, Any]],
    timelines: list,
    workflow: WorkflowConfig,
    period: MonthPeriod,
) -> dict[str, Any]:
    delivered = [timeline for timeline in timelines if timeline.is_delivered_in(period)]
    dev_delivered = [
        timeline
        for timeline in delivered
        if timeline.desenvolvedor != "Nao informado" and timeline.desenvolvedor.startswith("D-")
    ]
    cards_count = len(delivered)
    fibonacci_normal = sum(
        timeline.fibonacci_level or 0
        for timeline in dev_delivered
        if timeline.kind == "problem"
    )
    fibonacci_analysis = sum(
        timeline.fibonacci_level or 0
        for timeline in dev_delivered
        if timeline.kind == "analysis"
    )
    accepted = sum(1 for timeline in delivered if timeline.accepted_without_dev_return)
    return_dev = sum(timeline.developer_penalty_return_count for timeline in delivered)
    tester_quality_returns = sum(timeline.return_dev_by_teste_count for timeline in delivered)

    # Retrabalho do dev: qualquer RETORNO (DEV), inclusive escape encontrado em teste.
    # Retornos vindos do teste tambem contam como problemas evitados pelo tester.
    # A taxa de qualidade e o complemento (ex.: 10 entregues, 1 voltou => 90% de qualidade).
    cards_with_rework = sum(
        1 for timeline in delivered if timeline.developer_penalty_return_count > 0
    )
    rework_rate_pct = round(100 * cards_with_rework / cards_count, 1) if cards_count else 0.0
    quality_rate_pct = round(100 - rework_rate_pct, 1) if cards_count else 0.0

    double_review_required = [timeline for timeline in delivered if timeline.double_review_required]
    double_review_violations = [
        timeline for timeline in double_review_required if timeline.double_review_violation
    ]
    double_review_recommended = [
        timeline for timeline in delivered if timeline.double_review_recommended
    ]
    double_review_recommended_done = [
        timeline for timeline in double_review_recommended if timeline.double_review_done
    ]

    return {
        "cards_delivered": cards_count,
        "fibonacci_normal": fibonacci_normal,
        "fibonacci_analysis": fibonacci_analysis,
        "fibonacci_total": fibonacci_normal + fibonacci_analysis,
        "acceptance_rate_pct": round(100 * accepted / cards_count, 1) if cards_count else 0.0,
        "return_dev_rate_pct": round(100 * return_dev / cards_count, 1) if cards_count else 0.0,
        "prevented_problem_rate_pct": (
            round(100 * tester_quality_returns / cards_count, 1) if cards_count else 0.0
        ),
        "tester_quality_return_rate_pct": (
            round(100 * tester_quality_returns / cards_count, 1) if cards_count else 0.0
        ),
        "cards_with_rework_count": cards_with_rework,
        "total_return_dev_events": return_dev,
        "total_prevented_problems": tester_quality_returns,
        "total_tester_quality_returns": tester_quality_returns,
        "test_returns_missing_reason_count": sum(
            timeline.test_return_missing_reason_count for timeline in delivered
        ),
        "rework_rate_pct": rework_rate_pct,
        "quality_rate_pct": quality_rate_pct,
        "quality_seal": workflow.quality_seal(quality_rate_pct) if cards_count else "Sem dados",
        "double_review_mandatory_total": len(double_review_required),
        "double_review_mandatory_violations": len(double_review_violations),
        "double_review_recommended_total": len(double_review_recommended),
        "double_review_recommended_done": len(double_review_recommended_done),
        "active_developers": len([dev for dev in developers if dev["cards_delivered"] > 0]),
    }


def _counter_to_rows(counter: Counter[str]) -> list[dict[str, Any]]:
    return [
        {"name": name or "Nao informado", "count": count}
        for name, count in counter.most_common()
    ]
