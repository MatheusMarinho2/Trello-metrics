from __future__ import annotations

from pathlib import Path
from typing import Any


def write_pdf_report(metrics: dict[str, Any], output_path: str | Path) -> Path:
    """Gera PDF com layout IntGest (HTML + Playwright), mantendo os mesmos dados."""
    from trello_metrics.reports.pdf_intgest import build_pdf_report

    return build_pdf_report(metrics, output_path)
