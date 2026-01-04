import logging
import os
import random
from typing import Optional

import google.generativeai as genai
from django.conf import settings

logger = logging.getLogger(__name__)


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


def generate_ai_comment(post_url: str, persona: str = "", tone: str = "", user_prompt: str = "", use_image_context: bool = False) -> str:
    """
    Genera un comentario corto para Instagram usando Gemini.
    """
    model = _get_model()
    if not model:
        return "Great post!"

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

    prompt = f"""
    ROLE: Social Media Expert.
    TASK: Write a SHORT, natural Instagram comment (max 1 sentence).

    {persona_str}
    {tone_str}
    {user_instruction}

    INPUT CONTEXT:
    - {' | '.join(context_lines)}
    - CAPTION: \"Caption not available. Respond generically but relevant.\"

    GUIDELINES:
    1. Match the detected or implied language from any user instruction; otherwise default to English.
    2. Avoid hashtags and emojis unless explicitly requested.
    3. Keep tone human and specific, no generic praise.
    4. ANGLE: {selected_angle}
    """

    try:
        response = model.generate_content(prompt)
        return response.text.strip().replace('"', '').replace("Comment:", "")
    except Exception as exc:
        logger.error("Fallo generando comentario IA: %s", exc)
        return "Great post!"
