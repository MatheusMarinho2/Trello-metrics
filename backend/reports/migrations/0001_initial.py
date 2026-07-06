from __future__ import annotations

import uuid

from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies: list[tuple[str, str]] = []

    operations = [
        migrations.CreateModel(
            name="GeneratedReport",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("title", models.CharField(max_length=180)),
                (
                    "report_type",
                    models.CharField(
                        choices=[
                            ("general", "Geral"),
                            ("individual", "Individual"),
                            ("developers", "Desenvolvedores"),
                            ("requesters", "Solicitantes"),
                            ("testers", "Testers"),
                            ("management", "Gestao"),
                            ("specific_metrics", "Metricas especificas"),
                        ],
                        max_length=32,
                    ),
                ),
                ("month", models.CharField(max_length=7)),
                ("collaborator_name", models.CharField(blank=True, max_length=160)),
                ("metric_keys", models.JSONField(blank=True, default=list)),
                ("board_id", models.CharField(blank=True, max_length=80)),
                ("board_name", models.CharField(blank=True, max_length=180)),
                ("board_url", models.URLField(blank=True)),
                ("metrics", models.JSONField()),
                ("filtered_metrics", models.JSONField()),
                ("ai_provider", models.CharField(blank=True, max_length=32)),
                ("ai_model", models.CharField(blank=True, max_length=120)),
                ("ai_status", models.CharField(default="disabled", max_length=24)),
                ("ai_analysis", models.TextField(blank=True)),
                ("ai_error", models.TextField(blank=True)),
                ("created_by", models.CharField(blank=True, max_length=120)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ("-created_at",)},
        ),
    ]
