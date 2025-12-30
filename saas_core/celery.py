import os
from celery import Celery

# Establecer el módulo de configuración de Django por defecto
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'saas_core.settings')

app = Celery('saas_core')

# Usar la configuración de settings.py que empiece con CELERY_
app.config_from_object('django.conf:settings', namespace='CELERY')

# Autodetectar tareas en la carpeta 'automation/tasks.py'
app.autodiscover_tasks()