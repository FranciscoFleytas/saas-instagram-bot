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


@admin.register(Agency)
class AgencyAdmin(admin.ModelAdmin):
    list_display = ('name', 'plan_level')


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



class InteractionCampaignForm(forms.ModelForm):
    class Meta:
        model = InteractionCampaign
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
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
        ).upper()
        provider = provider if provider in {"GEMINI", "OLLAMA"} else "GEMINI"

        if mode == "AI" and provider == "OLLAMA":
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
        action = (cleaned.get("action") or "").upper()
        comment_mode = (cleaned.get("comment_mode") or "MANUAL").upper()
        cleaned["comment_mode"] = comment_mode

        provider = (cleaned.get("ai_provider") or get_ai_provider_default() or "GEMINI").upper()
        cleaned["ai_provider"] = provider

        if action == "COMMENT" and comment_mode == "AI":
            if provider not in {"GEMINI", "OLLAMA"}:
                raise forms.ValidationError("Selecciona un proveedor AI válido (GEMINI u OLLAMA).")
            if provider == "OLLAMA":
                base = (getattr(settings, "OLLAMA_BASE_URL", "") or "").strip()
                key = (getattr(settings, "OLLAMA_API_KEY", "") or "").strip()
                if not base or not key:
                    raise forms.ValidationError(
                        "Configura OLLAMA_BASE_URL y OLLAMA_API_KEY en tu .env para usar OLLAMA."
                    )
                model = (cleaned.get("ollama_model") or get_ollama_default_model() or "").strip()
                if not model:
                    raise forms.ValidationError("Define un modelo para Ollama (OLLAMA_DEFAULT_MODEL o valor manual).")
                cleaned["ollama_model"] = model
        else:
            cleaned["ollama_model"] = (cleaned.get("ollama_model") or "").strip()

        return cleaned


@admin.register(InteractionCampaign)
class InteractionCampaignAdmin(admin.ModelAdmin):
    form = InteractionCampaignForm
    list_display = ('name', 'action', 'status', 'bot_count', 'comment_mode', 'ai_provider', 'created_at')
    readonly_fields = ('created_at', 'started_at', 'finished_at')
    fieldsets = (
        (None, {
            'fields': ('agency', 'name', 'status', 'action')
        }),
        ('Interacción Automática', {
            'fields': (
                'target_url',
                'bot_count',
                'comment_mode',
                'ai_provider',
                'ollama_model',
                'manual_comments',
                'ai_persona',
                'ai_tone',
                'ai_user_prompt',
                'ai_use_image_context',
            )
        }),
        ('Meta', {
            'fields': ('created_at', 'started_at', 'finished_at')
        }),
    )

    def save_model(self, request, obj, form, change):
        """
        Guarda la campaña y sincroniza InteractionTasks según bot_count/comment_mode.
        """
        obj.comment_mode = (obj.comment_mode or "MANUAL").upper()
        if obj.comment_mode not in {"AI", "MANUAL"}:
            obj.comment_mode = "MANUAL"

        ai_provider = (obj.ai_provider or get_ai_provider_default() or "GEMINI").upper()
        if ai_provider not in {"GEMINI", "OLLAMA"}:
            ai_provider = "GEMINI"
        obj.ai_provider = ai_provider

        if ai_provider == "OLLAMA" and not (obj.ollama_model or "").strip():
            obj.ollama_model = get_ollama_default_model()
        else:
            obj.ollama_model = (obj.ollama_model or "").strip()

        is_comment_manual = (obj.action or "").upper() == "COMMENT" and obj.comment_mode == "MANUAL"
        if is_comment_manual:
            manual_choices = self._get_manual_comment_choices(obj)
            if not manual_choices:
                messages.error(
                    request,
                    "Debes ingresar al menos un comentario manual (una línea no vacía) para campañas COMMENT/MANUAL.",
                )
                return

        with transaction.atomic():
            if obj.post_urls is None:
                obj.post_urls = []
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
        qs = IGAccount.objects.filter(status__iexact='ACTIVE')
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
        post_url = campaign.target_url or (campaign.post_urls[0] if campaign.post_urls else "")
        if not post_url:
            messages.error(request, "No se pudo crear tareas: falta target_url.")
            return
        mode = (campaign.comment_mode or "MANUAL").upper()

        desired = max(campaign.bot_count or 0, 0)
        existing_tasks = list(InteractionTask.objects.filter(campaign=campaign).select_related("ig_account"))

        candidates = self._get_candidate_bots(campaign)
        max_bots = len(candidates)

        if max_bots == 0:
            campaign.bot_count = 0
            campaign.save(update_fields=["bot_count"])
            messages.warning(request, "No hay IGAccounts ACTIVAS con session_id para asignar.")
            return

        desired = max(int(campaign.bot_count or 0), 0)

        # Clamp al pool real
        if desired > max_bots:
            messages.warning(
                request,
                f"bot_count ({desired}) excede las cuentas disponibles ({max_bots}). Se ajustó automáticamente a {max_bots}."
            )
            desired = max_bots

        # Persistimos el clamp para que en admin quede coherente
        if campaign.bot_count != desired:
            campaign.bot_count = desired
            campaign.save(update_fields=["bot_count"])


        manual_choices = self._get_manual_comment_choices(campaign)
        if campaign.action == "COMMENT" and mode == "MANUAL" and not manual_choices:
            messages.error(
                request,
                "No se pueden crear tareas COMMENT/MANUAL sin comentarios manuales. Agrega al menos una línea.",
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
                if mode == "MANUAL" and manual_choices:
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

        if current_count == desired and all_pending_or_retry:
            if mode == "MANUAL" and manual_choices:
                for task in existing_tasks:
                    task.comment_text = random.choice(manual_choices)
                    task.save(update_fields=["comment_text"])
            elif mode == "AI":
                for task in existing_tasks:
                    if task.comment_text:
                        task.comment_text = ""
                        task.save(update_fields=["comment_text"])
            return

        if all_pending_or_retry:
            accounts = _pick_accounts(desired)
            if accounts is None:
                return
            InteractionTask.objects.filter(campaign=campaign).delete()
            _create_tasks(accounts)
            return

        if desired > current_count:
            exclude_ids = [t.ig_account_id for t in existing_tasks]
            missing_accounts = _pick_accounts(desired - current_count, exclude_ids)
            _create_tasks(missing_accounts)
        # Si desired < current_count y las tareas no están todas pendientes, preferimos no tocar las existentes.


@admin.register(InteractionTask)
class InteractionTaskAdmin(admin.ModelAdmin):
    list_display = ('campaign', 'ig_account', 'action', 'status', 'attempts')
