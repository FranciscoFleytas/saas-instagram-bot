import random
import time
import logging
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction, models
from django.utils import timezone

# Importamos la CLASE del adaptador, no la funcion (lo dejamos por compatibilidad aunque el worker use execute_task)
from automation.adapters.interaction_adapter import InteractionAdapter  # noqa: F401
from automation.models import InteractionTask, InteractionCampaign, IGAccount

# Ejecutamos por función (como ya lo tienes)
from automation.adapters.interaction_adapter import execute_task

logger = logging.getLogger(__name__)

BACKOFF_SCHEDULE = [
    timedelta(minutes=5),
    timedelta(minutes=30),
    timedelta(hours=2),
]


class Command(BaseCommand):
    help = "Procesa InteractionTasks pendientes usando el bot de interaccion rapida."

    def handle(self, *args, **options):
        self.stdout.write("[worker] Iniciando worker de InteractionTasks...")
        while True:
            task = self._pick_and_mark_task()
            if not task:
                time.sleep(5)
                continue

            # (1) Log consistente desde el worker: START + OK/FAIL
            result = self._execute_single_task(task)

            # Mantiene tu lógica de finalize (incluye rotación, expirado, backoff, etc.)
            self._finalize_task(task, result)

            # (3) Cierre de campaña + resumen final
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

    def _task_context_str(self, task) -> str:
        """
        Construye un contexto estándar para logs:
        task_id, campaign_id, acción, target/post, cuenta.
        No rompe si faltan campos.
        """
        acc = getattr(task, "ig_account", None)
        acc_user = getattr(acc, "username", None) or "NO_ACCOUNT"

        action = getattr(task, "action", None) or getattr(task, "task_type", None) or "UNKNOWN"

        # Target: prioriza username objetivo si existe; si no, URL/post; si no, UNKNOWN
        target = (
            getattr(task, "target_username", None)
            or getattr(task, "target", None)
            or getattr(task, "post_url", None)
            or getattr(task, "target_url", None)
            or "UNKNOWN"
        )

        return f"task={task.id} campaign={getattr(task, 'campaign_id', None)} action={action} target={target} account=@{acc_user}"

    def _execute_single_task(self, task):
        """
        (1) Log consistente siempre:
        - START antes de ejecutar
        - OK/FAIL después de ejecutar, leyendo estado real desde BD (después de finalize también se registrará,
          pero aquí damos visibilidad inmediata del intento).
        """
        ctx = self._task_context_str(task)
        logger.info(f"[TASK] START {ctx} attempt={task.attempts}")

        try:
            result = execute_task(task)
        except Exception as exc:
            logger.exception(f"[TASK] EXCEPTION {ctx} err={exc}")
            return {"success": False, "error_code": "UNKNOWN", "message": str(exc)}

        # Log preliminar basado en el result devuelto por adapter (antes de _finalize_task)
        ok = bool(result.get("success"))
        if ok:
            logger.info(f"[TASK] RESULT_OK {ctx} msg={result.get('message', '')}")
        else:
            logger.warning(
                f"[TASK] RESULT_FAIL {ctx} code={result.get('error_code', '')} msg={result.get('message', '')}"
            )
        return result

    def _finalize_task(self, task, result):
        now = timezone.now()
        success = result.get("success")
        error_code = result.get("error_code", "")
        message = result.get("message", "")

        # Definimos errores que requieren rotacion inmediata (bloqueos, sesiones muertas)
        # Agregamos CHECKPOINT y CHALLENGE para rotar si la cuenta se bloquea al intentar seguir
        critical_errors = ["SESSION_ERROR", "CHECKPOINT", "CHALLENGE", "LOGIN_REQUIRED", "FEEDBACK_REQUIRED"]

        is_critical_error = (
            error_code in critical_errors
            or "cookie" in str(message).lower()
            or "session" in str(message).lower()
            or "login" in str(message).lower()
            or "challenge" in str(message).lower()
        )

        if success:
            task.status = "SUCCESS"
            task.finished_at = now
            task.next_retry_at = None
        else:
            # Escenario 1: Error Critico -> Rotacion inmediata
            if is_critical_error:
                task.status = "ERROR"
                task.finished_at = now
                task.next_retry_at = None
                task.result_message = f"Fallo critico: {message}"

                # Si es error de sesión/login, marcamos la cuenta como expirada y limpiamos session_id
                session_or_login_error = (
                    error_code in ["SESSION_ERROR", "LOGIN", "LOGIN_REQUIRED"]
                    or "session" in str(message).lower()
                    or "sessionid" in str(message).lower()
                    or "session_id" in str(message).lower()
                    or "login" in str(message).lower()
                    or "cookie" in str(message).lower()
                )

                if session_or_login_error:
                    try:
                        account = task.ig_account
                        if account:
                            account.status = "SESSION_EXPIRED"
                            account.session_id = None  # o "" si prefieres string vacío
                            # opcional si usas cookies en DB:
                            # account.cookies = {}
                            account.save(update_fields=["status", "session_id"])  # + ["cookies"] si lo activas
                            logger.warning(
                                f"[ACCOUNT] SESSION_EXPIRED account=@{account.username} task={task.id} campaign={task.campaign_id}"
                            )
                    except Exception as e:
                        logger.error(f"Error actualizando estado de cuenta: {e}")

                # Si es bloqueo (Checkpoint/Challenge), marcamos la cuenta para revision
                elif error_code in ["CHECKPOINT", "CHALLENGE", "FEEDBACK_REQUIRED"]:
                    try:
                        account = task.ig_account
                        if account:
                            account.status = "CHECKPOINT"
                            account.save(update_fields=["status"])
                            logger.warning(
                                f"[ACCOUNT] CHECKPOINT account=@{account.username} task={task.id} campaign={task.campaign_id}"
                            )
                    except Exception as e:
                        logger.error(f"Error actualizando estado de cuenta: {e}")

                # Intentamos con otra cuenta
                self._spawn_replacement_task(task)

            # Escenario 2: Error leve, reintentamos con la MISMA cuenta
            elif task.attempts < 3:
                task.status = "RETRY"
                delay_index = min(task.attempts - 1, len(BACKOFF_SCHEDULE) - 1)
                task.next_retry_at = now + BACKOFF_SCHEDULE[delay_index]

            # Escenario 3: Se agotaron los intentos con esta cuenta -> ROTACION
            else:
                task.status = "ERROR"
                task.finished_at = now
                task.next_retry_at = None
                task.result_message = f"Agotados intentos. Ultimo error: {message}"

                # Aqui esta la clave: si fallo 3 veces, asumimos que esta cuenta no puede
                # y pasamos la tarea a otra cuenta del pool.
                self._spawn_replacement_task(task)

        # Guardamos el estado final de la tarea actual
        task.error_code = error_code
        if not task.result_message:  # No sobrescribir si ya pusimos mensaje de fallo critico
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

        # (1) Log consistente FINAL basado en el estado ya persistido
        ctx = self._task_context_str(task)
        if task.status == "SUCCESS":
            logger.info(f"[TASK] OK {ctx} attempts={task.attempts} msg={task.result_message}")
        elif task.status == "RETRY":
            logger.warning(
                f"[TASK] RETRY {ctx} attempts={task.attempts} next_retry_at={task.next_retry_at} code={task.error_code} msg={task.result_message}"
            )
        else:
            logger.warning(
                f"[TASK] FAIL {ctx} attempts={task.attempts} code={task.error_code} msg={task.result_message}"
            )

    def _spawn_replacement_task(self, failed_task):
        """
        Busca una cuenta nueva (no usada en esta campaña para esta tarea) y crea una tarea
        de reemplazo. Funciona para Follow, Like, Comment, etc.
        """
        campaign = failed_task.campaign

        # Obtenemos IDs de cuentas que YA intentaron esta accion especifica en esta campaña
        # para no volver a elegirlas (evita bucles infinitos entre cuentas fallidas)
        used_accounts_ids = (
            InteractionTask.objects.filter(
                campaign=campaign,
                action=failed_task.action,
                post_url=failed_task.post_url,
            ).values_list("ig_account_id", flat=True)
        )

        # Buscamos una cuenta activa que no este en la lista de usadas
        replacement_account = (
            IGAccount.objects.filter(
                agency=campaign.agency,
                status="ACTIVE",
            )
            .exclude(session_id__isnull=True)
            .exclude(session_id="")
            .exclude(id__in=used_accounts_ids)
            .order_by("?")
            .first()
        )  # Seleccion aleatoria para distribuir carga

        if replacement_account:
            logger.info(
                f"[REPLACEMENT] Rotando tarea de {failed_task.ig_account.username} "
                f"a {replacement_account.username} (Action: {failed_task.action})"
            )
            InteractionTask.objects.create(
                campaign=campaign,
                agency=campaign.agency,
                ig_account=replacement_account,
                action=failed_task.action,
                post_url=failed_task.post_url,
                comment_text=failed_task.comment_text,
                status="PENDING",
            )
        else:
            logger.warning(f"[REPLACEMENT] No hay mas cuentas disponibles para reemplazar la tarea {failed_task.id}.")

    def _log_campaign_summary(self, campaign: InteractionCampaign):
        """
        (3) Resumen final por campaña: totales + cuentas utilizadas + breakdown por estado.
        """
        qs = campaign.interactiontask_set.select_related("ig_account").all()

        total = qs.count()
        ok = qs.filter(status="SUCCESS").count()
        err = qs.filter(status="ERROR").count()
        retry = qs.filter(status="RETRY").count()
        pending = qs.filter(status__in=["PENDING", "IN_PROGRESS"]).count()

        # Breakdown por cuenta
        per_account = {}
        for t in qs:
            acc = getattr(t, "ig_account", None)
            u = getattr(acc, "username", None) or "NO_ACCOUNT"
            per_account[u] = per_account.get(u, 0) + 1

        logger.info(
            f"[CAMPAIGN] SUMMARY campaign={campaign.id} status={campaign.status} "
            f"tasks_total={total} success={ok} error={err} retry={retry} pending_like={pending} "
            f"accounts_used={per_account}"
        )

    def _update_campaign_status(self, campaign: InteractionCampaign):
        """
        Cierra campaña cuando ya no haya tareas activas.
        Además, imprime resumen final al cerrar.
        """
        pending_states = ["PENDING", "IN_PROGRESS", "RETRY"]
        qs = campaign.interactiontask_set.all()
        if qs.filter(status__in=pending_states).exists():
            return

        # Manteniendo tu idea, pero con objetivo: si bot_count existe, exigimos llegar a ese número.
        target = getattr(campaign, "bot_count", None) or 1
        success_count = qs.filter(status="SUCCESS").count()

        campaign.status = "DONE" if success_count >= target else "FAILED"
        campaign.finished_at = timezone.now()
        campaign.save(update_fields=["status", "finished_at"])

        # (3) Resumen final por campaña
        self._log_campaign_summary(campaign)
