from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("automation", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="interactioncampaign",
            name="ai_persona",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
        migrations.AddField(
            model_name="interactioncampaign",
            name="ai_tone",
            field=models.CharField(blank=True, default="", max_length=100),
        ),
        migrations.AddField(
            model_name="interactioncampaign",
            name="ai_use_image_context",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="interactioncampaign",
            name="ai_user_prompt",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AddField(
            model_name="interactioncampaign",
            name="bot_count",
            field=models.PositiveIntegerField(default=1),
        ),
        migrations.AddField(
            model_name="interactioncampaign",
            name="manual_comments",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AddField(
            model_name="interactioncampaign",
            name="target_url",
            field=models.URLField(default="https://instagram.com/p/example/"),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name="interactioncampaign",
            name="comment_mode",
            field=models.CharField(
                blank=True,
                choices=[("AI", "AI"), ("MANUAL", "MANUAL")],
                default="MANUAL",
                max_length=10,
                null=True,
            ),
        ),
    ]
