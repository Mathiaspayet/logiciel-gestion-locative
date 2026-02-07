# ============================================================
# Dockerfile - Gestion Locative (Production)
# ============================================================
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Version et date de build (injectées par le CI/CD)
ARG BUILD_VERSION=dev
ARG BUILD_DATE=unknown
ENV BUILD_VERSION=${BUILD_VERSION}
ENV BUILD_DATE=${BUILD_DATE}

# Dépendances système pour ReportLab (fonts)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        libffi-dev \
        fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

# Dépendances Python
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Code source
COPY gestion_locative/ /app/

# Créer les dossiers nécessaires
RUN mkdir -p /app/logs /app/staticfiles /app/data

# Collecter les fichiers statiques au build
RUN DJANGO_SECRET_KEY=build-placeholder \
    DJANGO_DEBUG=False \
    python manage.py collectstatic --noinput

# Script d'entrée
COPY docker-entrypoint.sh /app/
RUN chmod +x /app/docker-entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["/app/docker-entrypoint.sh"]
