from __future__ import annotations

from copy import deepcopy
import json
import re
import tempfile
import unicodedata
from pathlib import Path
from typing import Any

from django.http import HttpResponse

from reports.models import GeneratedReport
from reports.services.metrics_selection_service import MetricsSelectionService
from trello_metrics.reports.html_report import write_html_report
from trello_metrics.reports.pdf_report import write_pdf_report


class ReportExportService:
    def json_response(self, report: GeneratedReport) -> HttpResponse:
        payload = self._export_payload(report)
        response = HttpResponse(
            json.dumps(payload, ensure_ascii=False, indent=2),
            content_type="application/json; charset=utf-8",
        )
        response["Content-Disposition"] = f'attachment; filename="{_filename(report, "json")}"'
        return response

    def pdf_response(self, report: GeneratedReport) -> HttpResponse:
        metrics = self._metrics_for_document(report)
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / _filename(report, "pdf")
            write_pdf_report(metrics, output)
            content = output.read_bytes()

        response = HttpResponse(content, content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="{_filename(report, "pdf")}"'
        return response

    def html_response(self, report: GeneratedReport) -> HttpResponse:
        metrics = self._metrics_for_document(report)
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / _filename(report, "html")
            write_html_report(metrics, output)
            content = output.read_bytes()

        response = HttpResponse(content, content_type="text/html; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="{_filename(report, "html")}"'
        return response

    def _metrics_for_document(self, report: GeneratedReport) -> dict[str, Any]:
        metrics = MetricsSelectionService().with_card_metadata(
            deepcopy(report.filtered_metrics or report.metrics or {}),
            report.metrics or {},
        )
        board = metrics.get("board") or {}
        metrics["board"] = {
            **board,
            "id": board.get("id") or report.board_id,
            "name": board.get("name") or report.board_name,
            "url": board.get("url") or report.board_url,
        }
        metrics["export_meta"] = {
            "report_id": str(report.id),
            "title": report.title,
            "report_type": report.report_type,
            "month": report.month,
            "collaborator_name": report.collaborator_name,
            "created_at": report.created_at.isoformat(),
        }
        if report.ai_analysis:
            metrics["ai_analysis"] = report.ai_analysis
        if report.ai_status:
            metrics["ai"] = {
                "provider": report.ai_provider,
                "model": report.ai_model,
                "status": report.ai_status,
            }
        return metrics

    def _export_payload(self, report: GeneratedReport) -> dict[str, Any]:
        return {
            "id": str(report.id),
            "title": report.title,
            "report_type": report.report_type,
            "month": report.month,
            "collaborator_name": report.collaborator_name,
            "board": {
                "id": report.board_id,
                "name": report.board_name,
                "url": report.board_url,
            },
            "metrics": self._metrics_for_document(report),
            "ai": {
                "status": report.ai_status,
                "provider": report.ai_provider,
                "model": report.ai_model,
                "analysis": report.ai_analysis,
                "error": report.ai_error,
            },
            "created_at": report.created_at.isoformat(),
        }


REPORT_TYPE_SLUGS = {
    "general": "geral",
    "individual": "individual",
    "developers": "desenvolvedores",
    "requesters": "solicitantes",
    "testers": "testers",
    "management": "gestao",
    "specific_metrics": "metricas",
}


def _slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value or "")
    ascii_only = normalized.encode("ascii", "ignore").decode("ascii")
    ascii_only = re.sub(r"[^A-Za-z0-9]+", "-", ascii_only).strip("-").lower()
    return ascii_only


def _filename(report: GeneratedReport, extension: str) -> str:
    tipo = REPORT_TYPE_SLUGS.get(report.report_type, report.report_type)
    safe_month = (report.month or "").replace("/", "-")
    parts = ["intgest", tipo]
    if report.collaborator_name:
        colaborador = _slugify(report.collaborator_name)
        if colaborador:
            parts.append(colaborador)
    if safe_month:
        parts.append(safe_month)
    name = "_".join(parts)
    return f"{name}.{extension}"
