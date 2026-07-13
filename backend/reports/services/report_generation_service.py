from __future__ import annotations

from typing import Any

from django.conf import settings
from django.db import transaction

from reports.clients.trello_client import TrelloApiClient
from reports.dataclasses.report_config import ReportGenerationConfig
from reports.models import GeneratedReport
from reports.services.ai_analysis_service import AIAnalysisService
from reports.services.metrics_selection_service import MetricsSelectionService
from reports.services.trello_snapshot_service import TrelloSnapshotService
from reports.utils.text import title_or_fallback
from trello_metrics.config import load_workflow_config
from trello_metrics.metrics.engine import MetricsEngine
from trello_metrics.parsers.export_loader import parse_board_export


class ReportGenerationService:
    def __init__(
        self,
        trello_client: TrelloApiClient | None = None,
        selector: MetricsSelectionService | None = None,
        ai_service: AIAnalysisService | None = None,
        snapshot_service: TrelloSnapshotService | None = None,
    ) -> None:
        self.trello_client = trello_client or TrelloApiClient()
        self.selector = selector or MetricsSelectionService()
        self.ai_service = ai_service or AIAnalysisService()
        self.snapshot_service = snapshot_service or TrelloSnapshotService()

    @transaction.atomic
    def generate(self, config: ReportGenerationConfig, created_by: str = "") -> GeneratedReport:
        source_config = config.trello
        if source_config.use_live_api and not source_config.board_id:
            source_config = type(source_config)(
                board_id=settings.DEFAULT_TRELLO_BOARD_ID,
                api_key=source_config.api_key,
                token=source_config.token,
                use_live_api=source_config.use_live_api,
                source_json=source_config.source_json,
            )

        trello_payload = self.trello_client.fetch_board_export(source_config)
        parsed_board = parse_board_export(trello_payload)
        snapshot = self.snapshot_service.persist_board(
            parsed_board,
            source="api" if source_config.use_live_api else "json",
        )
        # Calcula no board parseado (nao no roundtrip do snapshot) para nao perder
        # source_card_id de copyCard — necessario ao antifraude.
        workflow = load_workflow_config()
        metrics = MetricsEngine(
            workflow,
            include_templates=config.include_templates,
            month=config.month,
            history_months=config.history_months,
            timezone_name=config.timezone,
        ).calculate(parsed_board).to_dict()

        filtered_metrics = self.selector.build_payload(metrics, config)
        ai_result = self.ai_service.generate(filtered_metrics, config, full_metrics=metrics)
        if ai_result.text:
            filtered_metrics["ai_analysis"] = ai_result.text
            filtered_metrics["ai"] = {
                "provider": ai_result.provider,
                "model": ai_result.model,
                "status": ai_result.status,
            }

        board_info = metrics.get("board") or {}
        return GeneratedReport.objects.create(
            title=_report_title(config, board_info),
            report_type=config.report_type,
            month=config.month,
            collaborator_name=config.collaborator_name,
            metric_keys=config.metric_keys,
            board_id=board_info.get("id", ""),
            board_name=board_info.get("name", ""),
            board_url=board_info.get("url", ""),
            trello_snapshot=snapshot,
            metrics=metrics,
            filtered_metrics=filtered_metrics,
            ai_provider=ai_result.provider,
            ai_model=ai_result.model,
            ai_status=ai_result.status,
            ai_analysis=ai_result.text,
            ai_error=ai_result.error,
            created_by=created_by,
        )


def _report_title(config: ReportGenerationConfig, board_info: dict[str, Any]) -> str:
    board_name = title_or_fallback(board_info.get("name"), "Trello")
    label = {
        "general": "Relatorio geral",
        "individual": f"Relatorio individual - {config.collaborator_name}",
        "developers": "Relatorio de desenvolvedores",
        "requesters": "Relatorio de solicitantes",
        "testers": "Relatorio de testers",
        "management": "Relatorio de gestao",
        "specific_metrics": "Relatorio de metricas especificas",
    }.get(config.report_type, "Relatorio")
    return f"{label} | {board_name} | {config.month}"
