from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("reports", "0002_collaborator_trelloboardsnapshot_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="trellomovementrecord",
            name="source_card_id",
            field=models.CharField(blank=True, max_length=80),
        ),
        migrations.AddField(
            model_name="trellomovementrecord",
            name="source_card_name",
            field=models.CharField(blank=True, max_length=300),
        ),
    ]
