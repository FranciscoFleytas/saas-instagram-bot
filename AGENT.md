Proyecto: SaaS Instagram Bot - Resumen de características

- Tipo: Backend Django + Celery para automatización de interacciones en Instagram (scraping, outreach por DM, comentarios/engagement).
- Estructura principal: app `automation/` (modelos, vistas, tasks, templates), motores en `automation/engine/` (`engine_base.py`, `bot_scraper.py`, `bot_outreach.py`, `bot_comment.py`), configuración en `saas_core/`.
- Stack y dependencias observadas: Django, Django REST Framework, Celery, Redis (broker/result), Selenium (undetected_chromedriver), cryptography (Fernet). Falta `requirements.txt` para reproducibilidad.
- Modelos críticos: `Agency`, `Proxy`, `IGAccount` (contraseña encriptada), `Lead` (datos scrapeados). Archivo: automation/models.py
- Orquestación: Tareas Celery en `automation/tasks.py`:
	- `task_run_scraping`: ejecuta `ScraperBot`, guarda leads y agenda outreach (drip) si `enable_autodm` activado.
	- `task_run_outreach`: envía DM a un lead.
	- `task_run_comment`: realiza interacciones en posts (like, save, comment).
- Motores (Selenium): `BotEngine` gestiona driver, proxy por extensión, login por cookie/credenciales, utilidades (typing humano, dismiss popups). Los bots heredan y añaden lógica específica.

Riesgos y detalles técnicos importantes
- Secretos en código: `SECRET_KEY` fallback y credenciales DB hardcodeadas; `ENCRYPTION_KEY` embebida en `automation/models.py` — mover TODO a variables de entorno y `.env`.
- Inconsistencia de API entre `tasks.py` y `engine_base.py`: nombres de métodos (`start_driver`/`init_driver`, `login`/`login_if_needed`, `close`/`quit`) pueden provocar `AttributeError`.
- Configuración insegura para producción: `ALLOWED_HOSTS=['*']`, `CORS_ALLOW_ALL_ORIGINS = True`.
- Robustez del scraper: selectores frágiles y uso intensivo de `sleep`; manejo amplio de excepciones que puede ocultar fallos.
- Reproducibilidad: falta `requirements.txt`/`pyproject.toml` y documentación de versión de Chrome/driver.

Recomendaciones inmediatas (prioridad alta)
- Mover todas las claves y credenciales a variables de entorno y añadir `.env.example`.
- Unificar la API del `BotEngine` con lo que usan las tareas (o crear adaptadores simples).
- Añadir `requirements.txt` y documentar instalación de Chrome/driver; considerar `docker-compose` (Postgres + Redis + worker).
- Asegurar limpieza robusta de recursos (drivers, carpetas temporales) y agregar timeouts/retries.

Pasos siguientes sugeridos
- (Rápido) Añadir `.env.example` y `requirements.txt`.
- (Urgente) Corregir nombres de métodos entre `tasks.py` y `engine_base.py` para que las tareas funcionen.
- (Mediano) Añadir tests unitarios/mocks para Selenium y CI básico.

Contacto: mantener este archivo actualizado con cambios de arquitectura y decisiones de seguridad.
