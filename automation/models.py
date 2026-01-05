# automation/models.py
import uuid
from django.conf import settings
from django.db import models


def get_ai_provider_default():
    """
    Retorna el proveedor AI por defecto definido en settings/env.
    """
    raw = getattr(settings, "AI_PROVIDER_DEFAULT", "GEMINI") or "GEMINI"
    raw = str(raw).upper()
    return raw if raw in {"GEMINI", "OLLAMA"} else "GEMINI"


def get_ollama_default_model():
    """
    Modelo predeterminado para Ollama definido en settings/env.
    """
    return (getattr(settings, "OLLAMA_DEFAULT_MODEL", "") or "").strip()


class Agency(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.TextField()
    plan_level = models.TextField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField()

    class Meta:
        db_table = "agencies"
        managed = False  # MUY IMPORTANTE: Django no intenta crear/alterar esta tabla


class IGAccount(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    agency = models.ForeignKey(Agency, on_delete=models.CASCADE, db_column="agency_id")
    username = models.TextField()
    status = models.TextField(default="ACTIVE")
    session_id = models.TextField(null=True, blank=True)  # ajusta el nombre si en DB se llama distinto
    proxy_host = models.CharField(max_length=255, blank=True, default="")
    proxy_port = models.PositiveIntegerField(null=True, blank=True)
    proxy_user = models.CharField(max_length=255, blank=True, default="")
    proxy_password = models.CharField(max_length=255, blank=True, default="")
    created_at = models.DateTimeField()

    class Meta:
        db_table = "ig_accounts"
        managed = False
# automation/models.py (mismo archivo)
class InteractionCampaign(models.Model):
    ACTION_CHOICES = [("LIKE", "LIKE"), ("COMMENT", "COMMENT")]
    COMMENT_MODE_CHOICES = [("AI", "AI"), ("MANUAL", "MANUAL")]
    AI_PROVIDER_CHOICES = [("GEMINI", "GEMINI"), ("OLLAMA", "OLLAMA")]
    STATUS_CHOICES = [
        ("DRAFT", "DRAFT"), ("QUEUED", "QUEUED"), ("RUNNING", "RUNNING"),
        ("PAUSED", "PAUSED"), ("DONE", "DONE"), ("FAILED", "FAILED"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    agency = models.ForeignKey(Agency, on_delete=models.CASCADE, db_column="agency_id")
    name = models.CharField(max_length=200, default="Campaign")
    action = models.CharField(max_length=10, choices=ACTION_CHOICES)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="QUEUED")

    target_url = models.URLField()
    bot_count = models.PositiveIntegerField(default=1)
    post_urls = models.JSONField(default=list)  # ["https://instagram.com/p/.../", ...]
    comment_mode = models.CharField(
        max_length=10,
        choices=COMMENT_MODE_CHOICES,
        default="MANUAL",
        blank=True,
        null=False,
    )
    manual_comments = models.TextField(blank=True, default="")
    ai_provider = models.CharField(max_length=20, choices=AI_PROVIDER_CHOICES, default=get_ai_provider_default)
    ollama_model = models.CharField(max_length=100, blank=True, default=get_ollama_default_model)
    ai_persona = models.CharField(max_length=255, blank=True)
    ai_tone = models.CharField(max_length=100, blank=True)
    ai_user_prompt = models.TextField(blank=True)
    ai_use_image_context = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "interaction_campaigns"


class InteractionTask(models.Model):
    ACTION_CHOICES = [("LIKE", "LIKE"), ("COMMENT", "COMMENT")]
    STATUS_CHOICES = [
        ("PENDING", "PENDING"), ("IN_PROGRESS", "IN_PROGRESS"),
        ("SUCCESS", "SUCCESS"), ("ERROR", "ERROR"), ("RETRY", "RETRY"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    campaign = models.ForeignKey(InteractionCampaign, on_delete=models.CASCADE, db_column="campaign_id")
    agency = models.ForeignKey(Agency, on_delete=models.CASCADE, db_column="agency_id")
    ig_account = models.ForeignKey(IGAccount, on_delete=models.CASCADE, db_column="ig_account_id")

    action = models.CharField(max_length=10, choices=ACTION_CHOICES)
    post_url = models.TextField()
    comment_text = models.TextField(null=True, blank=True)

    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default="PENDING")
    attempts = models.IntegerField(default=0)
    next_retry_at = models.DateTimeField(null=True, blank=True)

    error_code = models.CharField(max_length=50, null=True, blank=True)
    result_message = models.TextField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "interaction_tasks"
        constraints = [
            models.UniqueConstraint(
                fields=["campaign", "ig_account", "action", "post_url"],
                name="uq_task_unique_action",
            )
        ]
        indexes = [
            models.Index(fields=["campaign"]),
            models.Index(fields=["status", "next_retry_at"]),
            models.Index(fields=["ig_account"]),
        ]
