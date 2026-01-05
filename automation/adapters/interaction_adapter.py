import logging
from typing import Dict, Optional
from urllib.parse import urlparse

from automation.engine.bot_fast_interaction import FastInteractionBot
from automation.models import InteractionTask
from automation.ai_comments import generate_ai_comment

logger = logging.getLogger(__name__)


def _map_error_code(exc: Exception) -> str:
    """
    Heurística simple para clasificar errores comunes de Instagram/API.
    """
    msg = str(exc).lower()
    if any(keyword in msg for keyword in ["checkpoint", "challenge"]):
        return "CHECKPOINT"
    if any(keyword in msg for keyword in ["login", "auth", "session"]):
        return "LOGIN"
    if any(keyword in msg for keyword in ["rate", "throttle", "too many"]):
        return "RATE_LIMIT"
    return "UNKNOWN"


def normalize_ig_url(url: str) -> str:
    """
    Normaliza URLs de Instagram a formato https://www.instagram.com/p/{CODE}/
    limpiando parámetros y exceso de path.
    """
    raw = (url or "").strip()
    if not raw:
        return ""

    normalized_input = raw if raw.startswith("http") else f"https://{raw.lstrip('/')}"
    parsed = urlparse(normalized_input)

    netloc = parsed.netloc or "www.instagram.com"
    parts = [p for p in parsed.path.split("/") if p]

    resource = parts[0] if len(parts) >= 2 else "p"
    code = parts[1] if len(parts) >= 2 else (parts[0] if parts else "")
    path = f"/{resource}/{code}/" if code else (parsed.path if parsed.path.endswith("/") else f"{parsed.path}/")

    return f"https://{netloc}{path}"

def _get_proxy_data_from_account(ig_account) -> Optional[Dict[str, str]]:
    """
    Devuelve proxy_data compatible con FastInteractionBot si IGAccount tiene proxy configurado.
    Requiere campos en IGAccount:
      - proxy_host (str)
      - proxy_port (int)
      - proxy_user (str)
      - proxy_password (str)
    """
    host = (getattr(ig_account, "proxy_host", "") or "").strip()
    port = getattr(ig_account, "proxy_port", None)
    user = (getattr(ig_account, "proxy_user", "") or "").strip()
    password = (getattr(ig_account, "proxy_password", "") or "").strip()

    if not host or not port:
        return None

    return {
        "host": host,
        "port": str(port),
        "user": user,
        "password": password,
    }


def _proxy_label(proxy_data: Optional[Dict[str, str]]) -> str:
    if not proxy_data:
        return "none"
    return f"{proxy_data.get('host')}:{proxy_data.get('port')}"


def execute_task(task: InteractionTask) -> Dict[str, Optional[str]]:
    """
    Ejecuta una InteractionTask usando FastInteractionBot.

    Retorna:
    {
        "success": bool,
        "error_code": str | None,
        "message": str
    }
    """
    try:
        action = (task.action or "").upper()
        campaign = getattr(task, "campaign", None)
        post_url = normalize_ig_url(task.post_url)
        if post_url and post_url != task.post_url:
            task.post_url = post_url
            task.save(update_fields=["post_url"])

        def _log_result(status_label: str):
            logger.info(
                "interaction_task_completed task_id=%s account=%s action=%s url=%s status=%s attempts=%s",
                getattr(task, "id", "?"),
                getattr(getattr(task, "ig_account", None), "username", "?"),
                action,
                post_url,
                status_label,
                getattr(task, "attempts", "?"),
            )

        # --- Validar session_id ---
        session_id = (getattr(task.ig_account, "session_id", None) or "").strip()
        if not session_id:
            result = {
                "success": False,
                "error_code": "LOGIN",
                "message": "Missing session_id on IGAccount. Paste session_id extracted from browser cookies.",
            }
            _log_result("ERROR")
            return result

        # Inicializar bot
        proxy_data = _get_proxy_data_from_account(task.ig_account)
        logger.info(
            "interaction_task_proxy task_id=%s account=%s proxy=%s",
            getattr(task, "id", "?"),
            getattr(getattr(task, "ig_account", None), "username", "?"),
            _proxy_label(proxy_data),
        )

        bot = FastInteractionBot(task.ig_account, proxy_data=proxy_data)


        if not bot.login():
            result = {
                "success": False,
                "error_code": "LOGIN",
                "message": "Login failed (invalid/expired session_id or checkpoint required).",
            }
            _log_result("ERROR")
            return result

        mode = ""

        # --- Ejecutar acción ---
        if action == "LIKE":
            ok = bot.execute(
                post_url,
                do_like=True,
                do_comment=False
            )

        elif action == "COMMENT":
            comment_text = (task.comment_text or "").strip()

            mode = (getattr(campaign, "comment_mode", "") or "").upper() if campaign else ""

            if not comment_text:
                if mode == "AI":
                    generated = generate_ai_comment(
                        post_url=post_url,
                        persona=getattr(campaign, "ai_persona", ""),
                        tone=getattr(campaign, "ai_tone", ""),
                        user_prompt=getattr(campaign, "ai_user_prompt", ""),
                        use_image_context=getattr(campaign, "ai_use_image_context", False),
                        ai_provider=getattr(campaign, "ai_provider", None),
                        ollama_model=getattr(campaign, "ollama_model", None),
                    )
                    comment_text = generated or "Great post!"
                    task.comment_text = comment_text
                    task.result_message = f"AI generated comment for {post_url}: {comment_text}"
                    task.save(update_fields=["comment_text", "result_message"])
                else:
                    comment_text = "🔥 Nice post!"
                    warning = "Comentario manual faltante; se usó fallback seguro."
                    task.comment_text = comment_text
                    task.result_message = warning
                    task.save(update_fields=["comment_text", "result_message"])

            ok = bot.execute(
                post_url,
                do_like=False,
                do_comment=True,
                comment_text=comment_text
            )

        else:
            result = {
                "success": False,
                "error_code": "UNKNOWN",
                "message": f"Unsupported action: {task.action}",
            }
            _log_result("ERROR")
            return result

        if ok:
            success_message = "Task executed successfully"
            if action == "COMMENT":
                prefix = "AI comment executed" if mode == "AI" else "Comment executed"
                success_message = f"{prefix}: {comment_text}"
            result = {
                "success": True,
                "error_code": None,
                "message": success_message,
            }
        else:
            result = {
                "success": False,
                "error_code": "UNKNOWN",
                "message": "Bot execution returned failure",
            }

        _log_result("SUCCESS" if result["success"] else "ERROR")
        return result

    except Exception as exc:
        logger.exception(
            "Error executing InteractionTask %s account=%s action=%s url=%s attempts=%s",
            getattr(task, "id", "?"),
            getattr(getattr(task, "ig_account", None), "username", "?"),
            getattr(task, "action", "?"),
            getattr(task, "post_url", "?"),
            getattr(task, "attempts", "?"),
        )
        return {
            "success": False,
            "error_code": _map_error_code(exc),
            "message": str(exc),
        }
