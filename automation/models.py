import uuid
from django.db import models
from django.conf import settings


def get_ai_provider_default():
    provider = (getattr(settings, "AI_PROVIDER_DEFAULT", "") or "GEMINI").upper()
    if provider not in {"GEMINI", "OLLAMA"}:
        provider = "GEMINI"
    return provider


def get_ollama_default_model():
    return (getattr(settings, "OLLAMA_DEFAULT_MODEL", "") or "ministral-3:8b").strip()


class Agency(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.TextField()
    plan_level = models.TextField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "agencies"
        managed = True


class IGAccount(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    agency = models.ForeignKey(
        Agency,
        on_delete=models.CASCADE,
        db_column="agency_id",
        null=True,
        blank=True
    )
    username = models.TextField()
    status = models.TextField(default="ACTIVE")
    session_id = models.TextField(null=True, blank=True)

    # Cookies completas opcionales (además de session_id)
    cookies = models.JSONField(default=dict, blank=True)

    proxy_host = models.CharField(max_length=255, blank=True, default="")
    proxy_port = models.PositiveIntegerField(null=True, blank=True)
    proxy_user = models.CharField(max_length=255, blank=True, default="")
    proxy_password = models.CharField(max_length=255, blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "ig_accounts"
        managed = True


# -----------------------------
# Acciones soportadas (Campaign/Task)
# -----------------------------
ACTION_LIKE = "LIKE"
ACTION_COMMENT = "COMMENT"
ACTION_FOLLOW = "FOLLOW"
ACTION_LIKE_COMMENT = "LIKE_COMMENT"

ACTION_CHOICES = [
    (ACTION_LIKE, "LIKE"),
    (ACTION_COMMENT, "COMMENT"),
    (ACTION_FOLLOW, "FOLLOW"),
    (ACTION_LIKE_COMMENT, "LIKE_COMMENT"),
]


class InteractionCampaign(models.Model):
    COMMENT_MODE_CHOICES = [("AI", "AI"), ("MANUAL", "MANUAL")]
    STATUS_CHOICES = [
        ("DRAFT", "DRAFT"),
        ("QUEUED", "QUEUED"),
        ("RUNNING", "RUNNING"),
        ("PAUSED", "PAUSED"),
        ("DONE", "DONE"),
        ("FAILED", "FAILED"),
    ]

    AI_PROVIDERS = [
        ("GEMINI", "Gemini"),
        ("OLLAMA", "Ollama"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    agency = models.ForeignKey(Agency, on_delete=models.CASCADE, db_column="agency_id")

    name = models.CharField(max_length=200, default="Campaign")

    # IMPORTANTE: max_length debe soportar "LIKE_COMMENT"
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)

    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="QUEUED")

    # Antes era URLField (solo URLs válidas). Para FOLLOW necesitas aceptar @username o URL.
    # Para LIKE/COMMENT/LIKE_COMMENT puede ser URL de post. Para FOLLOW: @user o URL de perfil.
    target_url = models.TextField()

    bot_count = models.PositiveIntegerField(default=1)

    # Se mantiene por compatibilidad con tu lógica actual en admin (guardas target_url en post_urls[0])
    post_urls = models.JSONField(default=list)

    comment_mode = models.CharField(
        max_length=10,
        choices=COMMENT_MODE_CHOICES,
        default="MANUAL",
        blank=True,
        null=False,
    )
    manual_comments = models.TextField(blank=True, default="")

    # Configuración de IA
    ai_persona = models.CharField(max_length=255, blank=True)
    ai_tone = models.CharField(max_length=100, blank=True)
    ai_user_prompt = models.TextField(blank=True)
    ai_use_image_context = models.BooleanField(default=False)

    # Proveedor IA (default consistente con settings)
    ai_provider = models.CharField(
        max_length=20,
        choices=AI_PROVIDERS,
        default=get_ai_provider_default,
    )
    ollama_model = models.CharField(max_length=100, default=get_ollama_default_model)

    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "interaction_campaigns"


class InteractionTask(models.Model):
    STATUS_CHOICES = [
        ("PENDING", "PENDING"),
        ("IN_PROGRESS", "IN_PROGRESS"),
        ("SUCCESS", "SUCCESS"),
        ("ERROR", "ERROR"),
        ("RETRY", "RETRY"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    campaign = models.ForeignKey(InteractionCampaign, on_delete=models.CASCADE, db_column="campaign_id")
    agency = models.ForeignKey(Agency, on_delete=models.CASCADE, db_column="agency_id")
    ig_account = models.ForeignKey(IGAccount, on_delete=models.CASCADE, db_column="ig_account_id")

    # IMPORTANTE: max_length debe soportar "LIKE_COMMENT"
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)

    # Para LIKE/COMMENT/LIKE_COMMENT: URL del post
    # Para FOLLOW: @username o URL de perfil (lo guardas aquí por compatibilidad)
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


class SystemLog(models.Model):
    level = models.CharField(max_length=20, default="INFO")
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "system_logs"
