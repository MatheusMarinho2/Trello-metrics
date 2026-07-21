from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("reports", "0005_generatedreport_sistema_name"),
    ]

    operations = [
        migrations.CreateModel(
            name="ProjectSystem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=160, unique=True)),
                ("active", models.BooleanField(default=True)),
                ("source", models.CharField(default="manual", max_length=40)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "ordering": ("name",),
            },
        ),
    ]
