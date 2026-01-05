from django.db import migrations, models
from django.db.models import Q


def backfill_ai_provider(apps, schema_editor):
    Campaign = apps.get_model("automation", "InteractionCampaign")
    Campaign.objects.filter(
        Q(comment_mode__iexact="AI"),
        Q(ai_provider__isnull=True) | Q(ai_provider=""),
    ).update(ai_provider="GEMINI")


class Migration(migrations.Migration):

    dependencies = [
        ("automation", "0005_igaccount_proxy_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="interactioncampaign",
            name="ai_provider",
            field=models.CharField(choices=[("GEMINI", "GEMINI"), ("OLLAMA", "OLLAMA")], default="GEMINI", max_length=20),
        ),
        migrations.AddField(
            model_name="interactioncampaign",
            name="ollama_model",
            field=models.CharField(blank=True, default="", max_length=100),
        ),
        migrations.RunPython(backfill_ai_provider, migrations.RunPython.noop),
    ]
