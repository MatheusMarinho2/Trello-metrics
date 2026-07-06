from __future__ import annotations

import json
from typing import Any, Protocol
from urllib.parse import urlencode
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from reports.dataclasses.report_config import AIProviderConfig
from reports.services.ai_models import default_model_for, resolve_model


class AIClient(Protocol):
    def generate(self, system_prompt: str, user_prompt: str) -> str:
        ...


class OpenAIResponsesClient:
    endpoint = "https://api.openai.com/v1/responses"

    def __init__(self, config: AIProviderConfig) -> None:
        self.config = config
        self.model = resolve_model("openai", config.model or default_model_for("openai"))

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        payload = {
            "model": self.model,
            "input": [
                {
                    "role": "system",
                    "content": [{"type": "input_text", "text": system_prompt}],
                },
                {
                    "role": "user",
                    "content": [{"type": "input_text", "text": user_prompt}],
                },
            ],
            "max_output_tokens": self.config.max_tokens,
        }
        data = _post_json(
            self.endpoint,
            payload,
            {
                "Authorization": f"Bearer {self.config.api_key}",
                "Content-Type": "application/json",
            },
        )
        return _extract_openai_text(data)


class GeminiGenerateContentClient:
    endpoint = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

    def __init__(self, config: AIProviderConfig) -> None:
        self.config = config
        self.model = resolve_model("gemini", config.model or default_model_for("gemini"))
        self.last_finish_reason: str | None = None

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        url = f"{self.endpoint.format(model=self.model)}?{urlencode({'key': self.config.api_key})}"
        payload = {
            "system_instruction": {"parts": [{"text": system_prompt}]},
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": user_prompt}],
                }
            ],
            "generationConfig": {
                "temperature": self.config.temperature,
                "maxOutputTokens": self.config.max_tokens,
            },
        }
        data = _post_json(url, payload, {"Content-Type": "application/json"})
        text, finish_reason = _extract_gemini_text(data)
        self.last_finish_reason = finish_reason
        return text


class ClaudeMessagesClient:
    endpoint = "https://api.anthropic.com/v1/messages"

    def __init__(self, config: AIProviderConfig) -> None:
        self.config = config
        self.model = resolve_model("claude", config.model or default_model_for("claude"))

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        payload = {
            "model": self.model,
            "max_tokens": self.config.max_tokens,
            "temperature": self.config.temperature,
            "system": system_prompt,
            "messages": [{"role": "user", "content": user_prompt}],
        }
        data = _post_json(
            self.endpoint,
            payload,
            {
                "x-api-key": self.config.api_key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            },
        )
        return _extract_claude_text(data)


def build_ai_client(config: AIProviderConfig) -> AIClient:
    if config.provider == "gemini":
        return GeminiGenerateContentClient(config)
    if config.provider == "claude":
        return ClaudeMessagesClient(config)
    return OpenAIResponsesClient(config)


def response_was_truncated(client: AIClient) -> bool:
    reason = getattr(client, "last_finish_reason", None)
    return reason in {"MAX_TOKENS", "length"}


def _post_json(url: str, payload: dict[str, Any], headers: dict[str, str]) -> dict[str, Any]:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = Request(url, data=body, headers=headers, method="POST")
    try:
        with urlopen(request, timeout=90) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            return json.loads(response.read().decode(charset))
    except HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        message = raw
        try:
            parsed = json.loads(raw)
            message = (
                parsed.get("error", {}).get("message")
                or parsed.get("message")
                or raw
            )
        except json.JSONDecodeError:
            pass
        raise RuntimeError(f"HTTP Error {exc.code}: {message}") from exc


def _extract_openai_text(data: dict[str, Any]) -> str:
    if data.get("output_text"):
        return str(data["output_text"]).strip()
    chunks: list[str] = []
    for item in data.get("output") or []:
        for content in item.get("content") or []:
            text = content.get("text")
            if text:
                chunks.append(str(text))
    return "\n".join(chunks).strip()


def _extract_gemini_text(data: dict[str, Any]) -> tuple[str, str | None]:
    chunks: list[str] = []
    finish_reason: str | None = None
    for candidate in data.get("candidates") or []:
        finish_reason = candidate.get("finishReason") or finish_reason
        content = candidate.get("content") or {}
        for part in content.get("parts") or []:
            text = part.get("text")
            if text:
                chunks.append(str(text))
    return "\n".join(chunks).strip(), finish_reason


def _extract_claude_text(data: dict[str, Any]) -> str:
    chunks: list[str] = []
    for block in data.get("content") or []:
        if block.get("type") == "text" and block.get("text"):
            chunks.append(str(block["text"]))
    return "\n".join(chunks).strip()
