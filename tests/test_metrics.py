from __future__ import annotations

import unittest
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from trello_metrics.config import load_workflow_config
from trello_metrics.domain.models import (
    BoardData,
    CardDescriptionData,
    CustomFieldChange,
    MovementEvent,
    TrelloCard,
    TrelloList,
)
from trello_metrics.metrics.aggregators.bottlenecks import aggregate_bottlenecks
from trello_metrics.metrics.aggregators.collaborators import aggregate_collaborators
from trello_metrics.metrics.aggregators.developers import aggregate_developers
from trello_metrics.metrics.aggregators.trends import aggregate_trends
from trello_metrics.utils.business_hours import business_hours_between
from trello_metrics.metrics.engine import MetricsEngine
from trello_metrics.metrics.timeline import build_card_timelines
from trello_metrics.utils.fibonacci import parse_fibonacci_level
from trello_metrics.utils.period import parse_month


def _dt(year: int, month: int, day: int, hour: int = 12) -> datetime:
    return datetime(year, month, day, hour, tzinfo=ZoneInfo("America/Sao_Paulo")).astimezone(
        timezone.utc
    )


class FibonacciTest(unittest.TestCase):
    def test_parse_valid_levels(self) -> None:
        self.assertEqual(parse_fibonacci_level("8"), 8)
        self.assertEqual(parse_fibonacci_level("Nivel 13"), 13)
        self.assertIsNone(parse_fibonacci_level("20"))


class BusinessHoursTest(unittest.TestCase):
    def setUp(self) -> None:
        self.rules = load_workflow_config().sla_rules()

    def test_excludes_lunch_break_on_weekday(self) -> None:
        start = _dt(2026, 6, 1, 11)
        end = _dt(2026, 6, 1, 14)
        elapsed = business_hours_between(start, end, self.rules, "America/Sao_Paulo")
        self.assertEqual(elapsed, 2.0)

    def test_thursday_ends_at_1730(self) -> None:
        start = _dt(2026, 6, 4, 17)
        end = _dt(2026, 6, 4, 18)
        elapsed = business_hours_between(start, end, self.rules, "America/Sao_Paulo")
        self.assertEqual(elapsed, 0.5)

    def test_timeline_group_hours_exclude_lunch(self) -> None:
        card = TrelloCard(
            id="card_lunch",
            name="PM CLIENTE / Permanencia almoco",
            current_list_id="dev",
            current_list_name="EM ANDAMENTO",
            created_at=_dt(2026, 6, 2, 11),
            custom_fields={"Desenvolvedor": "D-Dev.A", "Nivel": "3", "Sistema": "Legislativo"},
        )
        events = [
            MovementEvent(
                card_id=card.id,
                card_name=card.name,
                at=_dt(2026, 6, 2, 11),
                event_type="moved",
                to_list_name="EM ANDAMENTO",
            ),
            MovementEvent(
                card_id=card.id,
                card_name=card.name,
                at=_dt(2026, 6, 2, 14),
                event_type="moved",
                from_list_name="EM ANDAMENTO",
                to_list_name="AGUARDANDO REVISAO FORMAL",
            ),
        ]
        timelines = build_card_timelines(
            [card],
            {card.id: events},
            load_workflow_config(),
            _dt(2026, 6, 2, 15),
        )
        self.assertEqual(timelines[0].group_hours.get("development"), 2.0)


class MetricsEngineTest(unittest.TestCase):
    def setUp(self) -> None:
        self.workflow = load_workflow_config()
        self.period = parse_month("2026-06")

    def test_return_developer_is_attributed_to_developer_field(self) -> None:
        card = TrelloCard(
            id="card1",
            name="PM CLIENTE / Erro ao finalizar",
            current_list_id="return_dev",
            current_list_name="RETORNO (DEV)",
            created_at=_dt(2026, 6, 10),
            custom_fields={"Desenvolvedor": "D-Kauan.Carolino", "Nível": "3"},
        )
        board = self._board(
            card,
            [
                MovementEvent(
                    card_id="card1",
                    card_name=card.name,
                    at=_dt(2026, 6, 10, 13),
                    event_type="created",
                    to_list_id="dev",
                    to_list_name="EM ANDAMENTO",
                ),
                MovementEvent(
                    card_id="card1",
                    card_name=card.name,
                    at=_dt(2026, 6, 10, 14),
                    event_type="moved",
                    from_list_id="dev",
                    from_list_name="EM ANDAMENTO",
                    to_list_id="return_dev",
                    to_list_name="RETORNO (DEV)",
                ),
            ],
        )

        result = MetricsEngine(
            self.workflow,
            now=_dt(2026, 6, 30, 16),
        ).calculate(board).to_dict()

        returns = result["movements"]["returns_by_responsible"]["desenvolvedor"]
        self.assertEqual(returns, [{"name": "D-Kauan.Carolino", "count": 1}])
        self.assertEqual(result["cards"][0]["return_developer_count"], 1)

    def test_delivery_in_june_via_waiting_production(self) -> None:
        card = TrelloCard(
            id="card2",
            name="PM CLIENTE / Ajuste relatorio",
            current_list_id="wait_prod",
            current_list_name="AGUARDANDO PRODUÇÃO (EXECUTIVO)",
            created_at=_dt(2026, 6, 5),
            custom_fields={
                "Desenvolvedor": "D-Dev.A",
                "Nível": "5",
                "Sistema": "Executivo",
                "Solicitante": "Sup A",
            },
        )
        board = self._board(
            card,
            [
                MovementEvent(
                    card_id="card2",
                    card_name=card.name,
                    at=_dt(2026, 6, 5, 10),
                    event_type="created",
                    to_list_name="PLANEJAMENTO",
                ),
                MovementEvent(
                    card_id="card2",
                    card_name=card.name,
                    at=_dt(2026, 6, 8, 10),
                    event_type="moved",
                    from_list_name="EM ANDAMENTO",
                    to_list_name="AGUARDANDO PRODUÇÃO (EXECUTIVO)",
                ),
            ],
        )

        timelines = build_card_timelines(
            board.cards,
            {"card2": board.movements},
            self.workflow,
            _dt(2026, 6, 30),
        )
        self.assertTrue(timelines[0].is_delivered_in(self.period))
        self.assertEqual(timelines[0].fibonacci_level, 5)

        result = MetricsEngine(
            self.workflow,
            now=_dt(2026, 6, 30),
            month="2026-06",
        ).calculate(board).to_dict()

        self.assertEqual(result["team_summary"]["cards_delivered"], 1)
        self.assertEqual(result["developers"][0]["fibonacci_normal"], 5)

    def test_peer_review_return_counts_for_developer(self) -> None:
        card = TrelloCard(
            id="card3",
            name="PM CLIENTE / Bug critico",
            current_list_id="dev",
            current_list_name="EM ANDAMENTO",
            created_at=_dt(2026, 6, 1),
            custom_fields={
                "Desenvolvedor": "D-Dev.B",
                "Revisor em Par": "Dev C",
                "Nível": "8",
                "Sistema": "Legislativo",
            },
        )
        events = [
            MovementEvent(
                card_id="card3",
                card_name=card.name,
                at=_dt(2026, 6, 10),
                event_type="moved",
                from_list_name="REVISÃO EM PAR",
                to_list_name="EM ANDAMENTO",
            ),
            MovementEvent(
                card_id="card3",
                card_name=card.name,
                at=_dt(2026, 6, 20),
                event_type="moved",
                from_list_name="EM TESTE",
                to_list_name="AGUARDANDO PRODUÇÃO (LEGISLATIVO)",
            ),
        ]
        board = self._board(card, events)
        timelines = build_card_timelines(
            board.cards,
            {"card3": events},
            self.workflow,
            _dt(2026, 6, 30),
        )
        self.assertEqual(timelines[0].peer_review_returns, 1)
        self.assertTrue(timelines[0].peer_review_sent_back)

        developers = aggregate_developers(timelines, self.period)
        dev_b = next(row for row in developers if row["name"] == "D-Dev.B")
        self.assertEqual(dev_b["peer_review_returns"], 1)

    def test_acceptance_without_dev_return(self) -> None:
        card = TrelloCard(
            id="card4",
            name="PM CLIENTE / Sem retorno",
            current_list_id="wait_prod",
            current_list_name="AGUARDANDO PRODUÇÃO (PAC)",
            created_at=_dt(2026, 6, 2),
            custom_fields={"Desenvolvedor": "D-Dev.D", "Nível": "3", "Sistema": "PAC"},
        )
        events = [
            MovementEvent(
                card_id="card4",
                card_name=card.name,
                at=_dt(2026, 6, 15),
                event_type="moved",
                to_list_name="AGUARDANDO PRODUÇÃO (PAC)",
            )
        ]
        board = self._board(card, events)
        timelines = build_card_timelines(
            board.cards,
            {"card4": events},
            self.workflow,
            _dt(2026, 6, 30),
        )
        self.assertTrue(timelines[0].accepted_without_dev_return)

        developers = aggregate_developers(timelines, self.period)
        dev_d = next(row for row in developers if row["name"] == "D-Dev.D")
        self.assertEqual(dev_d["acceptance_rate_pct"], 100.0)

    def test_collaborator_merges_same_base_name_across_roles(self) -> None:
        card = TrelloCard(
            id="card_colab",
            name="PM CLIENTE / Fluxo completo",
            current_list_id="wait_prod",
            current_list_name="AGUARDANDO PRODUCAO (EXECUTIVO)",
            created_at=_dt(2026, 6, 1, 9),
            custom_fields={
                "Solicitante": "S-Kauan.Carolino",
                "Desenvolvedor": "D-Kauan.Carolino",
                "Revisor em Par": "RP-Kauan.Carolino",
                "Revisor": "R-Kauan.Carolino",
                "Tester": "T-Kauan.Carolino",
                "Nivel": "5",
                "Sistema": "Executivo",
            },
        )
        events = [
            MovementEvent(
                card_id="card_colab",
                card_name=card.name,
                at=_dt(2026, 6, 1, 9),
                event_type="created",
                to_list_name="PLANEJAMENTO",
            ),
            MovementEvent(
                card_id="card_colab",
                card_name=card.name,
                at=_dt(2026, 6, 1, 10),
                event_type="moved",
                from_list_name="PLANEJAMENTO",
                to_list_name="EM ANDAMENTO",
            ),
            MovementEvent(
                card_id="card_colab",
                card_name=card.name,
                at=_dt(2026, 6, 1, 12),
                event_type="moved",
                from_list_name="EM ANDAMENTO",
                to_list_name="REVISAO EM PAR",
            ),
            MovementEvent(
                card_id="card_colab",
                card_name=card.name,
                at=_dt(2026, 6, 1, 13),
                event_type="moved",
                from_list_name="REVISAO EM PAR",
                to_list_name="EM REVISAO",
            ),
            MovementEvent(
                card_id="card_colab",
                card_name=card.name,
                at=_dt(2026, 6, 1, 14),
                event_type="moved",
                from_list_name="EM REVISAO",
                to_list_name="EM TESTE",
            ),
            MovementEvent(
                card_id="card_colab",
                card_name=card.name,
                at=_dt(2026, 6, 1, 15),
                event_type="moved",
                from_list_name="EM TESTE",
                to_list_name="AGUARDANDO PRODUCAO (EXECUTIVO)",
            ),
        ]

        result = MetricsEngine(
            self.workflow,
            now=_dt(2026, 6, 30, 16),
            month="2026-06",
        ).calculate(self._board(card, events)).to_dict()

        collaborator = next(row for row in result["collaborators"] if row["name"] == "Kauan.Carolino")
        self.assertEqual(collaborator["summary"]["cards_delivered"], 1)
        self.assertEqual(collaborator["summary"]["cards_created"], 1)
        self.assertEqual(collaborator["summary"]["fibonacci_total"], 5)
        self.assertEqual(
            collaborator["roles"],
            ["Solicitante", "Desenvolvedor", "Revisor em Par", "Revisor", "Tester"],
        )
        self.assertEqual(len(collaborator["cards"]), 1)
        self.assertEqual(len(collaborator["cards"][0]["collaborator_involvements"]), 5)

    def test_bottleneck_waiting_test(self) -> None:
        card = TrelloCard(
            id="card5",
            name="PM CLIENTE / Fila teste",
            current_list_id="wait_test",
            current_list_name="AGUARDANDO TESTE (EXECUTIVO)",
            created_at=_dt(2026, 6, 1),
            custom_fields={"Desenvolvedor": "Dev E", "Nível": "2", "Sistema": "Executivo"},
        )
        events = [
            MovementEvent(
                card_id="card5",
                card_name=card.name,
                at=_dt(2026, 6, 5, 8),
                event_type="moved",
                to_list_name="AGUARDANDO TESTE (EXECUTIVO)",
            ),
            MovementEvent(
                card_id="card5",
                card_name=card.name,
                at=_dt(2026, 6, 7, 8),
                event_type="moved",
                from_list_name="AGUARDANDO TESTE (EXECUTIVO)",
                to_list_name="AGUARDANDO PRODUÇÃO (EXECUTIVO)",
            ),
        ]
        board = self._board(card, events)
        timelines = build_card_timelines(
            board.cards,
            {"card5": events},
            self.workflow,
            _dt(2026, 6, 8, 9),
        )
        bottlenecks = aggregate_bottlenecks(
            timelines,
            board.cards,
            self.workflow,
            self.period,
        )
        top = bottlenecks["top_bottleneck"]
        self.assertIsNotNone(top)
        self.assertEqual(top["group"], "waiting_test")

    def test_aguardando_revisao_is_neutral_control_stage(self) -> None:
        card = TrelloCard(
            id="card_review_control",
            name="PM CLIENTE / Pareamento",
            current_list_id="prod",
            current_list_name="EM PRODUÇÃO",
            created_at=_dt(2026, 6, 1, 9),
            custom_fields={
                "Desenvolvedor": "D-Matheus.Marinho",
                "Revisor": "R-Dheryk.Medeiros",
                "Revisor em Par": "RP-Joao.Mariano",
                "Nivel": "5",
                "Sistema": "Legislativo",
            },
        )
        events = [
            MovementEvent(
                card_id=card.id,
                card_name=card.name,
                at=_dt(2026, 6, 1, 9),
                event_type="created",
                to_list_name="EM ANDAMENTO",
            ),
            MovementEvent(
                card_id=card.id,
                card_name=card.name,
                at=_dt(2026, 6, 1, 10),
                event_type="moved",
                from_list_name="EM ANDAMENTO",
                to_list_name="AGUARDANDO REVISÃO EM PAR",
            ),
            MovementEvent(
                card_id=card.id,
                card_name=card.name,
                at=_dt(2026, 6, 1, 11),
                event_type="moved",
                from_list_name="AGUARDANDO REVISÃO EM PAR",
                to_list_name="AGUARDANDO REVISÃO (Opcional)",
            ),
            MovementEvent(
                card_id=card.id,
                card_name=card.name,
                at=_dt(2026, 6, 1, 12),
                event_type="moved",
                from_list_name="AGUARDANDO REVISÃO (Opcional)",
                to_list_name="REVISÃO EM PAR",
            ),
            MovementEvent(
                card_id=card.id,
                card_name=card.name,
                at=_dt(2026, 6, 1, 13),
                event_type="moved",
                from_list_name="REVISÃO EM PAR",
                to_list_name="AGUARDANDO PRODUÇÃO (LEGISLATIVO)",
            ),
        ]

        board = self._board(card, events)
        timelines = build_card_timelines(
            board.cards,
            {card.id: events},
            self.workflow,
            _dt(2026, 6, 1, 14),
        )
        timeline = timelines[0]
        waiting_peer_stage = next(stage for stage in timeline.stage_timeline if stage.group == "waiting_peer_review")
        control_stage = next(stage for stage in timeline.stage_timeline if stage.group == "review_control")

        self.assertTrue(waiting_peer_stage.excluded_from_flow_metrics)
        self.assertTrue(control_stage.excluded_from_flow_metrics)
        self.assertFalse(timeline.passed_formal_review)
        self.assertEqual(timeline.group_hours.get("waiting_review", 0), 0)

        collaborators = aggregate_collaborators(timelines, self.period, self.workflow)
        revisor = next(row for row in collaborators if row["name"] == "Dheryk.Medeiros")
        revisor_role = next(role for role in revisor["role_metrics"] if role["role_key"] == "revisor")
        self.assertEqual(revisor_role["time_hours"], 0.0)
        revisor_par = next(row for row in collaborators if row["name"] == "Joao.Mariano")
        revisor_par_role = next(
            role for role in revisor_par["role_metrics"] if role["role_key"] == "revisor_par"
        )
        self.assertEqual(
            [item["group"] for item in revisor_par_role["process_times"]],
            ["peer_review"],
        )

    def test_sla_development_uses_fibonacci_level_hours(self) -> None:
        card = TrelloCard(
            id="card_sla",
            name="PM CLIENTE / SLA nivel 1",
            current_list_id="wait_prod",
            current_list_name="AGUARDANDO PRODUÇÃO (LEGISLATIVO)",
            created_at=_dt(2026, 6, 1, 9),
            custom_fields={
                "Desenvolvedor": "D-Matheus.Marinho",
                "Nivel": "1",
                "Sistema": "Legislativo",
                "Solicitante": "S-Genilson",
            },
        )
        events = [
            MovementEvent(
                card_id=card.id,
                card_name=card.name,
                at=_dt(2026, 6, 1, 9),
                event_type="created",
                to_list_name="PLANEJAMENTO",
            ),
            MovementEvent(
                card_id=card.id,
                card_name=card.name,
                at=_dt(2026, 6, 1, 10),
                event_type="moved",
                from_list_name="PLANEJAMENTO",
                to_list_name="EM ANDAMENTO",
            ),
            MovementEvent(
                card_id=card.id,
                card_name=card.name,
                at=_dt(2026, 6, 1, 12),
                event_type="moved",
                from_list_name="EM ANDAMENTO",
                to_list_name="AGUARDANDO PRODUÇÃO (LEGISLATIVO)",
            ),
        ]

        result = MetricsEngine(
            self.workflow,
            now=_dt(2026, 6, 1, 13),
            month="2026-06",
        ).calculate(self._board(card, events)).to_dict()

        development = next(row for row in result["sla"]["by_stage"] if row["group"] == "development")
        self.assertEqual(development["breached_count"], 1)
        self.assertEqual(development["sla_human"], "1.00 h")
        self.assertEqual(result["sla"]["team"]["compliance_pct"], 66.7)

    def test_sla_analysis_planning_uses_analysis_level_hours(self) -> None:
        card = TrelloCard(
            id="card_sla_analysis",
            name="ANALISE / Impacto no modulo de pauta",
            current_list_id="analysis_done",
            current_list_name="ANALISES FINALIZADAS",
            created_at=_dt(2026, 6, 2, 9),
            custom_fields={
                "Desenvolvedor": "D-Matheus.Marinho",
                "Nivel (Analise)": "2",
                "Sistema": "Legislativo",
                "Solicitante": "S-Genilson",
            },
        )
        events = [
            MovementEvent(
                card_id=card.id,
                card_name=card.name,
                at=_dt(2026, 6, 2, 10),
                event_type="moved",
                to_list_name="ANALISES PARA PLANEJAMENTO",
            ),
            MovementEvent(
                card_id=card.id,
                card_name=card.name,
                at=_dt(2026, 6, 2, 12),
                event_type="moved",
                from_list_name="ANALISES PARA PLANEJAMENTO",
                to_list_name="PLANEJAMENTO",
            ),
        ]

        result = MetricsEngine(
            self.workflow,
            now=_dt(2026, 6, 2, 13),
            month="2026-06",
        ).calculate(self._board(card, events)).to_dict()

        analysis_stage = next(
            row for row in result["sla"]["by_stage"] if row["group"] == "analysis_planning"
        )
        self.assertEqual(analysis_stage["breached_count"], 1)
        self.assertEqual(analysis_stage["sla_human"], "1.00 h")
        card_checks = result["sla"]["cards"][0]["checks"]
        planning_check = next(item for item in card_checks if item["group"] == "analysis_planning")
        self.assertEqual(planning_check["sla_basis"], "analysis_level")
        self.assertEqual(planning_check["limit_hours"], 1.0)

    def test_sla_analysis_planning_without_level_is_skipped(self) -> None:
        card = TrelloCard(
            id="card_sla_analysis_no_level",
            name="ANALISE / Sem nivel informado",
            current_list_id="analysis_planning",
            current_list_name="ANALISES PARA PLANEJAMENTO",
            created_at=_dt(2026, 6, 3, 9),
            custom_fields={
                "Desenvolvedor": "D-Matheus.Marinho",
                "Sistema": "Legislativo",
            },
        )
        events = [
            MovementEvent(
                card_id=card.id,
                card_name=card.name,
                at=_dt(2026, 6, 3, 10),
                event_type="moved",
                to_list_name="ANALISES PARA PLANEJAMENTO",
            ),
            MovementEvent(
                card_id=card.id,
                card_name=card.name,
                at=_dt(2026, 6, 3, 12),
                event_type="moved",
                from_list_name="ANALISES PARA PLANEJAMENTO",
                to_list_name="PLANEJAMENTO",
            ),
        ]

        result = MetricsEngine(
            self.workflow,
            now=_dt(2026, 6, 3, 13),
            month="2026-06",
        ).calculate(self._board(card, events)).to_dict()

        groups = {row["group"] for row in result["sla"]["by_stage"]}
        self.assertNotIn("analysis_planning", groups)

    def test_sla_return_developer_uses_priority_hours(self) -> None:
        card = TrelloCard(
            id="card_sla_return",
            name="PM CLIENTE / Correcao pos teste",
            current_list_id="return_dev",
            current_list_name="RETORNO (DEV)",
            created_at=_dt(2026, 6, 4, 9),
            custom_fields={
                "Desenvolvedor": "D-Matheus.Marinho",
                "Nivel": "3",
                "Prioridade": "Critica",
                "Sistema": "Legislativo",
            },
        )
        events = [
            MovementEvent(
                card_id=card.id,
                card_name=card.name,
                at=_dt(2026, 6, 4, 10),
                event_type="moved",
                to_list_name="RETORNO (DEV)",
            ),
            MovementEvent(
                card_id=card.id,
                card_name=card.name,
                at=_dt(2026, 6, 4, 14),
                event_type="moved",
                from_list_name="RETORNO (DEV)",
                to_list_name="EM ANDAMENTO",
            ),
        ]

        result = MetricsEngine(
            self.workflow,
            now=_dt(2026, 6, 4, 15),
            month="2026-06",
        ).calculate(self._board(card, events)).to_dict()

        return_stage = next(
            row for row in result["sla"]["by_stage"] if row["group"] == "return_developer"
        )
        self.assertEqual(return_stage["breached_count"], 1)
        self.assertEqual(return_stage["sla_human"], "2.00 h")
        return_check = next(
            item for item in result["sla"]["cards"][0]["checks"] if item["group"] == "return_developer"
        )
        self.assertEqual(return_check["sla_basis"], "return_priority")
        self.assertEqual(return_check["limit_hours"], 2.0)

    def test_sla_waiting_review_uses_fixed_stage_hours(self) -> None:
        card = TrelloCard(
            id="card_sla_waiting_review",
            name="PM CLIENTE / Aguardando revisor",
            current_list_id="waiting_review",
            current_list_name="AGUARDANDO REVISAO FORMAL",
            created_at=_dt(2026, 6, 5, 9),
            custom_fields={
                "Desenvolvedor": "D-Matheus.Marinho",
                "Nivel": "5",
                "Sistema": "Legislativo",
            },
        )
        events = [
            MovementEvent(
                card_id=card.id,
                card_name=card.name,
                at=_dt(2026, 6, 5, 10),
                event_type="moved",
                to_list_name="AGUARDANDO REVISAO FORMAL",
            ),
            MovementEvent(
                card_id=card.id,
                card_name=card.name,
                at=_dt(2026, 6, 5, 16),
                event_type="moved",
                from_list_name="AGUARDANDO REVISAO FORMAL",
                to_list_name="EM REVISAO",
            ),
        ]

        result = MetricsEngine(
            self.workflow,
            now=_dt(2026, 6, 5, 17),
            month="2026-06",
        ).calculate(self._board(card, events)).to_dict()

        waiting_review = next(
            row for row in result["sla"]["by_stage"] if row["group"] == "waiting_review"
        )
        self.assertEqual(waiting_review["breached_count"], 1)
        self.assertEqual(waiting_review["sla_human"], "4.00 h")

    def test_tester_return_dev_penalizes_dev_and_reviewers_but_counts_prevented_problem(self) -> None:
        card = TrelloCard(
            id="card_tester_return",
            name="PM CLIENTE / Tester encontrou defeito",
            current_list_id="wait_prod",
            current_list_name="AGUARDANDO PRODUÇÃO (LEGISLATIVO)",
            created_at=_dt(2026, 6, 1, 9),
            custom_fields={
                "Desenvolvedor": "D-Matheus.Marinho",
                "Revisor em Par": "RP-Joao.Mariano",
                "Revisor": "R-Dheryk.Medeiros",
                "Tester": "T-Genilson",
                "Nivel": "3",
                "Sistema": "Legislativo",
                "Solicitante": "S-Genilson",
            },
        )
        events = [
            MovementEvent(
                card_id=card.id,
                card_name=card.name,
                at=_dt(2026, 6, 1, 9),
                event_type="created",
                to_list_name="EM ANDAMENTO",
            ),
            MovementEvent(
                card_id=card.id,
                card_name=card.name,
                at=_dt(2026, 6, 1, 10),
                event_type="moved",
                from_list_name="EM ANDAMENTO",
                to_list_name="REVISAO EM PAR",
            ),
            MovementEvent(
                card_id=card.id,
                card_name=card.name,
                at=_dt(2026, 6, 1, 10),
                event_type="moved",
                from_list_name="REVISAO EM PAR",
                to_list_name="EM REVISAO",
            ),
            MovementEvent(
                card_id=card.id,
                card_name=card.name,
                at=_dt(2026, 6, 1, 10),
                event_type="moved",
                from_list_name="EM REVISAO",
                to_list_name="AGUARDANDO TESTE (LEGISLATIVO)",
            ),
            MovementEvent(
                card_id=card.id,
                card_name=card.name,
                at=_dt(2026, 6, 1, 11),
                event_type="moved",
                from_list_name="AGUARDANDO TESTE (LEGISLATIVO)",
                to_list_name="EM TESTE",
            ),
            MovementEvent(
                card_id=card.id,
                card_name=card.name,
                at=_dt(2026, 6, 1, 12),
                event_type="moved",
                from_list_name="EM TESTE",
                to_list_name="RETORNO (DEV)",
            ),
            MovementEvent(
                card_id=card.id,
                card_name=card.name,
                at=_dt(2026, 6, 1, 13),
                event_type="moved",
                from_list_name="RETORNO (DEV)",
                to_list_name="EM ANDAMENTO",
            ),
            MovementEvent(
                card_id=card.id,
                card_name=card.name,
                at=_dt(2026, 6, 1, 14),
                event_type="moved",
                from_list_name="EM ANDAMENTO",
                to_list_name="AGUARDANDO TESTE (LEGISLATIVO)",
            ),
            MovementEvent(
                card_id=card.id,
                card_name=card.name,
                at=_dt(2026, 6, 1, 15),
                event_type="moved",
                from_list_name="AGUARDANDO TESTE (LEGISLATIVO)",
                to_list_name="EM TESTE",
            ),
            MovementEvent(
                card_id=card.id,
                card_name=card.name,
                at=_dt(2026, 6, 1, 16),
                event_type="moved",
                from_list_name="EM TESTE",
                to_list_name="AGUARDANDO PRODUÇÃO (LEGISLATIVO)",
            ),
        ]

        result = MetricsEngine(
            self.workflow,
            now=_dt(2026, 6, 1, 17),
            month="2026-06",
        ).calculate(self._board(card, events)).to_dict()

        dev = result["developers"][0]
        tester = result["testers"][0]
        reviewer = result["reviewers"][0]
        formal_reviewer = next(
            role
            for collaborator in result["collaborators"]
            for role in collaborator["role_metrics"]
            if role["role_key"] == "revisor"
        )

        self.assertEqual(dev["return_dev_count"], 1)
        self.assertEqual(dev["tester_quality_returns"], 1)
        self.assertEqual(dev["cards_with_rework"], 1)
        self.assertEqual(dev["acceptance_rate_pct"], 0.0)
        self.assertEqual(result["team_summary"]["total_return_dev_events"], 1)
        self.assertEqual(result["team_summary"]["total_prevented_problems"], 1)
        self.assertEqual(result["team_summary"]["total_tester_quality_returns"], 1)
        self.assertEqual(result["team_summary"]["test_returns_missing_reason_count"], 1)
        self.assertEqual(result["team_summary"]["quality_rate_pct"], 0.0)
        self.assertEqual(reviewer["escaped_to_test"], 1)
        self.assertEqual(reviewer["approved"], 0)
        self.assertEqual(reviewer["approval_rate_pct"], 0.0)
        self.assertEqual(formal_reviewer["escaped_to_test"], 1)
        self.assertEqual(formal_reviewer["formal_review_passed"], 0)
        self.assertEqual(formal_reviewer["approval_rate_pct"], 0.0)
        self.assertEqual(tester["prevented_problems"], 1)
        self.assertEqual(tester["returned_dev_for_quality"], 1)
        self.assertEqual(tester["returns_missing_reason"], 1)
        self.assertEqual(tester["approved_first_pass"], 0)
        self.assertNotIn("quality_guarantee_approved", tester)
        self.assertNotIn("approval_rate_pct", tester)

    def test_waiting_test_return_dev_is_not_prevented_problem(self) -> None:
        card = TrelloCard(
            id="card_waiting_test_return",
            name="PM CLIENTE / Retorno antes do teste",
            current_list_id="dev",
            current_list_name="EM ANDAMENTO",
            created_at=_dt(2026, 6, 1, 9),
            custom_fields={
                "Desenvolvedor": "D-Matheus.Marinho",
                "Tester": "T-Genilson",
                "Nivel": "3",
                "Sistema": "Legislativo",
                "Solicitante": "S-Genilson",
            },
        )
        events = [
            MovementEvent(
                card_id=card.id,
                card_name=card.name,
                at=_dt(2026, 6, 1, 9),
                event_type="created",
                to_list_name="EM ANDAMENTO",
            ),
            MovementEvent(
                card_id=card.id,
                card_name=card.name,
                at=_dt(2026, 6, 1, 10),
                event_type="moved",
                from_list_name="EM ANDAMENTO",
                to_list_name="AGUARDANDO TESTE (LEGISLATIVO)",
            ),
            MovementEvent(
                card_id=card.id,
                card_name=card.name,
                at=_dt(2026, 6, 1, 11),
                event_type="moved",
                from_list_name="AGUARDANDO TESTE (LEGISLATIVO)",
                to_list_name="RETORNO (DEV)",
            ),
            MovementEvent(
                card_id=card.id,
                card_name=card.name,
                at=_dt(2026, 6, 1, 12),
                event_type="moved",
                from_list_name="RETORNO (DEV)",
                to_list_name="EM ANDAMENTO",
            ),
            MovementEvent(
                card_id=card.id,
                card_name=card.name,
                at=_dt(2026, 6, 1, 13),
                event_type="moved",
                from_list_name="EM ANDAMENTO",
                to_list_name="EM TESTE",
            ),
            MovementEvent(
                card_id=card.id,
                card_name=card.name,
                at=_dt(2026, 6, 1, 14),
                event_type="moved",
                from_list_name="EM TESTE",
                to_list_name="AGUARDANDO PRODUÃ‡ÃƒO (LEGISLATIVO)",
            ),
        ]

        result = MetricsEngine(
            self.workflow,
            now=_dt(2026, 6, 1, 15),
            month="2026-06",
        ).calculate(self._board(card, events)).to_dict()

        dev = result["developers"][0]
        tester = result["testers"][0]

        self.assertEqual(dev["return_dev_count"], 1)
        self.assertEqual(dev["tester_quality_returns"], 0)
        self.assertEqual(result["team_summary"]["total_tester_quality_returns"], 0)
        self.assertEqual(result["team_summary"]["total_prevented_problems"], 0)
        self.assertEqual(tester["prevented_problems"], 0)
        self.assertEqual(tester["returned_dev_for_quality"], 0)
        self.assertEqual(tester["tester_return_rate_pct"], 0.0)

    def test_placeholder_title_without_level_is_ignored(self) -> None:
        placeholder = TrelloCard(
            id="placeholder",
            name="PM CLIENTE / INFORMA O TÍTULO DO PROBLEMA",
            current_list_id="planning",
            current_list_name="PLANEJAMENTO",
            created_at=_dt(2026, 6, 1, 9),
            custom_fields={},
        )
        real_card = TrelloCard(
            id="real",
            name="PM CLIENTE / INFORMA O TÍTULO DO PROBLEMA",
            current_list_id="dev",
            current_list_name="EM ANDAMENTO",
            created_at=_dt(2026, 6, 1, 9),
            custom_fields={
                "Desenvolvedor": "D-Matheus.Marinho",
                "Nivel": "3",
                "Sistema": "Legislativo",
            },
        )
        board = BoardData(
            id="board1",
            name="Board",
            url="",
            lists={},
            cards=[placeholder, real_card],
            movements=[],
        )

        result = MetricsEngine(
            self.workflow,
            now=_dt(2026, 6, 1, 13),
        ).calculate(board).to_dict()

        self.assertEqual(result["overview"]["total_cards_metricados"], 1)
        self.assertEqual(result["overview"]["total_placeholders_ignorados"], 1)
        self.assertEqual(result["cards"][0]["id"], "real")

    def test_operational_metrics_flow_priority_dora_discipline_and_risk(self) -> None:
        delivered = TrelloCard(
            id="delivered_card",
            name="PM CLIENTE / Fluxo operacional",
            current_list_id="prod",
            current_list_name="EM PRODUCAO",
            created_at=_dt(2026, 6, 1, 9),
            custom_fields={
                "Desenvolvedor": "D-Dev.A",
                "Nivel": "3",
                "Sistema": "Legislativo",
                "Prioridade": "Urgente",
                "Solicitante": "S-Cliente",
                "Tester": "T-QA",
            },
        )
        open_card = TrelloCard(
            id="open_card",
            name="PM CLIENTE / Urgente parado",
            current_list_id="dev",
            current_list_name="EM ANDAMENTO",
            created_at=_dt(2026, 6, 1, 9),
            custom_fields={
                "Desenvolvedor": "D-Dev.A",
                "Nivel": "5",
                "Sistema": "Legislativo",
                "Prioridade": "Urgente",
                "Solicitante": "S-Cliente",
            },
        )
        events = [
            MovementEvent(
                card_id=delivered.id,
                card_name=delivered.name,
                at=_dt(2026, 6, 1, 9),
                event_type="created",
                to_list_name="PLANEJAMENTO",
            ),
            MovementEvent(
                card_id=delivered.id,
                card_name=delivered.name,
                at=_dt(2026, 6, 1, 10),
                event_type="moved",
                from_list_name="PLANEJAMENTO",
                to_list_name="AGUARDANDO APROVACAO",
            ),
            MovementEvent(
                card_id=delivered.id,
                card_name=delivered.name,
                at=_dt(2026, 6, 1, 11),
                event_type="moved",
                from_list_name="AGUARDANDO APROVACAO",
                to_list_name="BACKLOG",
            ),
            MovementEvent(
                card_id=delivered.id,
                card_name=delivered.name,
                at=_dt(2026, 6, 1, 12),
                event_type="moved",
                from_list_name="BACKLOG",
                to_list_name="EM ANDAMENTO",
            ),
            MovementEvent(
                card_id=delivered.id,
                card_name=delivered.name,
                at=_dt(2026, 6, 1, 13),
                event_type="moved",
                from_list_name="EM ANDAMENTO",
                to_list_name="AGUARDANDO DEPLOY",
            ),
            MovementEvent(
                card_id=delivered.id,
                card_name=delivered.name,
                at=_dt(2026, 6, 1, 14),
                event_type="moved",
                from_list_name="AGUARDANDO DEPLOY",
                to_list_name="AGUARDANDO TESTE (LEGISLATIVO)",
            ),
            MovementEvent(
                card_id=delivered.id,
                card_name=delivered.name,
                at=_dt(2026, 6, 1, 15),
                event_type="moved",
                from_list_name="AGUARDANDO TESTE (LEGISLATIVO)",
                to_list_name="EM TESTE",
            ),
            MovementEvent(
                card_id=delivered.id,
                card_name=delivered.name,
                at=_dt(2026, 6, 1, 16),
                event_type="moved",
                from_list_name="EM TESTE",
                to_list_name="AGUARDANDO PRODUCAO (LEGISLATIVO)",
            ),
            MovementEvent(
                card_id=delivered.id,
                card_name=delivered.name,
                at=_dt(2026, 6, 1, 17),
                event_type="moved",
                from_list_name="AGUARDANDO PRODUCAO (LEGISLATIVO)",
                to_list_name="EM PRODUCAO",
            ),
            MovementEvent(
                card_id=open_card.id,
                card_name=open_card.name,
                at=_dt(2026, 6, 1, 9),
                event_type="created",
                to_list_name="PLANEJAMENTO",
            ),
            MovementEvent(
                card_id=open_card.id,
                card_name=open_card.name,
                at=_dt(2026, 6, 1, 10),
                event_type="moved",
                from_list_name="PLANEJAMENTO",
                to_list_name="EM ANDAMENTO",
            ),
        ]
        board = BoardData(
            id="board1",
            name="Board",
            url="",
            lists={},
            cards=[delivered, open_card],
            movements=events,
            custom_field_changes=[
                CustomFieldChange(
                    card_id=open_card.id,
                    card_name=open_card.name,
                    field_name="Desenvolvedor",
                    at=_dt(2026, 6, 1, 11),
                    old_value=None,
                    new_value="D-Dev.A",
                )
            ],
        )

        result = MetricsEngine(
            self.workflow,
            now=_dt(2026, 6, 30),
            month="2026-06",
        ).calculate(board).to_dict()

        self.assertEqual(result["flow"]["team"]["lead_time"]["p85_hours"], 6.0)
        self.assertEqual(result["flow"]["team"]["cycle_time"]["p85_hours"], 3.0)
        self.assertEqual(result["flow"]["team"]["planning_to_approval_time"]["p85_hours"], 1.0)
        self.assertEqual(result["flow"]["team"]["wip_total"], 1)
        self.assertGreater(result["flow"]["team"]["little_law"]["predicted_lead_time_days"], 0)
        self.assertEqual(result["priority"]["urgent_critical_pct"], 100.0)
        self.assertEqual(result["dora"]["deployment_frequency"]["total"], 1)
        self.assertEqual(result["dora"]["lead_time_deploy"]["median_hours"], 1.0)
        self.assertEqual(result["process_discipline"]["flow_conformity"]["compliance_pct"], 100.0)
        self.assertEqual(
            result["process_discipline"]["developer_assignment_latency"]["median_hours"],
            2.0,
        )
        self.assertEqual(result["risk_board"]["high_or_critical_count"], 1)
        self.assertEqual(result["risk_board"]["cards_that_need_attention"][0]["level"], "critico")

    def test_trends_6m(self) -> None:
        card = TrelloCard(
            id="card6",
            name="PM CLIENTE / Entrega maio",
            current_list_id="wait_prod",
            current_list_name="AGUARDANDO PRODUÇÃO (OUTROS)",
            created_at=_dt(2026, 5, 10),
            custom_fields={"Desenvolvedor": "D-Dev.F", "Nível": "5", "Sistema": "Outros"},
        )
        events = [
            MovementEvent(
                card_id="card6",
                card_name=card.name,
                at=_dt(2026, 5, 20),
                event_type="moved",
                to_list_name="AGUARDANDO PRODUÇÃO (OUTROS)",
            )
        ]
        board = self._board(card, events)
        timelines = build_card_timelines(
            board.cards,
            {"card6": events},
            self.workflow,
            _dt(2026, 6, 30),
        )
        periods = [
            parse_month("2026-01"),
            parse_month("2026-02"),
            parse_month("2026-03"),
            parse_month("2026-04"),
            parse_month("2026-05"),
            parse_month("2026-06"),
        ]
        trends = aggregate_trends(timelines, board.cards, self.workflow, periods)
        may_row = next(row for row in trends["team"] if row["month"] == "2026-05")
        june_row = next(row for row in trends["team"] if row["month"] == "2026-06")
        self.assertEqual(may_row["fibonacci_normal"], 5)
        self.assertEqual(june_row["fibonacci_normal"], 0)

    def test_gestor_premature_approval_detected(self) -> None:
        card = TrelloCard(
            id="card_gestor",
            name="PM CLIENTE / Planejamento fraco",
            current_list_id="return_sup",
            current_list_name="RETORNO (SUP)",
            created_at=_dt(2026, 6, 3),
            custom_fields={
                "Desenvolvedor": "D-Dev.A",
                "Nível": "3",
                "Sistema": "Executivo",
                "Solicitante": "S-Solic.A",
            },
        )
        events = [
            MovementEvent(
                card_id="card_gestor",
                card_name=card.name,
                at=_dt(2026, 6, 4),
                event_type="moved",
                from_list_name="AGUARDANDO APROVAÇÃO",
                to_list_name="EM ANDAMENTO",
            ),
            MovementEvent(
                card_id="card_gestor",
                card_name=card.name,
                at=_dt(2026, 6, 12),
                event_type="moved",
                from_list_name="EM ANDAMENTO",
                to_list_name="RETORNO (SUP)",
            ),
            MovementEvent(
                card_id="card_gestor",
                card_name=card.name,
                at=_dt(2026, 6, 20),
                event_type="moved",
                from_list_name="EM TESTE",
                to_list_name="AGUARDANDO PRODUÇÃO (EXECUTIVO)",
            ),
        ]
        board = self._board(card, events)
        timelines = build_card_timelines(
            board.cards,
            {"card_gestor": events},
            self.workflow,
            _dt(2026, 6, 30),
        )
        self.assertTrue(timelines[0].gestor_premature_approval)
        self.assertEqual(timelines[0].dev_to_sup_return_count, 1)

        result = MetricsEngine(
            self.workflow,
            now=_dt(2026, 6, 30),
            month="2026-06",
        ).calculate(board).to_dict()
        requester = next(
            row for row in result["requesters"] if row["name"] == "S-Solic.A"
        )
        self.assertEqual(requester["gestor_premature_approvals"], 1)
        self.assertEqual(requester["planning_ok_rate_pct"], 0.0)

    def test_specific_metrics_filter_keeps_only_selected_keys(self) -> None:
        from trello_metrics.metrics.report_filter import filter_metrics

        full = {
            "board": {"name": "Board"},
            "period": {"month": "2026-06"},
            "team_summary": {"cards_delivered": 3},
            "developers": [{"name": "Dev"}],
            "requesters": [{"name": "Sol"}],
            "flow": {"team": {"wip_total": 2}},
        }
        filtered = filter_metrics(
            full,
            report_type="specific_metrics",
            metric_keys=["team_summary", "flow"],
        )
        self.assertIn("team_summary", filtered)
        self.assertIn("flow", filtered)
        self.assertNotIn("developers", filtered)
        self.assertNotIn("requesters", filtered)
        self.assertEqual(filtered["metric_keys"], ["team_summary", "flow"])

    def test_dora_deploy_paths_and_cfr_proxy(self) -> None:
        standard = TrelloCard(
            id="deploy_std",
            name="PM CLIENTE / Deploy normal",
            current_list_id="prod",
            current_list_name="EM PRODUCAO",
            created_at=_dt(2026, 6, 1, 8),
            custom_fields={
                "Desenvolvedor": "D-Dev.A",
                "Nivel": "3",
                "Sistema": "Legislativo",
                "Solicitante": "S-Sol",
            },
        )
        direct = TrelloCard(
            id="deploy_direct",
            name="PM CLIENTE / Hotfix direto",
            current_list_id="direct",
            current_list_name="DIRETAMENTE NA PRODUCAO",
            created_at=_dt(2026, 6, 2, 8),
            custom_fields={
                "Desenvolvedor": "D-Dev.B",
                "Nivel": "2",
                "Sistema": "Executivo",
                "Solicitante": "S-Sol",
            },
        )
        correction = TrelloCard(
            id="corr_1",
            name="PM CLIENTE / Correcao pos deploy",
            current_list_id="dev",
            current_list_name="EM ANDAMENTO",
            created_at=_dt(2026, 6, 3, 10),
            labels=["CORRECAO"],
            custom_fields={
                "Desenvolvedor": "D-Dev.A",
                "Nivel": "2",
                "Sistema": "Legislativo",
                "Solicitante": "S-Sol",
            },
        )
        events = [
            MovementEvent(
                card_id=standard.id,
                card_name=standard.name,
                at=_dt(2026, 6, 1, 9),
                event_type="created",
                to_list_name="EM ANDAMENTO",
            ),
            MovementEvent(
                card_id=standard.id,
                card_name=standard.name,
                at=_dt(2026, 6, 1, 12),
                event_type="moved",
                from_list_name="EM ANDAMENTO",
                to_list_name="AGUARDANDO TESTE (LEGISLATIVO)",
            ),
            MovementEvent(
                card_id=standard.id,
                card_name=standard.name,
                at=_dt(2026, 6, 1, 13),
                event_type="moved",
                from_list_name="AGUARDANDO TESTE (LEGISLATIVO)",
                to_list_name="EM TESTE",
            ),
            MovementEvent(
                card_id=standard.id,
                card_name=standard.name,
                at=_dt(2026, 6, 1, 14),
                event_type="moved",
                from_list_name="EM TESTE",
                to_list_name="AGUARDANDO PRODUCAO (LEGISLATIVO)",
            ),
            MovementEvent(
                card_id=standard.id,
                card_name=standard.name,
                at=_dt(2026, 6, 1, 15),
                event_type="moved",
                from_list_name="AGUARDANDO PRODUCAO (LEGISLATIVO)",
                to_list_name="EM PRODUCAO",
            ),
            MovementEvent(
                card_id=direct.id,
                card_name=direct.name,
                at=_dt(2026, 6, 2, 9),
                event_type="created",
                to_list_name="EM ANDAMENTO",
            ),
            MovementEvent(
                card_id=direct.id,
                card_name=direct.name,
                at=_dt(2026, 6, 2, 11),
                event_type="moved",
                from_list_name="EM ANDAMENTO",
                to_list_name="DIRETAMENTE NA PRODUCAO",
            ),
            MovementEvent(
                card_id=correction.id,
                card_name=correction.name,
                at=_dt(2026, 6, 3, 10),
                event_type="created",
                to_list_name="PLANEJAMENTO",
            ),
        ]
        board = BoardData(
            id="board1",
            name="Board",
            url="",
            lists={},
            cards=[standard, direct, correction],
            movements=events,
        )
        result = MetricsEngine(self.workflow, now=_dt(2026, 6, 30), month="2026-06").calculate(
            board
        ).to_dict()
        dora = result["dora"]
        by_path = dora["deployment_frequency"]["by_path"]
        self.assertEqual(dora["deployment_frequency"]["total"], 2)
        self.assertEqual(by_path["standard_production"], 1)
        self.assertEqual(by_path["direct_production"], 1)
        self.assertIn("PROXY", dora["cfr_note"].upper())
        cfr = dora["change_failure_rate"]
        self.assertEqual(cfr["failed_deployments"], 1)
        self.assertEqual(cfr["failures"][0]["deployment_card_id"], "deploy_std")
        self.assertEqual(cfr["failures"][0]["correction_card_id"], "corr_1")

    def test_direct_production_skips_test_in_discipline(self) -> None:
        direct = TrelloCard(
            id="direct_ok",
            name="PM CLIENTE / Hotfix",
            current_list_id="direct",
            current_list_name="DIRETAMENTE NA PRODUCAO",
            created_at=_dt(2026, 6, 5, 9),
            custom_fields={
                "Desenvolvedor": "D-Dev.A",
                "Nivel": "3",
                "Sistema": "Legislativo",
                "Solicitante": "S-Sol",
            },
        )
        skipped_test = TrelloCard(
            id="skip_test",
            name="PM CLIENTE / Pulou teste",
            current_list_id="prod",
            current_list_name="EM PRODUCAO",
            created_at=_dt(2026, 6, 6, 9),
            custom_fields={
                "Desenvolvedor": "D-Dev.B",
                "Nivel": "3",
                "Sistema": "Legislativo",
                "Solicitante": "S-Sol",
            },
        )
        events = [
            MovementEvent(
                card_id=direct.id,
                card_name=direct.name,
                at=_dt(2026, 6, 5, 10),
                event_type="created",
                to_list_name="EM ANDAMENTO",
            ),
            MovementEvent(
                card_id=direct.id,
                card_name=direct.name,
                at=_dt(2026, 6, 5, 12),
                event_type="moved",
                from_list_name="EM ANDAMENTO",
                to_list_name="DIRETAMENTE NA PRODUCAO",
            ),
            MovementEvent(
                card_id=skipped_test.id,
                card_name=skipped_test.name,
                at=_dt(2026, 6, 6, 10),
                event_type="created",
                to_list_name="EM ANDAMENTO",
            ),
            MovementEvent(
                card_id=skipped_test.id,
                card_name=skipped_test.name,
                at=_dt(2026, 6, 6, 12),
                event_type="moved",
                from_list_name="EM ANDAMENTO",
                to_list_name="AGUARDANDO PRODUCAO (LEGISLATIVO)",
            ),
            MovementEvent(
                card_id=skipped_test.id,
                card_name=skipped_test.name,
                at=_dt(2026, 6, 6, 13),
                event_type="moved",
                from_list_name="AGUARDANDO PRODUCAO (LEGISLATIVO)",
                to_list_name="EM PRODUCAO",
            ),
        ]
        board = BoardData(
            id="board1",
            name="Board",
            url="",
            lists={},
            cards=[direct, skipped_test],
            movements=events,
        )
        result = MetricsEngine(self.workflow, now=_dt(2026, 6, 30), month="2026-06").calculate(
            board
        ).to_dict()
        discipline = result["process_discipline"]
        violations = {
            item["card_id"]: item for item in discipline["flow_conformity"]["violations"]
        }
        self.assertNotIn("direct_ok", violations)
        self.assertIn("skip_test", violations)
        self.assertTrue(
            any("teste" in issue.lower() for issue in violations["skip_test"]["issues"])
        )

    def test_direct_production_from_peer_review_and_review(self) -> None:
        from_peer = TrelloCard(
            id="direct_peer",
            name="PM CLIENTE / Hotfix pos par",
            current_list_id="direct",
            current_list_name="DIRETAMENTE NA PRODUCAO",
            created_at=_dt(2026, 6, 9, 9),
            custom_fields={
                "Desenvolvedor": "D-Dev.A",
                "Nivel": "5",
                "Sistema": "Legislativo",
                "Solicitante": "S-Sol",
                "Revisor em Par": "R-Par.A",
            },
        )
        from_review = TrelloCard(
            id="direct_review",
            name="PM CLIENTE / Hotfix pos revisao",
            current_list_id="direct",
            current_list_name="DIRETAMENTE NA PRODUCAO",
            created_at=_dt(2026, 6, 10, 9),
            custom_fields={
                "Desenvolvedor": "D-Dev.B",
                "Nivel": "8",
                "Sistema": "Executivo",
                "Solicitante": "S-Sol",
                "Revisor": "R-Formal.B",
            },
        )
        events = [
            MovementEvent(
                card_id=from_peer.id,
                card_name=from_peer.name,
                at=_dt(2026, 6, 9, 10),
                event_type="created",
                to_list_name="REVISAO EM PAR",
            ),
            MovementEvent(
                card_id=from_peer.id,
                card_name=from_peer.name,
                at=_dt(2026, 6, 9, 12),
                event_type="moved",
                from_list_name="REVISAO EM PAR",
                to_list_name="DIRETAMENTE NA PRODUCAO",
            ),
            MovementEvent(
                card_id=from_review.id,
                card_name=from_review.name,
                at=_dt(2026, 6, 10, 10),
                event_type="created",
                to_list_name="EM ANDAMENTO",
            ),
            MovementEvent(
                card_id=from_review.id,
                card_name=from_review.name,
                at=_dt(2026, 6, 10, 11),
                event_type="moved",
                from_list_name="EM ANDAMENTO",
                to_list_name="AGUARDANDO REVISAO FORMAL",
            ),
            MovementEvent(
                card_id=from_review.id,
                card_name=from_review.name,
                at=_dt(2026, 6, 10, 12),
                event_type="moved",
                from_list_name="AGUARDANDO REVISAO FORMAL",
                to_list_name="EM REVISAO",
            ),
            MovementEvent(
                card_id=from_review.id,
                card_name=from_review.name,
                at=_dt(2026, 6, 10, 13),
                event_type="moved",
                from_list_name="EM REVISAO",
                to_list_name="DIRETAMENTE NA PRODUCAO",
            ),
        ]
        board = BoardData(
            id="board1",
            name="Board",
            url="",
            lists={},
            cards=[from_peer, from_review],
            movements=events,
        )
        result = MetricsEngine(self.workflow, now=_dt(2026, 6, 30), month="2026-06").calculate(
            board
        ).to_dict()
        violations = {
            item["card_id"]: item
            for item in result["process_discipline"]["flow_conformity"]["violations"]
        }
        self.assertNotIn("direct_peer", violations)
        self.assertNotIn("direct_review", violations)

    def test_post_terminal_return_after_production(self) -> None:
        card = TrelloCard(
            id="post_term",
            name="PM CLIENTE / Retorno pos prod",
            current_list_id="return_dev",
            current_list_name="RETORNO (DEV)",
            created_at=_dt(2026, 6, 4, 9),
            custom_fields={
                "Desenvolvedor": "D-Dev.A",
                "Nivel": "3",
                "Sistema": "Legislativo",
                "Solicitante": "S-Sol",
            },
        )
        events = [
            MovementEvent(
                card_id=card.id,
                card_name=card.name,
                at=_dt(2026, 6, 4, 10),
                event_type="created",
                to_list_name="EM ANDAMENTO",
            ),
            MovementEvent(
                card_id=card.id,
                card_name=card.name,
                at=_dt(2026, 6, 4, 12),
                event_type="moved",
                from_list_name="EM ANDAMENTO",
                to_list_name="AGUARDANDO PRODUCAO (LEGISLATIVO)",
            ),
            MovementEvent(
                card_id=card.id,
                card_name=card.name,
                at=_dt(2026, 6, 4, 13),
                event_type="moved",
                from_list_name="AGUARDANDO PRODUCAO (LEGISLATIVO)",
                to_list_name="EM PRODUCAO",
            ),
            MovementEvent(
                card_id=card.id,
                card_name=card.name,
                at=_dt(2026, 6, 4, 15),
                event_type="moved",
                from_list_name="EM PRODUCAO",
                to_list_name="RETORNO (DEV)",
            ),
        ]
        board = self._board(card, events)
        result = MetricsEngine(self.workflow, now=_dt(2026, 6, 30), month="2026-06").calculate(
            board
        ).to_dict()
        post = result["process_discipline"]["post_terminal_returns"]
        self.assertEqual(post["count"], 1)
        self.assertEqual(post["cards"][0]["card_id"], "post_term")
        violations = result["process_discipline"]["flow_conformity"]["violations"]
        self.assertTrue(any(item["card_id"] == "post_term" for item in violations))

    def test_analysis_workflow_metrics(self) -> None:
        complete = TrelloCard(
            id="anal_ok",
            name="ANALISE / Fluxo completo",
            current_list_id="done",
            current_list_name="ANALISES FINALIZADAS",
            created_at=_dt(2026, 6, 7, 9),
            custom_fields={
                "Desenvolvedor": "D-Dev.A",
                "Nivel (Analise)": "2",
                "Sistema": "Legislativo",
                "Solicitante": "S-Sol",
            },
            description_data=CardDescriptionData(
                analise_realizada="Analise feita",
                recomendacao="Implementar melhoria",
            ),
        )
        incomplete = TrelloCard(
            id="anal_bad",
            name="ANALISE / Descricao incompleta",
            current_list_id="plan",
            current_list_name="ANALISES PARA PLANEJAMENTO",
            created_at=_dt(2026, 6, 8, 9),
            custom_fields={
                "Desenvolvedor": "D-Dev.B",
                "Nivel (Analise)": "1",
                "Sistema": "Executivo",
                "Solicitante": "S-Sol",
            },
        )
        events = [
            MovementEvent(
                card_id=complete.id,
                card_name=complete.name,
                at=_dt(2026, 6, 7, 10),
                event_type="created",
                to_list_name="EM ANDAMENTO",
            ),
            MovementEvent(
                card_id=complete.id,
                card_name=complete.name,
                at=_dt(2026, 6, 7, 11),
                event_type="moved",
                from_list_name="EM ANDAMENTO",
                to_list_name="ANALISES PARA PLANEJAMENTO",
            ),
            MovementEvent(
                card_id=complete.id,
                card_name=complete.name,
                at=_dt(2026, 6, 7, 13),
                event_type="moved",
                from_list_name="ANALISES PARA PLANEJAMENTO",
                to_list_name="ANALISES FINALIZADAS",
            ),
            MovementEvent(
                card_id=incomplete.id,
                card_name=incomplete.name,
                at=_dt(2026, 6, 8, 10),
                event_type="created",
                to_list_name="EM ANDAMENTO",
            ),
            MovementEvent(
                card_id=incomplete.id,
                card_name=incomplete.name,
                at=_dt(2026, 6, 8, 11),
                event_type="moved",
                from_list_name="EM ANDAMENTO",
                to_list_name="ANALISES PARA PLANEJAMENTO",
            ),
        ]
        board = BoardData(
            id="board1",
            name="Board",
            url="",
            lists={},
            cards=[complete, incomplete],
            movements=events,
        )
        result = MetricsEngine(self.workflow, now=_dt(2026, 6, 30), month="2026-06").calculate(
            board
        ).to_dict()
        analysis = result["analysis_workflow"]
        self.assertEqual(analysis["analysis_delivered"], 1)
        self.assertEqual(analysis["analysis_in_planning_wip"], 1)
        self.assertEqual(analysis["descricao_completa_count"], 1)
        self.assertEqual(analysis["descricao_completa_pct"], 50.0)

    def _board(self, card: TrelloCard, movements: list[MovementEvent]) -> BoardData:
        return BoardData(
            id="board1",
            name="Board",
            url="",
            lists={
                "dev": TrelloList(id="dev", name="EM ANDAMENTO"),
                "return_dev": TrelloList(id="return_dev", name="RETORNO (DEV)"),
            },
            cards=[card],
            movements=movements,
        )


if __name__ == "__main__":
    unittest.main()
