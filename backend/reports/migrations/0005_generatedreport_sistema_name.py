from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("reports", "0004_workcalendar_overtime"),
    ]

    operations = [
        migrations.AddField(
            model_name="generatedreport",
            name="sistema_name",
            field=models.CharField(blank=True, max_length=160),
        ),
        migrations.AlterField(
            model_name="generatedreport",
            name="report_type",
            field=models.CharField(
                choices=[
                    ("general", "Geral"),
                    ("individual", "Individual"),
                    ("developers", "Desenvolvedores"),
                    ("requesters", "Solicitantes"),
                    ("testers", "Testers"),
                    ("reviewers", "Revisao em par"),
                    ("formal_reviewers", "Revisores"),
                    ("management", "Gestao"),
                    ("specific_metrics", "Metricas especificas"),
                    ("by_system", "Por sistema"),
                ],
                max_length=32,
            ),
        ),
    ]
