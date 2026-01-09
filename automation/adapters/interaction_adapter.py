import logging
import os
from typing import Dict, Optional
from urllib.parse import urlparse

from automation.engine.bot_fast_interaction import FastInteractionBot
from automation.models import InteractionTask
from automation.ai_comments import generate_ai_comment

logger = logging.getLogger(__name__)

DEBUG_BOT = str(os.getenv("BOT_DEBUG", "")).strip().lower() in {"1", "true", "yes", "on"}


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
    OJO: esto es SOLO para POSTS (LIKE/COMMENT/LIKE_COMMENT), NO para perfiles.
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


def _extract_follow_username(raw_target: str) -> str:
    """
    Acepta:
      - "@username"
      - "username"
      - "https://www.instagram.com/username/"
      - "instagram.com/username"
      - Incluso casos rotos por el normalizador: "https://@username/"
    Devuelve: "username" (sin @)
    """
    raw = (raw_target or "").strip()
    if not raw:
        return ""

    # Caso simple @user o user
    if raw.startswith("@"):
        return raw.lstrip("@").strip()

    # Si no parece URL, tratamos como username directo (quitando / ? etc)
    if "://" not in raw and "instagram.com" not in raw:
        raw = raw.split("?")[0].strip().strip("/")
        # si vino tipo "username/xxxx", tomamos el primer segmento
        return (raw.split("/")[0] or "").lstrip("@").strip()

    # URL-like
    normalized_input = raw if raw.startswith("http") else f"https://{raw.lstrip('/')}"
    parsed = urlparse(normalized_input)

    # Caso roto: https://@username/
    if parsed.netloc and parsed.netloc.startswith("@"):
        return parsed.netloc.lstrip("@").strip()

    parts = [p for p in (parsed.path or "").split("/") if p]
    if not parts:
        return ""

    # URL perfil típica: /username/
    # Evitar rutas no-perfil (p, reels, stories, etc)
    first = parts[0].lstrip("@").strip()
    if first.lower() in {"p", "reel", "reels", "stories", "explore", "tv"}:
        # Si llega un post por error, no sirve como FOLLOW
        return ""

    return first


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

        # Para logs, vamos a usar un "subject" que sea post_url (posts) o @username (follow)
        raw_input = (task.post_url or "").strip()
        subject_for_logs = raw_input

        def _log_result(status_label: str):
            logger.info(
                "interaction_task_completed task_id=%s account=%s action=%s subject=%s status=%s attempts=%s",
                getattr(task, "id", "?"),
                getattr(getattr(task, "ig_account", None), "username", "?"),
                action,
                subject_for_logs,
                status_label,
                getattr(task, "attempts", "?"),
            )
            if DEBUG_BOT:
                print(
                    f"[DEBUG] task_completed id={getattr(task,'id','?')} "
                    f"acc={getattr(getattr(task,'ig_account',None),'username','?')} "
                    f"action={action} subject={subject_for_logs} status={status_label} attempts={getattr(task,'attempts','?')}"
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
        if DEBUG_BOT:
            print(
                f"[DEBUG] init_bot task_id={getattr(task,'id','?')} "
                f"account={getattr(getattr(task,'ig_account',None),'username','?')} proxy={_proxy_label(proxy_data)}"
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
        ok = False

        # --- Ejecutar acción ---
        if action in {"LIKE", "COMMENT", "LIKE_COMMENT"}:
            # Normalizamos SOLO para posts
            post_url = normalize_ig_url(raw_input)
            subject_for_logs = post_url or raw_input

            # Si cambió y es válido, guardamos (solo posts)
            if post_url and post_url != task.post_url:
                task.post_url = post_url
                task.save(update_fields=["post_url"])

            if action == "LIKE":
                ok = bot.execute(post_url, do_like=True, do_comment=False)

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
                        comment_text = " Nice post!"
                        warning = "Comentario manual faltante; se usó fallback seguro."
                        task.comment_text = comment_text
                        task.result_message = warning
                        task.save(update_fields=["comment_text", "result_message"])

                ok = bot.execute(post_url, do_like=False, do_comment=True, comment_text=comment_text)

            else:  # LIKE_COMMENT
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
                        comment_text = " Nice post!"
                        warning = "Comentario manual faltante; se usó fallback seguro."
                        task.comment_text = comment_text
                        task.result_message = warning
                        task.save(update_fields=["comment_text", "result_message"])

                ok = bot.execute(post_url, do_like=True, do_comment=True, comment_text=comment_text)

        elif action == "FOLLOW":
            # NO normalizar como post. Extraemos username.
            username = _extract_follow_username(raw_input)
            subject_for_logs = f"@{username}" if username else raw_input

            if not username:
                result = {
                    "success": False,
                    "error_code": "UNKNOWN",
                    "message": f"Invalid follow target: {raw_input}",
                }
                _log_result("ERROR")
                return result

            if DEBUG_BOT:
                print(
                    f"[DEBUG] follow_action task_id={getattr(task,'id','?')} "
                    f"account={getattr(getattr(task,'ig_account',None),'username','?')} target=@{username}"
                )

            ok = bot.follow_user(username, check_friendship=True)

        else:
            result = {
                "success": False,
                "error_code": "UNKNOWN",
                "message": f"Unsupported action: {task.action}",
            }
            _log_result("ERROR")
            return result

        # Resultado final
        if ok:
            success_message = "Task executed successfully"
            if action in {"COMMENT", "LIKE_COMMENT"}:
                # si fue AI, lo dejamos explícito
                prefix = "AI comment executed" if mode == "AI" else "Comment executed"
                success_message = prefix
            if action == "FOLLOW":
                success_message = f"Follow executed: {subject_for_logs}"

            result = {"success": True, "error_code": None, "message": success_message}
        else:
            result = {"success": False, "error_code": "UNKNOWN", "message": "Bot execution returned failure"}

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
        if DEBUG_BOT:
            print(f"[DEBUG][EXCEPTION] {exc}")
        return {"success": False, "error_code": _map_error_code(exc), "message": str(exc)}
