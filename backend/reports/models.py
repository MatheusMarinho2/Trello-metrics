from __future__ import annotations

import uuid

from django.db import models


class TrelloBoardSnapshot(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    board_id = models.CharField(max_length=80, db_index=True)
    name = models.CharField(max_length=180, blank=True)
    url = models.URLField(blank=True)
    source = models.CharField(max_length=24, default="api")
    raw_payload = models.JSONField(default=dict)
    cards_count = models.PositiveIntegerField(default=0)
    movements_count = models.PositiveIntegerField(default=0)
    custom_field_changes_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return f"{self.name or self.board_id} ({self.created_at:%Y-%m-%d %H:%M})"


class TrelloListRecord(models.Model):
    snapshot = models.ForeignKey(
        TrelloBoardSnapshot,
        related_name="lists",
        on_delete=models.CASCADE,
    )
    trello_id = models.CharField(max_length=80, db_index=True)
    name = models.CharField(max_length=180)
    closed = models.BooleanField(default=False)
    pos = models.FloatField(null=True, blank=True)
    color = models.CharField(max_length=80, blank=True)

    class Meta:
        ordering = ("pos", "name")
        indexes = [models.Index(fields=("snapshot", "trello_id"))]


class TrelloCardRecord(models.Model):
    snapshot = models.ForeignKey(
        TrelloBoardSnapshot,
        related_name="cards",
        on_delete=models.CASCADE,
    )
    trello_id = models.CharField(max_length=80, db_index=True)
    name = models.CharField(max_length=300)
    current_list_id = models.CharField(max_length=80, blank=True)
    current_list_name = models.CharField(max_length=180, blank=True)
    closed = models.BooleanField(default=False)
    is_template = models.BooleanField(default=False)
    created_at_trello = models.DateTimeField(null=True, blank=True)
    date_closed = models.DateTimeField(null=True, blank=True)
    date_last_activity = models.DateTimeField(null=True, blank=True)
    url = models.URLField(blank=True)
    id_short = models.IntegerField(null=True, blank=True)
    labels = models.JSONField(default=list, blank=True)
    custom_fields = models.JSONField(default=dict, blank=True)
    description_data = models.JSONField(default=dict, blank=True)
    raw = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ("current_list_name", "name")
        indexes = [
            models.Index(fields=("snapshot", "trello_id")),
            models.Index(fields=("snapshot", "current_list_name")),
        ]


class TrelloMovementRecord(models.Model):
    snapshot = models.ForeignKey(
        TrelloBoardSnapshot,
        related_name="movements",
        on_delete=models.CASCADE,
    )
    card_id = models.CharField(max_length=80, db_index=True)
    card_name = models.CharField(max_length=300, blank=True)
    at = models.DateTimeField()
    event_type = models.CharField(max_length=40)
    from_list_id = models.CharField(max_length=80, blank=True)
    from_list_name = models.CharField(max_length=180, blank=True)
    to_list_id = models.CharField(max_length=80, blank=True)
    to_list_name = models.CharField(max_length=180, blank=True)
    actor_id = models.CharField(max_length=80, blank=True)
    actor_name = models.CharField(max_length=180, blank=True)
    action_id = models.CharField(max_length=80, blank=True)
    source_card_id = models.CharField(max_length=80, blank=True)
    source_card_name = models.CharField(max_length=300, blank=True)

    class Meta:
        ordering = ("at",)
        indexes = [
            models.Index(fields=("snapshot", "card_id")),
            models.Index(fields=("snapshot", "event_type")),
        ]


class TrelloCustomFieldChangeRecord(models.Model):
    snapshot = models.ForeignKey(
        TrelloBoardSnapshot,
        related_name="custom_field_changes",
        on_delete=models.CASCADE,
    )
    card_id = models.CharField(max_length=80, db_index=True)
    card_name = models.CharField(max_length=300, blank=True)
    field_name = models.CharField(max_length=180)
    at = models.DateTimeField()
    old_value = models.TextField(blank=True)
    new_value = models.TextField(blank=True)
    actor_id = models.CharField(max_length=80, blank=True)
    actor_name = models.CharField(max_length=180, blank=True)
    action_id = models.CharField(max_length=80, blank=True)

    class Meta:
        ordering = ("at",)
        indexes = [
            models.Index(fields=("snapshot", "card_id")),
            models.Index(fields=("snapshot", "field_name")),
        ]


class Collaborator(models.Model):
    name = models.CharField(max_length=160, unique=True)
    aliases = models.JSONField(default=list, blank=True)
    active = models.BooleanField(default=True)
    source = models.CharField(max_length=40, default="manual")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("name",)

    def __str__(self) -> str:
        return self.name


class GeneratedReport(models.Model):
    REPORT_TYPES = (
        ("general", "Geral"),
        ("individual", "Individual"),
        ("developers", "Desenvolvedores"),
        ("requesters", "Solicitantes"),
        ("testers", "Testers"),
        ("management", "Gestao"),
        ("specific_metrics", "Metricas especificas"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=180)
    report_type = models.CharField(max_length=32, choices=REPORT_TYPES)
    month = models.CharField(max_length=7)
    collaborator_name = models.CharField(max_length=160, blank=True)
    metric_keys = models.JSONField(default=list, blank=True)

    board_id = models.CharField(max_length=80, blank=True)
    board_name = models.CharField(max_length=180, blank=True)
    board_url = models.URLField(blank=True)
    trello_snapshot = models.ForeignKey(
        TrelloBoardSnapshot,
        null=True,
        blank=True,
        related_name="reports",
        on_delete=models.SET_NULL,
    )

    metrics = models.JSONField()
    filtered_metrics = models.JSONField()

    ai_provider = models.CharField(max_length=32, blank=True)
    ai_model = models.CharField(max_length=120, blank=True)
    ai_status = models.CharField(max_length=24, default="disabled")
    ai_analysis = models.TextField(blank=True)
    ai_error = models.TextField(blank=True)

    created_by = models.CharField(max_length=120, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return self.title
