from __future__ import annotations

from typing import Any

from reports.services.ai_models import AI_PROVIDERS

REPORT_TYPES = [
    {"value": "general", "label": "Geral"},
    {"value": "individual", "label": "Individual"},
    {"value": "developers", "label": "Desenvolvedores"},
    {"value": "requesters", "label": "Solicitantes"},
    {"value": "testers", "label": "Testers"},
    {"value": "management", "label": "Gestao"},
    {"value": "specific_metrics", "label": "Metricas especificas"},
]

METRIC_OPTIONS = [
    {"value": "team_summary", "label": "Resumo do time"},
    {"value": "flow", "label": "Fluxo"},
    {"value": "priority", "label": "Prioridade"},
    {"value": "dora", "label": "DORA"},
    {"value": "fibonacci_points", "label": "Pontos Fibonacci"},
    {"value": "developers", "label": "Desenvolvedores"},
    {"value": "developer_profiles", "label": "Perfis de dev"},
    {"value": "reviewers", "label": "Revisores"},
    {"value": "testers", "label": "Testers"},
    {"value": "requesters", "label": "Solicitantes"},
    {"value": "projects", "label": "Projetos"},
    {"value": "bottlenecks", "label": "Gargalos"},
    {"value": "sla", "label": "SLA"},
    {"value": "quality_gates", "label": "Dupla revisao"},
    {"value": "process_discipline", "label": "Disciplina de processo"},
    {"value": "risk_board", "label": "Risco"},
    {"value": "card_dossier", "label": "Detalhamento de cards"},
    {"value": "collaborators", "label": "Colaboradores"},
    {"value": "trends_6m", "label": "Tendencia 6 meses"},
    {"value": "custom_fields", "label": "Campos personalizados"},
    {"value": "movements", "label": "Movimentos"},
]


def report_options() -> dict[str, list[dict[str, Any]]]:
    return {
        "report_types": REPORT_TYPES,
        "metric_options": METRIC_OPTIONS,
        "ai_providers": AI_PROVIDERS,
    }
