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

# Créer les dossiers nécessaires (data/media est monté sur le volume persistant)
RUN mkdir -p /app/logs /app/staticfiles /app/data /app/data/media /app/data/cache

# Collecter les fichiers statiques au build
RUN DJANGO_SECRET_KEY=build-placeholder \
    DJANGO_DEBUG=False \
    python manage.py collectstatic --noinput

# Script d'entrée et sonde de santé
COPY docker-entrypoint.sh /app/
COPY healthcheck.py /app/
RUN chmod +x /app/docker-entrypoint.sh

EXPOSE 8000

# Sans healthcheck, un conteneur qui demarre mais ne repond plus reste "up" :
# Watchtower deploierait une image cassee sans que rien ne le signale.
HEALTHCHECK --interval=60s --timeout=10s --start-period=40s --retries=3 \
    CMD ["python", "/app/healthcheck.py"]

ENTRYPOINT ["/app/docker-entrypoint.sh"]
