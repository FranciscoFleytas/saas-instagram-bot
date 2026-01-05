import random
import time
import logging
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction, models
from django.utils import timezone

from automation.adapters.interaction_adapter import execute_task
# Importamos IGAccount para poder buscar reemplazos
from automation.models import InteractionTask, InteractionCampaign, IGAccount

logger = logging.getLogger(__name__)


BACKOFF_SCHEDULE = [
    timedelta(minutes=5),
    timedelta(minutes=30),
    timedelta(hours=2),
]


class Command(BaseCommand):
    help = "Procesa InteractionTasks pendientes usando el bot de interacción rápida."

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("[worker] Iniciando worker de InteractionTasks..."))
        while True:
            task = self._pick_and_mark_task()
            if not task:
                time.sleep(5)
                continue

            result = self._execute_single_task(task)
            self._finalize_task(task, result)
            self._update_campaign_status(task.campaign)

            sleep_seconds = random.uniform(3, 8)
            time.sleep(sleep_seconds)

    def _pick_and_mark_task(self):
        now = timezone.now()
        with transaction.atomic():
            task_qs = (
                InteractionTask.objects.select_related("campaign", "ig_account")
                .select_for_update()
                .filter(status__in=["PENDING", "RETRY"])
                .filter(models.Q(next_retry_at__isnull=True) | models.Q(next_retry_at__lte=now))
                .order_by("created_at")
            )
            task = task_qs.first()

            if not task:
                return None

            task.status = "IN_PROGRESS"
            task.started_at = now
            task.attempts = task.attempts + 1
            task.save(update_fields=["status", "started_at", "attempts"])

            campaign = task.campaign
            if campaign.status == "QUEUED":
                campaign.status = "RUNNING"
                if not campaign.started_at:
                    campaign.started_at = now
                campaign.save(update_fields=["status", "started_at"])

            return task

    def _execute_single_task(self, task):
        try:
            return execute_task(task)
        except Exception as exc:
            logger.error("Fallo crítico ejecutando task %s: %s", task.id, exc)
            return {"success": False, "error_code": "UNKNOWN", "message": str(exc)}

    def _finalize_task(self, task, result):
        now = timezone.now()
        success = result.get("success")
        error_code = result.get("error_code", "")
        message = result.get("message", "")

        # Detección robusta de error de sesión (cookie caducada o login fallido)
        is_session_error = (
            error_code == "SESSION_ERROR" 
            or "cookie" in str(message).lower() 
            or "session" in str(message).lower()
            or "login" in str(message).lower()
        )

        if success:
            task.status = "SUCCESS"
            task.finished_at = now
            task.next_retry_at = None
        else:
            if is_session_error:
                # 1. Marcar la tarea como ERROR definitivo (sin reintentos)
                task.status = "ERROR"
                task.finished_at = now
                task.next_retry_at = None

                # --- NUEVO: Actualizar el estado de la cuenta IGAccount ---
                # Esto hará que aparezca como "SESSION_EXPIRED" en el Admin
                try:
                    account = task.ig_account
                    # Solo actualizamos si no estaba ya marcada para evitar escrituras extra
                    if account.status != "SESSION_EXPIRED":
                        old_status = account.status
                        account.status = "SESSION_EXPIRED"
                        account.save(update_fields=["status"])
                        logger.warning(
                            f"Cuenta '{account.username}' marcada como SESSION_EXPIRED "
                            f"(antes: {old_status}). Motivo: {message}"
                        )
                except Exception as e:
                    logger.error(f"Error actualizando estado de cuenta {task.ig_account_id}: {e}")
                # -----------------------------------------------------------

                # 2. Buscar una cuenta de reemplazo para intentar la tarea de nuevo
                self._spawn_replacement_task(task)

            elif task.attempts < 3:
                # Fallo recuperable (red, timeout, etc.), reintentamos la misma cuenta
                task.status = "RETRY"
                delay_index = min(task.attempts - 1, len(BACKOFF_SCHEDULE) - 1)
                task.next_retry_at = now + BACKOFF_SCHEDULE[delay_index]
            else:
                # Se agotaron los intentos normales
                task.status = "ERROR"
                task.finished_at = now
                task.next_retry_at = None

        task.error_code = error_code
        task.result_message = message
        task.save(
            update_fields=[
                "status",
                "finished_at",
                "next_retry_at",
                "error_code",
                "result_message",
            ]
        )

    def _spawn_replacement_task(self, failed_task):
        """
        Busca una cuenta nueva (no usada en esta campaña) y crea una tarea
        para reemplazar a la que falló por problemas de sesión.
        """
        campaign = failed_task.campaign
        
        # Obtenemos IDs de cuentas ya usadas en esta campaña para excluirlas
        used_accounts_ids = InteractionTask.objects.filter(
            campaign=campaign
        ).values_list('ig_account_id', flat=True)

        # Buscamos una cuenta activa que tenga session_id y no se haya usado
        replacement_account = IGAccount.objects.filter(
            agency=campaign.agency,
            status="ACTIVE"
        ).exclude(
            session_id__isnull=True
        ).exclude(
            session_id=""
        ).exclude(
            id__in=used_accounts_ids
        ).order_by('?').first() # Selección aleatoria

        if replacement_account:
            logger.info(
                f"[REPLACEMENT] Sustituyendo cuenta fallida {failed_task.ig_account.username} "
                f"por {replacement_account.username} en campaña {campaign.id}"
            )
            InteractionTask.objects.create(
                campaign=campaign,
                agency=campaign.agency,
                ig_account=replacement_account,
                action=failed_task.action,
                post_url=failed_task.post_url,
                comment_text=failed_task.comment_text, # Copiamos el texto (o vacío si es AI)
                status="PENDING"
            )
        else:
            logger.warning(
                f"[REPLACEMENT] No hay más cuentas disponibles para reemplazar la tarea {failed_task.id}."
            )

    def _update_campaign_status(self, campaign: InteractionCampaign):
        """
        Marca la campaña como RUNNING/DONE/FAILED según el estado de sus tasks.
        """
        pending_states = ["PENDING", "IN_PROGRESS", "RETRY"]
        qs = campaign.interactiontask_set.all()
        if qs.filter(status__in=pending_states).exists():
            return

        success_exists = qs.filter(status="SUCCESS").exists()
        campaign.status = "DONE" if success_exists else "FAILED"
        campaign.finished_at = timezone.now()
        campaign.save(update_fields=["status", "finished_at"])