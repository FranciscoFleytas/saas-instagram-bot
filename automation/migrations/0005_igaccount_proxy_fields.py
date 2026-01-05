from django.db import migrations, models

SQL = """
ALTER TABLE ig_accounts
    ADD COLUMN IF NOT EXISTS proxy_host VARCHAR(255) DEFAULT '' NOT NULL,
    ADD COLUMN IF NOT EXISTS proxy_port INTEGER,
    ADD COLUMN IF NOT EXISTS proxy_user VARCHAR(255) DEFAULT '' NOT NULL,
    ADD COLUMN IF NOT EXISTS proxy_password VARCHAR(255) DEFAULT '' NOT NULL;
"""

SQL_REVERSE = """
ALTER TABLE ig_accounts
    DROP COLUMN IF EXISTS proxy_host,
    DROP COLUMN IF EXISTS proxy_port,
    DROP COLUMN IF EXISTS proxy_user,
    DROP COLUMN IF EXISTS proxy_password;
"""


class Migration(migrations.Migration):

    dependencies = [
        ("automation", "0004_comment_mode_defaults"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddField(
                    model_name="igaccount",
                    name="proxy_host",
                    field=models.CharField(blank=True, default="", max_length=255),
                ),
                migrations.AddField(
                    model_name="igaccount",
                    name="proxy_password",
                    field=models.CharField(blank=True, default="", max_length=255),
                ),
                migrations.AddField(
                    model_name="igaccount",
                    name="proxy_port",
                    field=models.PositiveIntegerField(blank=True, null=True),
                ),
                migrations.AddField(
                    model_name="igaccount",
                    name="proxy_user",
                    field=models.CharField(blank=True, default="", max_length=255),
                ),
            ],
            database_operations=[
                migrations.RunSQL(sql=SQL, reverse_sql=SQL_REVERSE),
            ],
        ),
    ]
