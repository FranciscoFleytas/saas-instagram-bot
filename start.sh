#!/bin/bash
echo "Iniciando Protocolo SaaS..."

# 1. Iniciar Redis en segundo plano (si no está corriendo)
if ! pgrep -x "redis-server" > /dev/null
then
    echo "Levantando Redis..."
    redis-server --daemonize yes
fi

# 2. Activar entorno virtual
source venv/bin/activate

# 3. Matar workers viejos para limpiar
pkill -f "celery worker"

# 4. Iniciar Celery en segundo plano (logs a archivo para no ensuciar)
echo "Iniciando Enjambre de Bots (Celery)..."
nohup celery -A saas_core worker --loglevel=info > celery.log 2>&1 &

# 5. Iniciar Django (este se queda en primer plano)
echo "Iniciando Dashboard..."
python manage.py runserver