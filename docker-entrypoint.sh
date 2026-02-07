#!/bin/bash
set -e

echo "=== Gestion Locative - Démarrage ==="

# Appliquer les migrations
echo "Application des migrations..."
python manage.py migrate --noinput

# Créer le superuser si les variables sont définies
if [ -n "$DJANGO_SUPERUSER_USERNAME" ] && [ -n "$DJANGO_SUPERUSER_PASSWORD" ]; then
    python manage.py createsuperuser --noinput 2>/dev/null || true
fi

echo "Lancement de Gunicorn..."
exec gunicorn gestion_locative.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers "${GUNICORN_WORKERS:-2}" \
    --timeout 120 \
    --access-logfile - \
    --error-logfile -
