#!/bin/sh
set -e

cd /app/backend
python manage.py migrate --noinput

gunicorn intgest_reports.wsgi:application \
    --bind 127.0.0.1:8000 \
    --workers "${GUNICORN_WORKERS:-2}" \
    --timeout "${GUNICORN_TIMEOUT:-300}" \
    --chdir /app/backend &

exec nginx -g 'daemon off;'
