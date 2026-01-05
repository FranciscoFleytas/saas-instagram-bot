import logging
import os
import random
from typing import Optional

from django.conf import settings

# Gemini (por ahora mantenemos tu lib actual, aunque te muestre warning)
import google.generativeai as genai

from automation.ai_providers.ollama_client import ollama_chat

logger = logging.getLogger(__name__)

AI_PROVIDER_GEMINI = "GEMINI"
AI_PROVIDER_OLLAMA = "OLLAMA"
AI_PROVIDERS = {AI_PROVIDER_GEMINI, AI_PROVIDER_OLLAMA}


def _env(name: str, default: Optional[str] = None) -> Optional[str]:
    return getattr(settings, name, None) or os.getenv(name) or default


def _normalize_provider(value: Optional[str]) -> str:
    chosen = (value or _env("AI_PROVIDER_DEFAULT", AI_PROVIDER_GEMINI) or AI_PROVIDER_GEMINI).upper().strip()
    return chosen if chosen in AI_PROVIDERS else AI_PROVIDER_GEMINI


def _get_gemini_model() -> Optional[genai.GenerativeModel]:
    api_key = _env("GEMINI_API_KEY")
    if not api_key:
        logger.warning("GEMINI_API_KEY no configurada; fallback a comentario por defecto.")
        return None

    try:
        genai.configure(api_key=api_key)
        return genai.GenerativeModel("gemini-2.5-flash")
    except Exception as exc:
        logger.error("No se pudo inicializar Gemini: %s", exc)
        return None


def _build_prompt(post_url: str, persona: str, tone: str, user_prompt: str, use_image_context: bool) -> str:
    angles = [
        "FOCUS: Compliment the visual aesthetic.",
        "FOCUS: Highlight the mood or feeling.",
        "FOCUS: Minimalist agreement with the main idea.",
        "FOCUS: Mention a subtle detail or keyword if obvious.",
    ]
    selected_angle = random.choice(angles)

    persona_str = f"IDENTITY: {persona}" if persona else "IDENTITY: Expert Social Media User."
    tone_str = f"TONE: {tone}." if tone else "TONE: Friendly and concise."
    user_instruction = f"IMPORTANT USER INSTRUCTION: {user_prompt}" if user_prompt else ""

    context_lines = [f"Post URL: {post_url}"]
    if use_image_context:
        context_lines.append("Image context: Not available; infer from typical Instagram post style.")

    return f"""
ROLE: Social Media Expert.
TASK: Write a SHORT, natural Instagram comment (max 1 sentence).

{persona_str}
{tone_str}
{user_instruction}

INPUT CONTEXT:
- {' | '.join(context_lines)}
- CAPTION: "Caption not available. Respond generically but relevant."

GUIDELINES:
1. Match the language requested in IMPORTANT USER INSTRUCTION; otherwise default to Spanish.
2. Avoid hashtags and avoid emojis unless explicitly requested.
3. Keep tone human and specific, not generic praise.
4. ANGLE: {selected_angle}

RETURN ONLY THE COMMENT TEXT.
""".strip()


def generate_ai_comment(
    post_url: str,
    persona: str = "",
    tone: str = "",
    user_prompt: str = "",
    use_image_context: bool = False,
    ai_provider: Optional[str] = None,
    ollama_model: Optional[str] = None,
) -> str:
    """
    Genera un comentario corto para Instagram usando Gemini u Ollama (REMOTO por API).
    """
    provider = _normalize_provider(ai_provider)
    prompt = _build_prompt(post_url, persona, tone, user_prompt, use_image_context)

    if provider == AI_PROVIDER_OLLAMA:
        try:
            text = ollama_chat(prompt, model=ollama_model)
            return (text or "").strip() or "Buen post."
        except Exception as exc:
            logger.error("Fallo generando comentario con Ollama remoto: %s", exc)
            return "Buen post."

    model = _get_gemini_model()
    if not model:
        return "Buen post."

    try:
        response = model.generate_content(prompt)
        text = (response.text or "").strip()
        # limpieza mínima
        return text.replace('"', "").replace("Comment:", "").strip() or "Buen post."
    except Exception as exc:
        logger.error("Fallo generando comentario con Gemini: %s", exc)
        return "Buen post."
