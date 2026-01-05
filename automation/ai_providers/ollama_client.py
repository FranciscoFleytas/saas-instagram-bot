# automation/ai_providers/ollama_client.py
import logging
import os
from typing import Optional

import requests
from django.conf import settings

logger = logging.getLogger(__name__)
FALLBACK_COMMENT = "Great post!"


def _get(name: str, default=None):
    return getattr(settings, name, None) or os.getenv(name) or default


def _base_url() -> str:
    return str(_get("OLLAMA_BASE_URL", "")).strip().rstrip("/")


def _api_key() -> Optional[str]:
    key = _get("OLLAMA_API_KEY", None)
    if not key:
        return None
    key = str(key).strip()
    return key or None


def _mode() -> str:
    # "openai" (recomendado) o "ollama"
    return str(_get("OLLAMA_API_MODE", "openai")).strip().lower()


def _default_model() -> str:
    return str(_get("OLLAMA_DEFAULT_MODEL", "")).strip()


def _timeout(default_timeout: int = 60) -> int:
    try:
        return int(_get("OLLAMA_TIMEOUT", default_timeout))
    except (TypeError, ValueError):
        return default_timeout


def ollama_generate(prompt: str, model: Optional[str] = None, timeout: int = 60) -> str:
    """
    Llamada remota a "Ollama vía API".
    Soporta 2 modos:
      - openai: POST {BASE}/v1/chat/completions
      - ollama: POST {BASE}/api/generate
    """
    base = _base_url()
    if not base:
        logger.warning("OLLAMA_BASE_URL no configurado; se devuelve comentario por defecto.")
        return FALLBACK_COMMENT

    key = _api_key()
    if not key:
        logger.warning("OLLAMA_API_KEY no configurado; se devuelve comentario por defecto.")
        return FALLBACK_COMMENT

    mode = _mode()
    mdl = (model or _default_model()).strip()
    if not mdl:
        logger.warning("OLLAMA_DEFAULT_MODEL no definido y no se proporcionó modelo; se devuelve comentario por defecto.")
        return FALLBACK_COMMENT

    headers = {"Content-Type": "application/json"}
    headers["Authorization"] = f"Bearer {key}"
    req_timeout = timeout or _timeout()

    try:
        if mode == "ollama":
            # Ollama native compatible
            url = f"{base}/api/generate"
            payload = {"model": mdl, "prompt": prompt, "stream": False}
            resp = requests.post(url, json=payload, headers=headers, timeout=req_timeout)
            if not resp.ok:
                logger.error("Ollama API error (native) status=%s body=%s", resp.status_code, resp.text[:500])
                return FALLBACK_COMMENT
            data = resp.json()
            # Ollama suele devolver {"response": "..."}
            return (data.get("response") or "").strip() or FALLBACK_COMMENT

        # Default: OpenAI-compatible
        url = f"{base}/v1/chat/completions"
        payload = {
            "model": mdl,
            "messages": [
                {"role": "system", "content": "You write short, natural Instagram comments."},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.7,
        }
        resp = requests.post(url, json=payload, headers=headers, timeout=req_timeout)
        if not resp.ok:
            logger.error("Ollama API error (openai) status=%s body=%s", resp.status_code, resp.text[:500])
            return FALLBACK_COMMENT
        data = resp.json()
        try:
            return (data["choices"][0]["message"]["content"] or "").strip() or FALLBACK_COMMENT
        except Exception:
            logger.error("Respuesta inesperada del endpoint OpenAI-compatible: %s", data)
            return FALLBACK_COMMENT

    except requests.RequestException as exc:
        logger.error("Fallo en la solicitud HTTP a Ollama: %s", exc)
        return FALLBACK_COMMENT
    except Exception as exc:
        logger.error("Error procesando respuesta de Ollama: %s", exc)
        return FALLBACK_COMMENT
