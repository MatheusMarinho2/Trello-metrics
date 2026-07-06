from __future__ import annotations

from typing import Any

from reports.clients.ai_client import build_ai_client, response_was_truncated
from reports.dataclasses.report_config import AIAnalysisResult, ReportGenerationConfig
from reports.services.ai_context_builder import (
    COLLABORATOR_BATCH_SIZE,
    build_ai_context,
    collaborator_names,
    context_for_collaborator_batch,
    to_json,
)
from reports.services.ai_prompts import (
    COLLABORATOR_REPORT_TYPES,
    SYSTEM_PROMPT,
    TWO_PART_REPORT_TYPES,
    build_collaborator_batch_prompt,
    build_management_user_prompt,
    build_user_prompt,
)


class AIAnalysisService:
    def generate(
        self,
        report_payload: dict[str, Any],
        config: ReportGenerationConfig,
        full_metrics: dict[str, Any] | None = None,
    ) -> AIAnalysisResult:
        if not config.ai.enabled:
            return AIAnalysisResult(status="disabled")
        if not config.ai.api_key.strip():
            return AIAnalysisResult(
                status="skipped",
                provider=config.ai.provider,
                model=config.ai.model,
                error="Informe a API key para habilitar a analise IA.",
            )

        client = build_ai_client(config.ai)
        model = config.ai.model or getattr(client, "model", "")
        context = build_ai_context(report_payload, full_metrics)
        names = collaborator_names(context)

        try:
            if (
                config.report_type in COLLABORATOR_REPORT_TYPES
                and len(names) > COLLABORATOR_BATCH_SIZE
            ):
                text = self._generate_with_collaborator_batches(
                    client=client,
                    context=context,
                    config=config,
                    names=names,
                )
            elif config.report_type in TWO_PART_REPORT_TYPES:
                if config.report_type == "management":
                    text = self._generate_management_two_part(
                        client=client,
                        context=context,
                        config=config,
                    )
                else:
                    include_collaborators = config.report_type != "individual"
                    text = self._generate_two_part(
                        client=client,
                        context=context,
                        config=config,
                        names=names,
                        include_collaborators_section=include_collaborators,
                    )
            else:
                text = client.generate(
                    system_prompt=SYSTEM_PROMPT,
                    user_prompt=build_user_prompt(
                        report_type=config.report_type,
                        month=config.month,
                        collaborator_name=config.collaborator_name,
                        metrics_json=to_json(context),
                        collaborators_total=len(names),
                    ),
                )
        except Exception as exc:
            return AIAnalysisResult(
                status="error",
                provider=config.ai.provider,
                model=model,
                error=str(exc),
            )

        cleaned = (text or "").strip()
        if not cleaned:
            return AIAnalysisResult(
                status="empty",
                provider=config.ai.provider,
                model=model,
                error="A IA retornou resposta vazia.",
            )

        return AIAnalysisResult(
            status="generated",
            text=cleaned,
            provider=config.ai.provider,
            model=model,
        )

    def _generate_two_part(
        self,
        *,
        client: Any,
        context: dict[str, Any],
        config: ReportGenerationConfig,
        names: list[str],
        include_collaborators_section: bool,
    ) -> str:
        metrics_json = to_json(context)
        part1 = client.generate(
            system_prompt=SYSTEM_PROMPT,
            user_prompt=build_user_prompt(
                report_type=config.report_type,
                month=config.month,
                collaborator_name=config.collaborator_name,
                metrics_json=metrics_json,
                collaborators_total=len(names),
                part="first",
            ),
        ).strip()

        part2 = client.generate(
            system_prompt=SYSTEM_PROMPT,
            user_prompt=build_user_prompt(
                report_type=config.report_type,
                month=config.month,
                collaborator_name=config.collaborator_name,
                metrics_json=metrics_json,
                include_collaborators_section=include_collaborators_section,
                collaborators_total=len(names),
                part="second",
                first_part_text=part1,
            ),
        ).strip()

        combined = f"{part1}\n\n{part2}".strip()
        if _looks_incomplete(combined) or response_was_truncated(client):
            continuation = client.generate(
                system_prompt=SYSTEM_PROMPT,
                user_prompt=build_user_prompt(
                    report_type=config.report_type,
                    month=config.month,
                    collaborator_name=config.collaborator_name,
                    metrics_json=metrics_json,
                    include_collaborators_section=include_collaborators_section,
                    collaborators_total=len(names),
                    part="second",
                    first_part_text=combined,
                ),
            ).strip()
            combined = f"{combined}\n\n{continuation}".strip()
        return combined

    def _generate_management_two_part(
        self,
        *,
        client: Any,
        context: dict[str, Any],
        config: ReportGenerationConfig,
    ) -> str:
        metrics_json = to_json(context)
        part1 = client.generate(
            system_prompt=SYSTEM_PROMPT,
            user_prompt=build_management_user_prompt(
                month=config.month,
                metrics_json=metrics_json,
                part="first",
            ),
        ).strip()
        part2 = client.generate(
            system_prompt=SYSTEM_PROMPT,
            user_prompt=build_management_user_prompt(
                month=config.month,
                metrics_json=metrics_json,
                part="second",
                first_part_text=part1,
            ),
        ).strip()
        combined = f"{part1}\n\n{part2}".strip()
        if _looks_incomplete(combined) or response_was_truncated(client):
            continuation = client.generate(
                system_prompt=SYSTEM_PROMPT,
                user_prompt=build_management_user_prompt(
                    month=config.month,
                    metrics_json=metrics_json,
                    part="second",
                    first_part_text=combined,
                ),
            ).strip()
            combined = f"{combined}\n\n{continuation}".strip()
        return combined

    def _generate_with_collaborator_batches(
        self,
        *,
        client: Any,
        context: dict[str, Any],
        config: ReportGenerationConfig,
        names: list[str],
    ) -> str:
        main_text = self._generate_two_part(
            client=client,
            context=context,
            config=config,
            names=names,
            include_collaborators_section=False,
        )

        batch_parts: list[str] = []
        batch_total = (len(names) + COLLABORATOR_BATCH_SIZE - 1) // COLLABORATOR_BATCH_SIZE
        for index in range(0, len(names), COLLABORATOR_BATCH_SIZE):
            batch_names = names[index : index + COLLABORATOR_BATCH_SIZE]
            batch_context = context_for_collaborator_batch(
                context,
                batch_names,
                batch_index=(index // COLLABORATOR_BATCH_SIZE) + 1,
                batch_total=batch_total,
            )
            batch_text = client.generate(
                system_prompt=SYSTEM_PROMPT,
                user_prompt=build_collaborator_batch_prompt(
                    report_type=config.report_type,
                    month=config.month,
                    metrics_json=to_json(batch_context),
                    batch_names=batch_names,
                    batch_index=(index // COLLABORATOR_BATCH_SIZE) + 1,
                    batch_total=batch_total,
                    collaborators_total=len(names),
                ),
            )
            batch_parts.append(batch_text.strip())

        collaborator_section = "## Colaboradores\n\n" + "\n\n".join(batch_parts)
        return f"{main_text.strip()}\n\n{collaborator_section}"


def _looks_incomplete(text: str) -> bool:
    normalized = text.lower()
    if "## conclusao para gestao" not in normalized:
        return True
    tail = text.strip()[-120:]
    if tail and tail[-1] not in ".!?":
        return True
    return False
