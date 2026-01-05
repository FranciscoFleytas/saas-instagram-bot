from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from automation.ai_providers.ollama_client import FALLBACK_COMMENT, ollama_generate


class Command(BaseCommand):
    help = "Prueba la conectividad con Ollama generando un comentario corto."

    def handle(self, *args, **options):
        base = (getattr(settings, "OLLAMA_BASE_URL", "") or "").strip()
        key = (getattr(settings, "OLLAMA_API_KEY", "") or "").strip()
        if not base or not key:
            raise CommandError("Configura OLLAMA_BASE_URL y OLLAMA_API_KEY para probar la API remota de Ollama.")

        prompt = "Write a short, upbeat Instagram comment about a great photo."
        try:
            result = ollama_generate(prompt)
        except Exception as exc:
            raise CommandError(f"Ollama no está respondiendo: {exc}")

        snippet = (result or "").strip()[:200]
        if snippet == FALLBACK_COMMENT:
            raise CommandError("La llamada a Ollama devolvió el fallback; revisa el endpoint remoto y el modelo.")
        self.stdout.write(self.style.SUCCESS(f"OK via {base} -> {snippet}"))
