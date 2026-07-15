from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from reports.services.ai_models import DEFAULT_MAX_OUTPUT_TOKENS


ReportType = Literal[
    "general",
    "individual",
    "developers",
    "requesters",
    "testers",
    "reviewers",
    "formal_reviewers",
    "management",
    "specific_metrics",
]

AIProvider = Literal["openai", "gemini", "claude"]


@dataclass(frozen=True)
class TrelloSourceConfig:
    board_id: str = ""
    api_key: str = ""
    token: str = ""
    use_live_api: bool = True
    source_json: dict[str, Any] | None = None


@dataclass(frozen=True)
class AIProviderConfig:
    enabled: bool = False
    provider: AIProvider = "openai"
    api_key: str = ""
    model: str = ""
    temperature: float = 0.2
    max_tokens: int = DEFAULT_MAX_OUTPUT_TOKENS

    @property
    def can_generate(self) -> bool:
        return self.enabled and bool(self.api_key.strip())


@dataclass(frozen=True)
class ReportGenerationConfig:
    report_type: ReportType
    month: str
    trello: TrelloSourceConfig
    ai: AIProviderConfig = field(default_factory=AIProviderConfig)
    history_months: int = 6
    timezone: str = "America/Sao_Paulo"
    include_templates: bool = False
    collaborator_name: str = ""
    metric_keys: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class AIAnalysisResult:
    status: str
    text: str = ""
    provider: str = ""
    model: str = ""
    error: str = ""
