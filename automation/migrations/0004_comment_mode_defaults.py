from django.db import migrations, models


def set_comment_mode_defaults(apps, schema_editor):
    Campaign = apps.get_model("automation", "InteractionCampaign")
    Campaign.objects.filter(comment_mode__isnull=True).update(comment_mode="MANUAL")
    Campaign.objects.filter(manual_comments__isnull=True).update(manual_comments="")


class Migration(migrations.Migration):

    dependencies = [
        ("automation", "0003_alter_interactioncampaign_ai_persona_and_more"),
    ]

    operations = [
        migrations.RunPython(set_comment_mode_defaults, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="interactioncampaign",
            name="comment_mode",
            field=models.CharField(
                blank=True,
                choices=[("AI", "AI"), ("MANUAL", "MANUAL")],
                default="MANUAL",
                max_length=10,
            ),
        ),
        migrations.AlterField(
            model_name="interactioncampaign",
            name="manual_comments",
            field=models.TextField(blank=True, default=""),
        ),
    ]
