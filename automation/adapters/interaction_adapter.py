import logging
from typing import Dict, Optional
from urllib.parse import urlparse

from automation.engine.bot_fast_interaction import FastInteractionBot
from automation.models import InteractionTask

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
    Limpia URLs de Instagram:
    - elimina parámetros (?img_index, utm, etc.)
    - asegura trailing slash
    """
    parsed = urlparse((url or "").strip())
    clean = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
    return clean if clean.endswith("/") else clean + "/"


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
        # --- Validar session_id ---
        session_id = (getattr(task.ig_account, "session_id", None) or "").strip()
        if not session_id:
            return {
                "success": False,
                "error_code": "LOGIN",
                "message": "Missing session_id on IGAccount. Paste session_id extracted from browser cookies.",
            }

        # Normalizar URL (FIX CRÍTICO)
        post_url = normalize_ig_url(task.post_url)

        # Inicializar bot
        bot = FastInteractionBot(task.ig_account, proxy_data=None)

        if not bot.login():
            return {
                "success": False,
                "error_code": "LOGIN",
                "message": "Login failed (invalid/expired session_id or checkpoint required).",
            }

        action = (task.action or "").upper()

        # --- Ejecutar acción ---
        if action == "LIKE":
            ok = bot.execute(
                post_url,
                do_like=True,
                do_comment=False
            )

        elif action == "COMMENT":
            comment_text = (task.comment_text or "").strip()
            if not comment_text:
                comment_text = "🔥 Nice post!"

            ok = bot.execute(
                post_url,
                do_like=False,
                do_comment=True,
                comment_text=comment_text
            )

        else:
            return {
                "success": False,
                "error_code": "UNKNOWN",
                "message": f"Unsupported action: {task.action}",
            }

        if ok:
            return {
                "success": True,
                "error_code": None,
                "message": "Task executed successfully",
            }

        return {
            "success": False,
            "error_code": "UNKNOWN",
            "message": "Bot execution returned failure",
        }

    except Exception as exc:
        logger.exception(
            "Error executing InteractionTask %s",
            getattr(task, "id", "?"),
        )
        return {
            "success": False,
            "error_code": _map_error_code(exc),
            "message": str(exc),
        }
