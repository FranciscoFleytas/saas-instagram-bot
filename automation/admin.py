import random
from django import forms
from django.conf import settings
from django.contrib import admin, messages
from django.db import transaction

from .models import (
    Agency,
    IGAccount,
    InteractionCampaign,
    InteractionTask,
    get_ai_provider_default,
    get_ollama_default_model,
)


# --------------------------
# Basic Admins
# --------------------------
@admin.register(Agency)
class AgencyAdmin(admin.ModelAdmin):
    list_display = ("name", "plan_level")


@admin.register(IGAccount)
class IGAccountAdmin(admin.ModelAdmin):
    list_display = ("username", "status", "agency", "has_proxy", "created_at")
    list_filter = ("status", "agency")
    search_fields = ("username",)

    fieldsets = (
        (None, {"fields": ("agency", "username", "status", "session_id")}),
        ("Proxy (opcional)", {"fields": ("proxy_host", "proxy_port", "proxy_user", "proxy_password")}),
    )

    def has_proxy(self, obj):
        return bool(obj.proxy_host and obj.proxy_port)

    has_proxy.boolean = True


# --------------------------
# Campaign Form (Checkbox UX)
# --------------------------
class InteractionCampaignForm(forms.ModelForm):
    """
    UX: checks (LIKE / COMMENT / FOLLOW)

    Reglas:
    - FOLLOW es exclusivo (no se mezcla con LIKE/COMMENT)
    - LIKE y COMMENT pueden combinarse => action = LIKE_COMMENT
    - Si no hay COMMENT, se limpian campos de comentario/AI
    - Si hay COMMENT y mode=AI, aplica validaciones existentes
    """

    do_like = forms.BooleanField(required=False, label="Like")
    do_comment = forms.BooleanField(required=False, label="Comment")
    do_follow = forms.BooleanField(required=False, label="Follow")

    class Meta:
        model = InteractionCampaign
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Inicializa checks desde instance.action (modo edición)
        current_action = (getattr(self.instance, "action", "") or "").upper()
        if current_action == "FOLLOW":
            self.fields["do_follow"].initial = True
        elif current_action == "LIKE":
            self.fields["do_like"].initial = True
        elif current_action == "COMMENT":
            self.fields["do_comment"].initial = True
        elif current_action == "LIKE_COMMENT":
            self.fields["do_like"].initial = True
            self.fields["do_comment"].initial = True

        # Requerimiento dinámico de ollama_model (igual que antes, pero solo si COMMENT activo)
        mode = (
            self.data.get("comment_mode")
            or self.initial.get("comment_mode")
            or getattr(self.instance, "comment_mode", "")
            or "MANUAL"
        ).upper()

        provider = (
            self.data.get("ai_provider")
            or self.initial.get("ai_provider")
            or getattr(self.instance, "ai_provider", "")
            or get_ai_provider_default()
            or "GEMINI"
        ).upper()
        provider = provider if provider in {"GEMINI", "OLLAMA"} else "GEMINI"

        # Si el usuario marcó COMMENT (o viene por instance) y mode=AI+OLLAMA => require model
        do_comment = self.data.get("do_comment")
        do_comment_bool = (str(do_comment).lower() in {"1", "true", "on", "yes"}) if do_comment is not None else self.fields["do_comment"].initial

        if do_comment_bool and mode == "AI" and provider == "OLLAMA":
            self.fields["ollama_model"].required = True
        else:
            self.fields["ollama_model"].required = False

    def clean_comment_mode(self):
        mode = (self.cleaned_data.get("comment_mode") or "MANUAL").upper()
        if mode not in {"AI", "MANUAL"}:
            mode = "MANUAL"
        return mode

    def clean_ai_provider(self):
        provider = (self.cleaned_data.get("ai_provider") or get_ai_provider_default() or "GEMINI").upper()
        if provider not in {"GEMINI", "OLLAMA"}:
            raise forms.ValidationError("ai_provider debe ser GEMINI u OLLAMA.")
        return provider

    def clean(self):
        cleaned = super().clean()

        do_like = bool(cleaned.get("do_like"))
        do_comment = bool(cleaned.get("do_comment"))
        do_follow = bool(cleaned.get("do_follow"))

        # 1) Validación de checks
        if not (do_like or do_comment or do_follow):
            raise forms.ValidationError("Debes seleccionar al menos una acción: Like, Comment o Follow.")

        if do_follow and (do_like or do_comment):
            raise forms.ValidationError("Follow no se puede combinar con Like/Comment. Selecciona solo Follow o solo Like/Comment.")

        # 2) Derivar action final
        if do_follow:
            cleaned["action"] = "FOLLOW"
        elif do_like and do_comment:
            cleaned["action"] = "LIKE_COMMENT"
        elif do_like:
            cleaned["action"] = "LIKE"
        else:
            cleaned["action"] = "COMMENT"

        # 3) Normalización AI/Comment fields
        action = cleaned["action"]
        comment_mode = (cleaned.get("comment_mode") or "MANUAL").upper()
        cleaned["comment_mode"] = comment_mode

        provider = (cleaned.get("ai_provider") or get_ai_provider_default() or "GEMINI").upper()
        cleaned["ai_provider"] = provider if provider in {"GEMINI", "OLLAMA"} else "GEMINI"

        # Si no hay COMMENT (FOLLOW o LIKE), limpiar todo lo de comments/AI
        if action in {"FOLLOW", "LIKE"}:
            cleaned["comment_mode"] = "MANUAL"
            cleaned["manual_comments"] = ""
            cleaned["ai_persona"] = ""
            cleaned["ai_tone"] = ""
            cleaned["ai_user_prompt"] = ""
            cleaned["ai_use_image_context"] = False
            cleaned["ollama_model"] = (cleaned.get("ollama_model") or "").strip()
            return cleaned

        # Si hay COMMENT (COMMENT o LIKE_COMMENT), aplicar tus validaciones previas
        # COMMENT/MANUAL requiere manual_comments
        if action in {"COMMENT", "LIKE_COMMENT"} and comment_mode == "MANUAL":
            lines = (cleaned.get("manual_comments") or "").splitlines()
            manual_choices = [line.strip() for line in lines if line.strip()]
            if not manual_choices:
                raise forms.ValidationError("Debes ingresar al menos un comentario manual (una línea no vacía) para campañas con Comment/MANUAL.")

        # COMMENT/AI valida provider + configs
        if action in {"COMMENT", "LIKE_COMMENT"} and comment_mode == "AI":
            if provider not in {"GEMINI", "OLLAMA"}:
                raise forms.ValidationError("Selecciona un proveedor AI válido (GEMINI u OLLAMA).")

            if provider == "OLLAMA":
                base = (getattr(settings, "OLLAMA_BASE_URL", "") or "").strip()
                key = (getattr(settings, "OLLAMA_API_KEY", "") or "").strip()
                if not base or not key:
                    raise forms.ValidationError("Configura OLLAMA_BASE_URL y OLLAMA_API_KEY en tu .env para usar OLLAMA.")

                model = (cleaned.get("ollama_model") or get_ollama_default_model() or "").strip()
                if not model:
                    raise forms.ValidationError("Define un modelo para Ollama (OLLAMA_DEFAULT_MODEL o valor manual).")
                cleaned["ollama_model"] = model
        else:
            cleaned["ollama_model"] = (cleaned.get("ollama_model") or "").strip()

        return cleaned


# --------------------------
# Campaign Admin
# --------------------------
@admin.register(InteractionCampaign)
class InteractionCampaignAdmin(admin.ModelAdmin):
    form = InteractionCampaignForm

    list_display = ("name", "action", "status", "bot_count", "comment_mode", "ai_provider", "created_at")
    readonly_fields = ("created_at", "started_at", "finished_at")

    fieldsets = (
        (None, {"fields": ("agency", "name", "status")}),
        ("Acciones (selecciona 1 modo)", {"fields": ("do_like", "do_comment", "do_follow")}),
        (
            "Interacción Automática",
            {
                "fields": (
                    "target_url",
                    "bot_count",
                    "comment_mode",
                    "ai_provider",
                    "ollama_model",
                    "manual_comments",
                    "ai_persona",
                    "ai_tone",
                    "ai_user_prompt",
                    "ai_use_image_context",
                )
            },
        ),
        ("Meta", {"fields": ("created_at", "started_at", "finished_at")}),
    )

    def save_model(self, request, obj, form, change):
        """
        Guarda la campaña y sincroniza InteractionTasks según bot_count.
        - target_url: post url (LIKE/COMMENT/LIKE_COMMENT) o profile/@user (FOLLOW)
        """
        # action ya viene derivada por el form.clean()
        obj.action = (getattr(form, "cleaned_data", {}).get("action") or obj.action or "").upper()

        # Normalización de comment_mode/ai_provider (aunque ya vino limpio)
        obj.comment_mode = (obj.comment_mode or "MANUAL").upper()
        if obj.comment_mode not in {"AI", "MANUAL"}:
            obj.comment_mode = "MANUAL"

        ai_provider = (obj.ai_provider or get_ai_provider_default() or "GEMINI").upper()
        if ai_provider not in {"GEMINI", "OLLAMA"}:
            ai_provider = "GEMINI"
        obj.ai_provider = ai_provider

        # Si la campaña no tiene COMMENT, limpiar campos de comment/AI para evitar basura
        if obj.action in {"FOLLOW", "LIKE"}:
            obj.comment_mode = "MANUAL"
            obj.manual_comments = ""
            obj.ai_persona = ""
            obj.ai_tone = ""
            obj.ai_user_prompt = ""
            obj.ai_use_image_context = False

        # Ollama model sólo si aplica (COMMENT/AI/OLLAMA)
        if obj.action in {"COMMENT", "LIKE_COMMENT"} and obj.comment_mode == "AI" and obj.ai_provider == "OLLAMA":
            if not (obj.ollama_model or "").strip():
                obj.ollama_model = get_ollama_default_model()
            else:
                obj.ollama_model = (obj.ollama_model or "").strip()
        else:
            obj.ollama_model = (obj.ollama_model or "").strip()

        with transaction.atomic():
            if obj.post_urls is None:
                obj.post_urls = []

            # Mantener compatibilidad con tu esquema: guardas target_url en post_urls[0]
            if obj.target_url:
                obj.post_urls = [obj.target_url]
            elif obj.post_urls:
                obj.target_url = obj.post_urls[0]

            super().save_model(request, obj, form, change)
            self._sync_tasks(request, obj)

    # --------------------------
    # Helpers
    # --------------------------
    def _get_candidate_bots(self, campaign):
        qs = IGAccount.objects.filter(status__iexact="ACTIVE")
        if campaign.agency_id:
            qs = qs.filter(agency_id=campaign.agency_id)

        qs = qs.exclude(session_id__isnull=True).exclude(session_id__exact="")
        accounts = list(qs)
        random.shuffle(accounts)
        return accounts

    def _tasks_are_pending(self, tasks):
        pending_states = {"PENDING", "RETRY"}
        return all(t.status in pending_states for t in tasks)

    def _get_manual_comment_choices(self, campaign):
        if (campaign.comment_mode or "").upper() != "MANUAL":
            return []
        lines = (campaign.manual_comments or "").splitlines()
        return [line.strip() for line in lines if line.strip()]

    def _sync_tasks(self, request, campaign):
        """
        Crea/ajusta tasks:
        - post_url = campaign.target_url (para LIKE/COMMENT/LIKE_COMMENT) o perfil/@user (FOLLOW)
        - action = campaign.action (LIKE, COMMENT, LIKE_COMMENT, FOLLOW)
        """
        post_url = campaign.target_url or (campaign.post_urls[0] if campaign.post_urls else "")
        if not post_url:
            messages.error(request, "No se pudo crear tareas: falta target_url.")
            return

        mode = (campaign.comment_mode or "MANUAL").upper()

        existing_tasks = list(
            InteractionTask.objects.filter(campaign=campaign).select_related("ig_account")
        )

        candidates = self._get_candidate_bots(campaign)
        max_bots = len(candidates)

        if max_bots == 0:
            campaign.bot_count = 0
            campaign.save(update_fields=["bot_count"])
            messages.warning(request, "No hay IGAccounts ACTIVAS con session_id para asignar.")
            return

        desired = max(int(campaign.bot_count or 0), 0)

        # Clamp pool real
        if desired > max_bots:
            messages.warning(
                request,
                f"bot_count ({desired}) excede las cuentas disponibles ({max_bots}). Se ajustó automáticamente a {max_bots}."
            )
            desired = max_bots

        if campaign.bot_count != desired:
            campaign.bot_count = desired
            campaign.save(update_fields=["bot_count"])

        manual_choices = self._get_manual_comment_choices(campaign)

        # Si la campaña tiene COMMENT (COMMENT o LIKE_COMMENT) en MANUAL, requiere manual choices
        if campaign.action in {"COMMENT", "LIKE_COMMENT"} and mode == "MANUAL" and not manual_choices:
            messages.error(
                request,
                "No se pueden crear tareas con Comment/MANUAL sin comentarios manuales. Agrega al menos una línea.",
            )
            return

        def _pick_accounts(desired_count, exclude_ids=None):
            exclude_ids = exclude_ids or []
            available = [acc for acc in candidates if acc.id not in exclude_ids]
            if desired_count == 0:
                return []
            if len(available) < desired_count:
                messages.error(
                    request,
                    f"Se requieren {desired_count} bots, pero solo hay {len(available)} disponibles con session_id.",
                )
                return None
            return random.sample(available, desired_count) if len(available) > desired_count else available

        def _create_tasks(accounts):
            if accounts is None:
                return

            for acc in accounts:
                comment_text = ""

                # Solo setear comment_text si la campaña incluye COMMENT y es MANUAL
                if campaign.action in {"COMMENT", "LIKE_COMMENT"} and mode == "MANUAL" and manual_choices:
                    comment_text = random.choice(manual_choices)

                InteractionTask.objects.create(
                    agency=campaign.agency,
                    campaign=campaign,
                    ig_account=acc,
                    action=campaign.action,
                    post_url=post_url,
                    comment_text=comment_text,
                    status="PENDING",
                )

        if not existing_tasks:
            accounts = _pick_accounts(desired)
            _create_tasks(accounts)
            return

        current_count = len(existing_tasks)
        all_pending_or_retry = self._tasks_are_pending(existing_tasks)

        # Si están todas pendientes y el count coincide, solo refrescamos comment_text según modo
        if current_count == desired and all_pending_or_retry:
            if campaign.action in {"COMMENT", "LIKE_COMMENT"} and mode == "MANUAL" and manual_choices:
                for task in existing_tasks:
                    task.comment_text = random.choice(manual_choices)
                    task.save(update_fields=["comment_text"])
            else:
                # si no es comment manual, limpiar comment_text
                for task in existing_tasks:
                    if task.comment_text:
                        task.comment_text = ""
                        task.save(update_fields=["comment_text"])
            return

        # Si todas pendientes/retry, preferimos recrear para mantener consistencia
        if all_pending_or_retry:
            accounts = _pick_accounts(desired)
            if accounts is None:
                return
            InteractionTask.objects.filter(campaign=campaign).delete()
            _create_tasks(accounts)
            return

        # Si deseamos más tasks y las existentes ya corrieron, solo agregamos faltantes
        if desired > current_count:
            exclude_ids = [t.ig_account_id for t in existing_tasks]
            missing_accounts = _pick_accounts(desired - current_count, exclude_ids)
            _create_tasks(missing_accounts)
        # Si desired < current_count y no están todas pendientes, no tocamos existentes.


# --------------------------
# Task Admin
# --------------------------
@admin.register(InteractionTask)
class InteractionTaskAdmin(admin.ModelAdmin):
    list_display = ("campaign", "ig_account", "action", "status", "attempts")
