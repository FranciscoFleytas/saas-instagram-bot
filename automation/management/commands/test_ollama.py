from django.core.management.base import BaseCommand, CommandError

from automation.ai_providers.ollama_client import ollama_chat


class Command(BaseCommand):
    help = "Prueba Ollama remoto vía API oficial (OLLAMA_BASE_URL + /api/chat)."

    def add_arguments(self, parser):
        parser.add_argument("--model", type=str, default=None, help="Modelo Ollama (ej: ministral-3:8b)")
        parser.add_argument("--prompt", type=str, default="Decí hola en español, 1 frase.", help="Prompt de prueba")

    def handle(self, *args, **options):
        model = options.get("model")
        prompt = options.get("prompt")

        try:
            text = ollama_chat(prompt, model=model)
        except Exception as exc:
            raise CommandError(f"Ollama no respondió correctamente: {exc}")

        if not text.strip():
            raise CommandError("Ollama devolvió vacío. Revisá OLLAMA_BASE_URL, OLLAMA_API_KEY y el modelo.")

        self.stdout.write(self.style.SUCCESS(f"Ollama OK  ({model or 'default'}): {text}"))
