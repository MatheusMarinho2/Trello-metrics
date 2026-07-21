from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "intgest_reports.settings")

import django

django.setup()

from reports.dataclasses.report_config import (
    AIProviderConfig,
    ReportGenerationConfig,
    TrelloSourceConfig,
)
from reports.serializers import ReportGenerationSerializer
from reports.services.metrics_selection_service import MetricsSelectionService


class BySystemSelectionTests(unittest.TestCase):
    def test_by_system_payload_includes_project_summary(self) -> None:
        metrics = {
            "board": {"id": "b1", "name": "Board"},
            "period": {"month": "2026-06"},
            "overview": {"total_cards_metricados": 2},
            "data_quality": {},
            "systems": ["Legislativo", "Executivo"],
            "sistema_filter": "Legislativo",
            "project_summary": {
                "name": "Legislativo",
                "cards_delivered": 4,
                "wip_total": 2,
                "cards_archived": 1,
                "fibonacci_total": 13,
                "rework_rate_pct": 10,
                "quality_rate_pct": 90,
            },
            "flow": {"team": {"cards_delivered": 4, "wip_total": 2}},
            "bottlenecks": {"by_stage": []},
            "trends_6m": {"team": []},
            "developers": [{"name": "D-Dev.A", "cards_delivered": 2}],
            "collaborators": [
                {
                    "name": "D-Dev.A",
                    "roles": ["Desenvolvedor"],
                    "summary": {"cards_delivered": 2, "fibonacci_total": 5},
                }
            ],
            "card_dossier": {"by_developer": {}},
        }
        config = ReportGenerationConfig(
            report_type="by_system",
            month="2026-06",
            trello=TrelloSourceConfig(),
            ai=AIProviderConfig(),
            sistema_name="Legislativo",
        )
        payload = MetricsSelectionService().build_payload(metrics, config)
        self.assertEqual(payload["project_summary"]["name"], "Legislativo")
        self.assertEqual(payload["role_summary"]["scope"], "by_system")
        self.assertEqual(payload["role_summary"]["cards_delivered"], 4)
        self.assertIn("flow", payload)
        self.assertIn("systems", payload)
        self.assertIn("collaborators", payload)

    def test_serializer_requires_sistema_name(self) -> None:
        serializer = ReportGenerationSerializer(
            data={
                "report_type": "by_system",
                "month": "2026-06",
                "trello": {"use_live_api": True, "board_id": "board"},
            }
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn("sistema_name", serializer.errors)

    def test_serializer_accepts_by_system(self) -> None:
        serializer = ReportGenerationSerializer(
            data={
                "report_type": "by_system",
                "month": "2026-06",
                "sistema_name": "Legislativo",
                "trello": {"use_live_api": True, "board_id": "board"},
            }
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        config = serializer.to_config()
        self.assertEqual(config.report_type, "by_system")
        self.assertEqual(config.sistema_name, "Legislativo")


if __name__ == "__main__":
    unittest.main()
