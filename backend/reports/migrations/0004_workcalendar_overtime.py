# Generated manually for calendar models

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("reports", "0003_trellomovement_source_card"),
    ]

    operations = [
        migrations.CreateModel(
            name="WorkCalendarException",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("date", models.DateField(db_index=True)),
                (
                    "kind",
                    models.CharField(
                        choices=[
                            ("holiday", "Feriado / dia inteiro fora"),
                            ("schedule_override", "Meio periodo / expediente curto"),
                            ("exclude_window", "Exclusao de janela"),
                        ],
                        max_length=32,
                    ),
                ),
                ("start_time", models.TimeField(blank=True, null=True)),
                ("end_time", models.TimeField(blank=True, null=True)),
                (
                    "scope",
                    models.CharField(
                        choices=[("all", "Todos"), ("collaborators", "Colaboradores especificos")],
                        default="all",
                        max_length=24,
                    ),
                ),
                ("note", models.CharField(blank=True, max_length=240)),
                ("active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "collaborators",
                    models.ManyToManyField(
                        blank=True,
                        related_name="calendar_exceptions",
                        to="reports.collaborator",
                    ),
                ),
            ],
            options={"ordering": ("-date", "-id")},
        ),
        migrations.CreateModel(
            name="OvertimeEntry",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("date", models.DateField(db_index=True)),
                ("start_time", models.TimeField()),
                ("end_time", models.TimeField()),
                ("note", models.CharField(blank=True, max_length=240)),
                ("active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "collaborator",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="overtime_entries",
                        to="reports.collaborator",
                    ),
                ),
            ],
            options={"ordering": ("-date", "-id")},
        ),
    ]
