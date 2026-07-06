from __future__ import annotations

from copy import deepcopy
from typing import Any

from rest_framework import serializers

from reports.dataclasses.report_config import (
    AIProviderConfig,
    ReportGenerationConfig,
    TrelloSourceConfig,
)
from reports.models import Collaborator, GeneratedReport
from reports.services.ai_models import (
    DEFAULT_MAX_OUTPUT_TOKENS,
    MAX_OUTPUT_TOKENS_LIMIT,
    effective_max_output_tokens,
    resolve_model,
)
from reports.services.metrics_selection_service import MetricsSelectionService


REPORT_TYPE_CHOICES = (
    ("general", "Geral"),
    ("individual", "Individual"),
    ("developers", "Desenvolvedores"),
    ("requesters", "Solicitantes"),
    ("testers", "Testers"),
    ("management", "Gestao"),
    ("specific_metrics", "Metricas especificas"),
)

AI_PROVIDER_CHOICES = (
    ("openai", "GPT"),
    ("gemini", "Gemini"),
    ("claude", "Claude"),
)


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=120)
    password = serializers.CharField(max_length=240, trim_whitespace=False)


class TrelloSourceSerializer(serializers.Serializer):
    board_id = serializers.CharField(max_length=120, required=False, allow_blank=True)
    api_key = serializers.CharField(max_length=240, required=False, allow_blank=True)
    token = serializers.CharField(max_length=400, required=False, allow_blank=True)
    use_live_api = serializers.BooleanField(default=True)
    source_json = serializers.JSONField(required=False, allow_null=True)


class AIProviderSerializer(serializers.Serializer):
    enabled = serializers.BooleanField(default=False)
    provider = serializers.ChoiceField(choices=AI_PROVIDER_CHOICES, default="openai")
    api_key = serializers.CharField(max_length=400, required=False, allow_blank=True)
    model = serializers.CharField(max_length=120, required=False, allow_blank=True)
    temperature = serializers.FloatField(default=0.2, min_value=0, max_value=1)
    max_tokens = serializers.IntegerField(
        default=DEFAULT_MAX_OUTPUT_TOKENS,
        min_value=300,
        max_value=MAX_OUTPUT_TOKENS_LIMIT,
    )


class ReportGenerationSerializer(serializers.Serializer):
    report_type = serializers.ChoiceField(choices=REPORT_TYPE_CHOICES)
    month = serializers.RegexField(regex=r"^\d{4}-\d{2}$")
    history_months = serializers.IntegerField(default=6, min_value=1, max_value=24)
    timezone = serializers.CharField(default="America/Sao_Paulo", max_length=80)
    include_templates = serializers.BooleanField(default=False)
    collaborator_name = serializers.CharField(
        max_length=160,
        required=False,
        allow_blank=True,
    )
    metric_keys = serializers.ListField(
        child=serializers.CharField(max_length=80),
        required=False,
        allow_empty=True,
    )
    trello = TrelloSourceSerializer()
    ai = AIProviderSerializer(required=False)

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        trello = attrs.get("trello") or {}
        source_json = trello.get("source_json")
        use_live_api = trello.get("use_live_api", True)

        if not use_live_api and not source_json:
            raise serializers.ValidationError(
                {"trello": "Envie source_json ou habilite a busca pela API do Trello."}
            )
        if attrs["report_type"] == "individual" and not attrs.get("collaborator_name"):
            raise serializers.ValidationError(
                {"collaborator_name": "Informe o colaborador para o relatorio individual."}
            )
        if attrs["report_type"] == "specific_metrics" and not attrs.get("metric_keys"):
            raise serializers.ValidationError(
                {"metric_keys": "Selecione ao menos uma metrica especifica."}
            )
        return attrs

    def to_config(self) -> ReportGenerationConfig:
        data = self.validated_data
        trello_data = data["trello"]
        ai_data = data.get("ai") or {}
        ai_provider = ai_data.get("provider", "openai")
        return ReportGenerationConfig(
            report_type=data["report_type"],
            month=data["month"],
            history_months=data["history_months"],
            timezone=data["timezone"],
            include_templates=data["include_templates"],
            collaborator_name=data.get("collaborator_name", ""),
            metric_keys=data.get("metric_keys", []),
            trello=TrelloSourceConfig(
                board_id=trello_data.get("board_id", ""),
                api_key=trello_data.get("api_key", ""),
                token=trello_data.get("token", ""),
                use_live_api=trello_data.get("use_live_api", True),
                source_json=trello_data.get("source_json"),
            ),
            ai=AIProviderConfig(
                enabled=ai_data.get("enabled", False),
                provider=ai_provider,
                api_key=ai_data.get("api_key", ""),
                model=resolve_model(ai_provider, ai_data.get("model", "")),
                temperature=ai_data.get("temperature", 0.2),
                max_tokens=effective_max_output_tokens(
                    ai_provider,
                    resolve_model(ai_provider, ai_data.get("model", "")),
                    ai_data.get("max_tokens", DEFAULT_MAX_OUTPUT_TOKENS),
                ),
            ),
        )


class GeneratedReportListSerializer(serializers.ModelSerializer):
    summary = serializers.SerializerMethodField()
    snapshot = serializers.SerializerMethodField()

    class Meta:
        model = GeneratedReport
        fields = (
            "id",
            "title",
            "report_type",
            "month",
            "collaborator_name",
            "board_name",
            "ai_status",
            "ai_provider",
            "ai_model",
            "created_at",
            "summary",
            "snapshot",
        )

    def get_summary(self, obj: GeneratedReport) -> dict[str, Any]:
        payload = obj.filtered_metrics or {}
        team = payload.get("team_summary") or {}
        overview = payload.get("overview") or {}
        return {
            "cards_delivered": team.get("cards_delivered", 0),
            "quality_rate_pct": team.get("quality_rate_pct", 0),
            "cards_metricados": overview.get("total_cards_metricados", 0),
        }

    def get_snapshot(self, obj: GeneratedReport) -> dict[str, Any] | None:
        snapshot = obj.trello_snapshot
        if not snapshot:
            return None
        return {
            "id": str(snapshot.id),
            "cards_count": snapshot.cards_count,
            "movements_count": snapshot.movements_count,
            "source": snapshot.source,
        }


class GeneratedReportDetailSerializer(serializers.ModelSerializer):
    snapshot = serializers.SerializerMethodField()
    filtered_metrics = serializers.SerializerMethodField()

    class Meta:
        model = GeneratedReport
        fields = (
            "id",
            "title",
            "report_type",
            "month",
            "collaborator_name",
            "metric_keys",
            "board_id",
            "board_name",
            "board_url",
            "snapshot",
            "filtered_metrics",
            "ai_status",
            "ai_provider",
            "ai_model",
            "ai_analysis",
            "ai_error",
            "created_by",
            "created_at",
            "updated_at",
        )

    def get_snapshot(self, obj: GeneratedReport) -> dict[str, Any] | None:
        snapshot = obj.trello_snapshot
        if not snapshot:
            return None
        return {
            "id": str(snapshot.id),
            "source": snapshot.source,
            "cards_count": snapshot.cards_count,
            "movements_count": snapshot.movements_count,
            "custom_field_changes_count": snapshot.custom_field_changes_count,
            "created_at": snapshot.created_at.isoformat(),
        }

    def get_filtered_metrics(self, obj: GeneratedReport) -> dict[str, Any]:
        return MetricsSelectionService().with_card_metadata(
            deepcopy(obj.filtered_metrics or {}),
            obj.metrics or {},
        )


class CollaboratorSyncSerializer(serializers.Serializer):
    board_id = serializers.CharField(max_length=120, required=False, allow_blank=True)
    api_key = serializers.CharField(max_length=240, required=False, allow_blank=True)
    token = serializers.CharField(max_length=400, required=False, allow_blank=True)


class CollaboratorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Collaborator
        fields = (
            "id",
            "name",
            "aliases",
            "active",
            "source",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "source", "created_at", "updated_at")

    def create(self, validated_data: dict[str, Any]) -> Collaborator:
        validated_data.setdefault("source", "manual")
        return super().create(validated_data)
