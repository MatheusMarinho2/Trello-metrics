from __future__ import annotations

from typing import Any

AIProvider = str

DEFAULT_MAX_OUTPUT_TOKENS = 131_072
MAX_OUTPUT_TOKENS_LIMIT = 200_000

_MODEL_MAX_OUTPUT: dict[str, int] = {
    "gpt-4o-mini": 16_384,
    "gpt-4o": 16_384,
    "gpt-4.1-mini": 16_384,
    "gemini-2.5-flash": 65_536,
    "gemini-2.5-flash-lite": 65_536,
    "gemini-2.5-pro": 65_536,
    "gemini-3.5-flash": 65_536,
    "claude-sonnet-4-20250514": 64_000,
    "claude-3-5-sonnet-latest": 8_192,
    "claude-3-5-haiku-latest": 8_192,
}

_PROVIDER_MAX_OUTPUT: dict[str, int] = {
    "openai": 16_384,
    "gemini": 65_536,
    "claude": 64_000,
}

MODEL_ALIASES: dict[str, str] = {
    "gemini-1.5-flash": "gemini-2.5-flash",
    "gemini-1.5-flash-8b": "gemini-2.5-flash-lite",
    "gemini-1.5-pro": "gemini-2.5-pro",
    "gemini-2.0-flash": "gemini-2.5-flash",
    "gemini-2.0-flash-001": "gemini-2.5-flash",
    "gemini-2.0-flash-lite": "gemini-2.5-flash-lite",
    "gemini-2.0-flash-lite-001": "gemini-2.5-flash-lite",
    "gpt-5.4-mini": "gpt-4o-mini",
    "gpt-5.1": "gpt-4o",
    "gemini-3.5-flash-preview": "gemini-2.5-flash",
    "claude-sonnet-5": "claude-sonnet-4-20250514",
}

AI_PROVIDERS: list[dict[str, Any]] = [
    {
        "value": "openai",
        "label": "GPT",
        "default_model": "gpt-4o-mini",
        "models": [
            {"value": "gpt-4o-mini", "label": "GPT-4o Mini (padrao)"},
            {"value": "gpt-4o", "label": "GPT-4o"},
            {"value": "gpt-4.1-mini", "label": "GPT-4.1 Mini"},
        ],
    },
    {
        "value": "gemini",
        "label": "Gemini",
        "default_model": "gemini-2.5-flash",
        "models": [
            {"value": "gemini-2.5-flash", "label": "Gemini 2.5 Flash (padrao)"},
            {"value": "gemini-2.5-flash-lite", "label": "Gemini 2.5 Flash Lite"},
            {"value": "gemini-2.5-pro", "label": "Gemini 2.5 Pro"},
            {"value": "gemini-3.5-flash", "label": "Gemini 3.5 Flash"},
        ],
    },
    {
        "value": "claude",
        "label": "Claude",
        "default_model": "claude-sonnet-4-20250514",
        "models": [
            {"value": "claude-sonnet-4-20250514", "label": "Claude Sonnet 4 (padrao)"},
            {"value": "claude-3-5-sonnet-latest", "label": "Claude 3.5 Sonnet"},
            {"value": "claude-3-5-haiku-latest", "label": "Claude 3.5 Haiku"},
        ],
    },
]

_PROVIDER_DEFAULTS = {item["value"]: item["default_model"] for item in AI_PROVIDERS}
_PROVIDER_MODELS = {
    item["value"]: {model["value"] for model in item["models"]}
    for item in AI_PROVIDERS
}


def default_model_for(provider: AIProvider) -> str:
    return _PROVIDER_DEFAULTS.get(provider, "gpt-4o-mini")


def effective_max_output_tokens(
    provider: AIProvider,
    model: str,
    requested: int | None = None,
) -> int:
    cap = _MODEL_MAX_OUTPUT.get(model) or _PROVIDER_MAX_OUTPUT.get(provider, 65_536)
    if requested is None or requested <= 0:
        return cap
    return min(requested, cap)


def resolve_model(provider: AIProvider, model: str | None) -> str:
    normalized = (model or "").strip()
    if normalized in MODEL_ALIASES:
        normalized = MODEL_ALIASES[normalized]
    allowed = _PROVIDER_MODELS.get(provider, set())
    default = default_model_for(provider)
    if not normalized:
        return default
    if normalized in allowed:
        return normalized
    if normalized in MODEL_ALIASES and MODEL_ALIASES[normalized] in allowed:
        return MODEL_ALIASES[normalized]
    return default
