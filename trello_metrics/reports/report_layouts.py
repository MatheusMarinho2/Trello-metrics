from __future__ import annotations

from typing import Any

# Secoes que o PDF/HTML podem renderizar por tipo de relatorio.
REPORT_LAYOUTS: dict[str, dict[str, Any]] = {
    "general": {
        "title_prefix": "Relatorio geral",
        "sections": [
            "overview",
            "team_summary",
            "metric_guide",
            "ai",
            "flow",
            "fibonacci",
            "collaborators",
            "developers",
            "reviewers",
            "formal_reviewers",
            "testers",
            "requesters",
            "projects",
            "sla",
            "bottlenecks",
            "trends",
            "quality_gates",
            "movements",
            "analysis_workflow",
            "antifraud",
            "dossier",
        ],
    },
    "individual": {
        "title_prefix": "Relatorio individual",
        "sections": ["overview", "metric_guide", "ai", "individual_summary", "dossier"],
    },
    "developers": {
        "title_prefix": "Relatorio de desenvolvedores",
        "sections": [
            "overview",
            "metric_guide",
            "ai",
            "role_summary",
            "flow",
            "fibonacci",
            "developers",
            "sla",
            "quality_gates",
            "dossier",
        ],
    },
    "requesters": {
        "title_prefix": "Relatorio de solicitantes",
        "sections": ["overview", "metric_guide", "ai", "role_summary", "requesters", "projects", "dossier"],
    },
    "testers": {
        "title_prefix": "Relatorio de testers",
        "sections": ["overview", "metric_guide", "ai", "role_summary", "testers", "quality_gates", "dossier"],
    },
    "reviewers": {
        "title_prefix": "Relatorio de revisao em par",
        "sections": ["overview", "metric_guide", "ai", "role_summary", "reviewers", "quality_gates", "dossier"],
    },
    "formal_reviewers": {
        "title_prefix": "Relatorio de revisores",
        "sections": [
            "overview",
            "metric_guide",
            "ai",
            "role_summary",
            "formal_reviewers",
            "quality_gates",
            "dossier",
        ],
    },
    "management": {
        "title_prefix": "Relatorio de gestao",
        "sections": [
            "overview",
            "team_summary",
            "metric_guide",
            "ai",
            "flow",
            "risk",
            "priority",
            "discipline",
            "projects",
            "sla",
            "bottlenecks",
            "trends",
            "quality_gates",
            "analysis_workflow",
            "antifraud",
        ],
    },
    "specific_metrics": {
        "title_prefix": "Relatorio de metricas especificas",
        "sections": ["overview", "metric_guide", "role_summary", "ai", "dynamic"],
    },
}


def report_layout(report_type: str | None) -> dict[str, Any]:
    return REPORT_LAYOUTS.get(report_type or "general", REPORT_LAYOUTS["general"])


def allows_section(report_type: str | None, section: str) -> bool:
    layout = report_layout(report_type)
    sections = layout.get("sections") or []
    if "dynamic" in sections:
        return section in sections or section not in _FIXED_SECTIONS
    return section in sections


_FIXED_SECTIONS = {
    "overview",
    "team_summary",
    "individual_summary",
    "role_summary",
    "metric_guide",
    "ai",
    "flow",
    "fibonacci",
    "collaborators",
    "developers",
    "reviewers",
    "formal_reviewers",
    "testers",
    "requesters",
    "projects",
    "sla",
    "bottlenecks",
    "trends",
    "quality_gates",
    "movements",
    "dossier",
    "risk",
    "priority",
    "discipline",
    "analysis_workflow",
    "antifraud",
}
