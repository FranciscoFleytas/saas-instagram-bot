# SaaS Automation API

## Backend
- Copia `.env.example` a `.env` y completa credenciales (incluye `AI_PROVIDER_DEFAULT`, `GEMINI_API_KEY`, `OLLAMA_BASE_URL` y `OLLAMA_API_KEY`).
- Ejecutar chequeos: `./venv/bin/python manage.py check`
- Migraciones: `./venv/bin/python manage.py migrate`
- Servidor de desarrollo: `./venv/bin/python manage.py runserver 127.0.0.1:8000`
- Worker de interacción: `./venv/bin/python manage.py run_worker`
- Probar API remota de Ollama (requiere `OLLAMA_BASE_URL` y `OLLAMA_API_KEY`): `./venv/bin/python manage.py test_ollama`

## API (JSON)
- Listar bots: `curl -s http://127.0.0.1:8000/api/bots/`
- Crear bot: `curl -s -X POST http://127.0.0.1:8000/api/bots/ -H "Content-Type: application/json" -d '{"username":"demo_bot","session_id":"<session_id>"}'`
- Crear campaña: `curl -s -X POST http://127.0.0.1:8000/api/campaigns/ -H "Content-Type: application/json" -d '{"action":"COMMENT","post_url":"https://instagram.com/p/.../","comment_text":"Nice!","ig_account_ids":["<bot_uuid>"]}'`
- Listar tareas (con filtro): `curl -s "http://127.0.0.1:8000/api/tasks/?campaign_id=<campaign_uuid>"`
