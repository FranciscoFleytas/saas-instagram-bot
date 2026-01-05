# automation/ai_comments.py
import logging
import os
import random
from typing import Optional

import google.generativeai as genai
from django.conf import settings

from automation.ai_providers.ollama_client import ollama_generate
from automation.models import get_ai_provider_default, get_ollama_default_model

logger = logging.getLogger(__name__)

AI_PROVIDER_GEMINI = "GEMINI"
AI_PROVIDER_OLLAMA = "OLLAMA"
AI_PROVIDERS = {AI_PROVIDER_GEMINI, AI_PROVIDER_OLLAMA}


def _get_model() -> Optional[genai.GenerativeModel]:
    api_key = getattr(settings, "GEMINI_API_KEY", None) or os.getenv("GEMINI_API_KEY")
    if not api_key:
        logger.warning("GEMINI_API_KEY no configurada; usando comentario por defecto.")
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
1. Match the detected or implied language from any user instruction; otherwise default to English.
2. Avoid hashtags and emojis unless explicitly requested.
3. Keep tone human and specific, no generic praise.
4. ANGLE: {selected_angle}
""".strip()


def _normalize_provider(value: Optional[str]) -> str:
    chosen = (value or get_ai_provider_default() or AI_PROVIDER_GEMINI).upper()
    if chosen not in AI_PROVIDERS:
        return AI_PROVIDER_GEMINI
    return chosen


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
    Genera un comentario corto para Instagram usando Gemini u Ollama.
    """
    provider = _normalize_provider(ai_provider)
    prompt = _build_prompt(post_url, persona, tone, user_prompt, use_image_context)

    if provider == AI_PROVIDER_OLLAMA:
        try:
            model_name = ollama_model or get_ollama_default_model()
            return ollama_generate(prompt, model=model_name)
        except Exception as exc:
            logger.error("Fallo generando comentario con Ollama: %s", exc)
            return "Great post!"

    model = _get_model()
    if not model:
        return "Great post!"

    try:
        response = model.generate_content(prompt)
        return response.text.strip().replace('"', "").replace("Comment:", "")
    except Exception as exc:
        logger.error("Fallo generando comentario IA (Gemini): %s", exc)
        return "Great post!"
