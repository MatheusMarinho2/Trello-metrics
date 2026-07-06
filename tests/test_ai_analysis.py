from __future__ import annotations

import json
import unittest
from unittest.mock import MagicMock, patch

from reports.dataclasses.report_config import AIProviderConfig, ReportGenerationConfig, TrelloSourceConfig
from reports.services.ai_analysis_service import AIAnalysisService
from reports.services.ai_context_builder import build_ai_context
from reports.services.ai_prompts import FIVE_CORE_QUESTIONS, build_user_prompt


class AIAnalysisTests(unittest.TestCase):
    def test_context_includes_trends_from_full_metrics(self) -> None:
        filtered = {
            "report_type": "developers",
            "team_summary": {"cards_delivered": 3},
            "developers": [{"name": "Dev.A", "cards_delivered": 2}],
        }
        full = {
            **filtered,
            "trends_6m": {
                "months": ["2026-05", "2026-06"],
                "team": [{"month": "2026-06", "quality_rate_pct": 88}],
            },
            "collaborators": [{"name": "Dev.A", "roles": ["Desenvolvedor"], "summary": {"cards_delivered": 2}}],
        }
        context = build_ai_context(filtered, full)
        self.assertIn("trends_6m", context)
        self.assertEqual(context["developers"][0]["name"], "Dev.A")

    def test_prompt_has_five_questions_and_structure(self) -> None:
        prompt = build_user_prompt(
            report_type="general",
            month="2026-07",
            collaborator_name="",
            metrics_json='{"team_summary": {"cards_delivered": 1}}',
        )
        self.assertIn("## Colaboradores", prompt)
        self.assertIn("Leitura operacional aprofundada", prompt)
        self.assertIn("Retornos, pausas e cards de analise", prompt)
        self.assertIn("Problemas do fluxo por coluna", prompt)
        prompt_with_people = build_user_prompt(
            report_type="general",
            month="2026-07",
            collaborator_name="",
            metrics_json='{"collaborators_total": 2}',
            collaborators_total=2,
        )
        self.assertIn("Positivos", prompt_with_people)
        self.assertIn("Negativos", prompt_with_people)
        for question in FIVE_CORE_QUESTIONS:
            self.assertIn(question.split("?")[0][:20], prompt)

    @patch("reports.services.ai_analysis_service.build_ai_client")
    def test_generate_requires_api_key(self, mock_build: MagicMock) -> None:
        service = AIAnalysisService()
        config = ReportGenerationConfig(
            report_type="general",
            month="2026-07",
            trello=TrelloSourceConfig(use_live_api=False),
            ai=AIProviderConfig(enabled=True, api_key=""),
        )
        result = service.generate({"team_summary": {}}, config)
        self.assertEqual(result.status, "skipped")
        mock_build.assert_not_called()

    @patch("reports.services.ai_analysis_service.build_ai_client")
    def test_generate_calls_model_with_structured_prompt(self, mock_build: MagicMock) -> None:
        client = MagicMock()
        client.model = "gpt-4o-mini"
        client.generate.side_effect = [
            "# Analise INTGEST — 2026-07\n\n## Resumo executivo\nOk.",
            "## Retornos, pausas e cards de analise\n\n## Conclusao para gestao\nFim.",
        ]
        mock_build.return_value = client

        service = AIAnalysisService()
        config = ReportGenerationConfig(
            report_type="general",
            month="2026-07",
            trello=TrelloSourceConfig(use_live_api=False),
            ai=AIProviderConfig(enabled=True, api_key="test-key", provider="openai"),
        )
        result = service.generate(
            {"team_summary": {"cards_delivered": 5}, "collaborators": []},
            config,
            full_metrics={"trends_6m": {"months": ["2026-07"], "team": []}},
        )
        self.assertEqual(result.status, "generated")
        self.assertIn("Resumo executivo", result.text or "")
        self.assertIn("Conclusao para gestao", result.text or "")
        self.assertEqual(client.generate.call_count, 2)
        first_prompt = client.generate.call_args_list[0].kwargs["user_prompt"]
        self.assertIn("5 perguntas", first_prompt.lower())
        self.assertIn("PARTE 1", first_prompt)
        second_prompt = client.generate.call_args_list[1].kwargs["user_prompt"]
        self.assertIn("PARTE 2", second_prompt)

    def test_context_keeps_all_collaborators(self) -> None:
        rows = [
            {
                "name": f"Dev.{index}",
                "roles": ["Desenvolvedor"],
                "summary": {"cards_delivered": index},
                "role_metrics": [{"role_label": "Desenvolvedor", "cards_delivered": index}],
            }
            for index in range(1, 12)
        ]
        context = build_ai_context({"report_type": "general"}, {"collaborators": rows})
        self.assertEqual(context["collaborators_total"], 11)
        self.assertEqual(len(context["collaborators"]), 11)

    @patch("reports.services.ai_analysis_service.build_ai_client")
    def test_general_report_batches_collaborators(self, mock_build: MagicMock) -> None:
        client = MagicMock()
        client.model = "gemini-2.5-flash"
        client.generate.side_effect = [
            "# Base parte 1",
            "## Retornos\n\n## Conclusao para gestao\nFim.",
            "### Dev.1\n- ok",
            "### Dev.7\n- ok",
        ]
        mock_build.return_value = client

        rows = [
            {
                "name": f"Dev.{index}",
                "roles": ["Desenvolvedor"],
                "summary": {"cards_delivered": 1},
                "role_metrics": [],
            }
            for index in range(1, 8)
        ]
        config = ReportGenerationConfig(
            report_type="general",
            month="2026-07",
            trello=TrelloSourceConfig(use_live_api=False),
            ai=AIProviderConfig(enabled=True, provider="gemini", api_key="k"),
        )
        result = AIAnalysisService().generate({"report_type": "general"}, config, full_metrics={"collaborators": rows})
        self.assertEqual(result.status, "generated")
        self.assertIn("## Colaboradores", result.text or "")
        self.assertEqual(client.generate.call_count, 4)

    @patch("reports.services.ai_analysis_service.build_ai_client")
    def test_individual_report_uses_two_part_generation(self, mock_build: MagicMock) -> None:
        client = MagicMock()
        client.model = "gemini-2.5-flash"
        client.generate.side_effect = [
            "# Analise\n\n## Resumo executivo\nOk.",
            "## Resumo individual — Dev.A\n\n## Conclusao para gestao\nFim.",
        ]
        mock_build.return_value = client

        config = ReportGenerationConfig(
            report_type="individual",
            month="2026-07",
            collaborator_name="Dev.A",
            trello=TrelloSourceConfig(use_live_api=False),
            ai=AIProviderConfig(enabled=True, provider="gemini", api_key="k"),
        )
        result = AIAnalysisService().generate(
            {"report_type": "individual", "team_summary": {}},
            config,
            full_metrics={"collaborators": [{"name": "Dev.A", "roles": ["Desenvolvedor"], "summary": {}}]},
        )
        self.assertEqual(result.status, "generated")
        self.assertIn("Resumo individual", result.text or "")
        self.assertEqual(client.generate.call_count, 2)
        second_prompt = client.generate.call_args_list[1].kwargs["user_prompt"]
        self.assertIn("Resumo individual", second_prompt)

    def test_returns_pauses_insights_from_dossier(self) -> None:
        from reports.services.ai_returns_context import build_returns_pauses_insights

        dossier = {
            "by_developer": {
                "Dev.A": {
                    "tarefas_normais": [
                        {
                            "card_id": "1",
                            "card_name": "Card A",
                            "kind": "problem",
                            "sistema": "ERP",
                            "desenvolvedor": "Dev.A",
                            "return_dev_count": 2,
                            "pause_count": 1,
                            "retornos": [
                                {
                                    "tipo": "dev",
                                    "subtipo": "Retorno teste",
                                    "motivo": "Bug na validacao",
                                    "atribuido_a": "tester",
                                }
                            ],
                            "pausas": [{"motivo": "Aguardando cliente"}],
                            "descricao": {},
                        }
                    ],
                    "cards_analise": [
                        {
                            "card_id": "2",
                            "card_name": "Analise B",
                            "kind": "analysis",
                            "sistema": "ERP",
                            "desenvolvedor": "Dev.A",
                            "return_dev_count": 0,
                            "pause_count": 0,
                            "retornos": [],
                            "pausas": [],
                            "descricao": {"solicitacao_analise": "Investigar erro"},
                        }
                    ],
                }
            }
        }
        insights = build_returns_pauses_insights(
            card_dossier=dossier,
            team_summary={"rework_rate_pct": 20, "total_return_dev_events": 2},
            quality_gates=None,
        )
        self.assertEqual(insights["cards_evaluated"], 2)
        self.assertGreaterEqual(len(insights["highlight_cards"]), 1)
        self.assertGreaterEqual(len(insights["analysis_cards"]), 1)
        self.assertTrue(insights["top_pause_motives"])

    def test_questionable_tester_return_detected(self) -> None:
        from reports.services.ai_returns_context import build_returns_pauses_insights

        dossier = {
            "by_developer": {
                "Dev.A": {
                    "tarefas_normais": [
                        {
                            "card_id": "1",
                            "card_name": "Card A",
                            "kind": "problem",
                            "desenvolvedor": "Dev.A",
                            "tester": "Test.B",
                            "return_dev_count": 1,
                            "return_dev_by_teste_count": 1,
                            "return_dev_by_revisao_count": 0,
                            "test_return_missing_reason_count": 0,
                            "pause_count": 0,
                            "retornos": [
                                {
                                    "numero": 1,
                                    "tipo": "dev",
                                    "subtipo": "Retorno teste",
                                    "motivo": "ok",
                                    "solucao": "Comportamento esperado do sistema em homologacao",
                                    "atribuido_a": "tester",
                                }
                            ],
                            "pausas": [],
                            "descricao": {},
                        }
                    ],
                    "cards_analise": [],
                }
            }
        }
        insights = build_returns_pauses_insights(
            card_dossier=dossier,
            team_summary={"rework_rate_pct": 20},
            quality_gates=None,
        )
        questionable = insights["questionable_returns"]
        self.assertTrue(questionable)
        self.assertEqual(questionable[0].get("card_id"), "1")
        self.assertTrue(questionable[0].get("injustice_reasons"))
        self.assertTrue(any(item.get("possibly_unfair_to_developer") for item in questionable))
        self.assertTrue(
            any("solucao_indica_causa_fora_do_codigo" in (item.get("fairness_flags") or []) for item in questionable)
        )

    def test_context_includes_returns_pauses_insights(self) -> None:
        dossier = {
            "by_developer": {
                "Dev.A": {
                    "tarefas_normais": [
                        {
                            "card_id": "1",
                            "card_name": "Card A",
                            "kind": "problem",
                            "desenvolvedor": "Dev.A",
                            "return_dev_count": 1,
                            "pause_count": 0,
                            "retornos": [{"tipo": "dev", "motivo": "Ajuste", "subtipo": "dev"}],
                            "pausas": [],
                            "descricao": {},
                        }
                    ],
                    "cards_analise": [],
                }
            }
        }
        context = build_ai_context(
            {"report_type": "general", "team_summary": {"cards_delivered": 1}},
            {"collaborators": [], "card_dossier": dossier},
        )
        self.assertIn("returns_pauses_insights", context)
        self.assertEqual(context["returns_pauses_insights"]["cards_evaluated"], 1)

    def test_flow_column_insights_ranks_inconsistent_columns(self) -> None:
        from reports.services.ai_flow_context import build_flow_column_insights

        insights = build_flow_column_insights(
            flow={
                "stage_time": [
                    {"group": "testing", "title": "Teste", "median_hours": 10, "p95_hours": 40, "p95_human": "1d 16h"},
                ],
                "wip_by_stage": [{"group": "testing", "title": "Teste", "count": 9}],
            },
            bottlenecks={
                "top_bottleneck": {"title": "Teste", "avg_human": "2d"},
                "by_stage": [{"group": "testing", "title": "Teste", "avg_hours": 50, "avg_human": "2d 2h", "samples": 4}],
                "stuck_now": [{"card": "Card X", "list": "Teste", "group": "Teste", "days_stuck": 5, "responsavel": "Dev.A"}],
            },
            sla={
                "by_stage": [
                    {"group": "testing", "title": "Teste", "checks": 10, "breached_count": 4, "compliance_pct": 60.0},
                ],
            },
            process_discipline={
                "flow_conformity": {"compliance_pct": 70, "cards_evaluated": 10, "compliant_count": 7, "violations": []},
                "skipped_stages": [{"group": "testing", "title": "Teste", "count": 3, "optional": False}],
            },
        )
        ranked = insights["columns_ranked_by_inconsistency"]
        self.assertTrue(ranked)
        self.assertEqual(ranked[0]["title"], "Teste")
        self.assertGreater(ranked[0]["inconsistency_score"], 0)
        self.assertTrue(insights["principal_flow_problems"])

    def test_context_includes_flow_column_insights(self) -> None:
        context = build_ai_context(
            {"report_type": "general"},
            {
                "flow": {"wip_by_stage": [{"group": "development", "title": "Desenvolvimento", "count": 2}]},
                "bottlenecks": {"by_stage": []},
                "sla": {"by_stage": []},
                "process_discipline": {},
            },
        )
        self.assertIn("flow_column_insights", context)
        self.assertIn("columns_ranked_by_inconsistency", context["flow_column_insights"])

    def test_effective_max_output_tokens_uses_model_cap(self) -> None:
        from reports.services.ai_models import DEFAULT_MAX_OUTPUT_TOKENS, effective_max_output_tokens

        self.assertEqual(
            effective_max_output_tokens("gemini", "gemini-2.5-flash", DEFAULT_MAX_OUTPUT_TOKENS),
            65_536,
        )
        self.assertEqual(
            effective_max_output_tokens("openai", "gpt-4o-mini", DEFAULT_MAX_OUTPUT_TOKENS),
            16_384,
        )

    def test_gemini_retired_model_is_remapped(self) -> None:
        from reports.clients.ai_client import GeminiGenerateContentClient
        from reports.services.ai_models import resolve_model

        self.assertEqual(resolve_model("gemini", "gemini-2.0-flash"), "gemini-2.5-flash")
        self.assertEqual(resolve_model("gemini", "gemini-1.5-flash"), "gemini-2.5-flash")
        client = GeminiGenerateContentClient(
            AIProviderConfig(enabled=True, provider="gemini", api_key="k", model="gemini-2.0-flash"),
        )
        self.assertEqual(client.model, "gemini-2.5-flash")

    def test_report_options_exposes_active_models(self) -> None:
        from reports.services.options_service import report_options

        options = report_options()
        gemini = next(item for item in options["ai_providers"] if item["value"] == "gemini")
        model_ids = {item["value"] for item in gemini["models"]}
        self.assertEqual(gemini["default_model"], "gemini-2.5-flash")
        self.assertIn("gemini-2.5-flash", model_ids)
        self.assertNotIn("gemini-2.0-flash", model_ids)


if __name__ == "__main__":
    unittest.main()
