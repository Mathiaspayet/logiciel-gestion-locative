# Utiliser une image Python légère et récente
FROM python:3.11-slim

# Empêcher Python de créer des fichiers .pyc et activer les logs en direct
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Dossier de travail dans le conteneur
WORKDIR /app

# Installation des dépendances
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Copie du code source
COPY . /app/

# Lancement du serveur (accessible depuis l'extérieur du conteneur)
CMD ["python", "gestion_locative/manage.py", "runserver", "0.0.0.0:8000"]