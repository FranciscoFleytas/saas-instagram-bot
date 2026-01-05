import logging
import os
from typing import Optional

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


def _get_env(name: str, default: Optional[str] = None) -> Optional[str]:
    return getattr(settings, name, None) or os.getenv(name) or default


def ollama_chat(prompt: str, model: Optional[str] = None, timeout: Optional[int] = None) -> str:
    """
    Llama a Ollama REMOTO vía API oficial (ollama.com):
      POST https://ollama.com/api/chat
    Auth:
      Authorization: Bearer <OLLAMA_API_KEY>

    Response esperado:
      {
        "message": {"role":"assistant","content":"..."},
        ...
      }
    """
    base_url = (_get_env("OLLAMA_BASE_URL", "https://ollama.com") or "https://ollama.com").strip().rstrip("/")
    api_key = (_get_env("OLLAMA_API_KEY") or "").strip()
    if not api_key:
        raise RuntimeError("OLLAMA_API_KEY no está configurada")

    used_model = (model or _get_env("OLLAMA_DEFAULT_MODEL") or "ministral-3:8b").strip()
    used_timeout = int(timeout or _get_env("OLLAMA_TIMEOUT", "60") or 60)

    url = f"{base_url}/api/chat"

    payload = {
        "model": used_model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    logger.info("ollama_chat request url=%s model=%s timeout=%s", url, used_model, used_timeout)

    resp = requests.post(url, json=payload, headers=headers, timeout=used_timeout)
    if resp.status_code >= 400:
        logger.error("Ollama API error status=%s body=%s", resp.status_code, resp.text[:500])
        resp.raise_for_status()

    data = resp.json() if resp.content else {}
    msg = (data.get("message") or {})
    content = (msg.get("content") or "").strip()

    if not content:
        # fallback: algunos servidores podrían devolver "response" u otra clave
        content = (data.get("response") or "").strip()

    return content
