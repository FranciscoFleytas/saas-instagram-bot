from django.db import migrations, models

import automation.models


class Migration(migrations.Migration):

    dependencies = [
        ("automation", "0006_add_ai_provider_and_ollama_model"),
    ]

    operations = [
        migrations.AlterField(
            model_name="interactioncampaign",
            name="ai_provider",
            field=models.CharField(
                choices=[("GEMINI", "GEMINI"), ("OLLAMA", "OLLAMA")],
                default=automation.models.get_ai_provider_default,
                max_length=20,
            ),
        ),
        migrations.AlterField(
            model_name="interactioncampaign",
            name="ollama_model",
            field=models.CharField(
                blank=True,
                default=automation.models.get_ollama_default_model,
                max_length=100,
            ),
        ),
    ]
