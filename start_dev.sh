#!/usr/bin/env bash
set -e

cd "$(dirname "$0")"

source venv/bin/activate
set -a
source .env
set +a

python manage.py migrate

# Levanta Django en background
python manage.py runserver 127.0.0.1:8000 &
DJANGO_PID=$!

# Levanta worker (elige UNO)
python manage.py run_worker &
WORKER_PID=$!

echo "Django PID: $DJANGO_PID"
echo "Worker PID: $WORKER_PID"
echo "Ctrl+C para parar ambos"

trap "kill $DJANGO_PID $WORKER_PID" INT TERM
wait
