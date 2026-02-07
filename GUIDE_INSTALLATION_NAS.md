# Guide d'installation - Synology DS218+

Guide pas à pas pour déployer l'application Gestion Locative sur un NAS Synology DS218+ avec mise à jour automatique depuis GitHub.

---

## Sommaire

1. [Prérequis](#1-prérequis)
2. [Préparer le NAS](#2-préparer-le-nas)
3. [Configurer GitHub](#3-configurer-github)
4. [Premier déploiement sur le NAS](#4-premier-déploiement-sur-le-nas)
5. [Configurer l'accès distant (Tailscale)](#5-configurer-laccès-distant-tailscale)
6. [Configurer le reverse proxy HTTPS](#6-configurer-le-reverse-proxy-https)
7. [Vérifier que tout fonctionne](#7-vérifier-que-tout-fonctionne)
8. [Workflow quotidien](#8-workflow-quotidien)
9. [Maintenance & Sauvegarde](#9-maintenance--sauvegarde)
10. [Dépannage](#10-dépannage)

---

## 1. Prérequis

### Sur ton PC
- [x] Un compte GitHub avec le repo `logiciel-gestion-locative`
- [x] Git installé sur ton PC

### Sur le NAS Synology DS218+
- [x] DSM 7.x installé et à jour
- [x] Accès administrateur au NAS
- [x] Le NAS est connecté à internet

---

## 2. Préparer le NAS

### 2.1 Installer Container Manager (Docker)

1. Ouvre **DSM** dans ton navigateur (ex: `http://192.168.1.XX:5000`)
2. Va dans **Centre de paquets**
3. Cherche **Container Manager** (anciennement "Docker")
4. Clique **Installer**
5. Attends la fin de l'installation

> **Note :** Sur DSM 7.2+, c'est "Container Manager". Sur DSM 7.0/7.1, ça s'appelle encore "Docker".

### 2.2 Activer SSH sur le NAS

1. Va dans **Panneau de configuration** → **Terminal & SNMP**
2. Coche **Activer le service SSH**
3. Port : laisse `22` (ou change-le si tu préfères)
4. Clique **Appliquer**

### 2.3 Se connecter en SSH au NAS

Depuis ton PC, ouvre un terminal :

```bash
# Remplace par l'IP de ton NAS
ssh admin@192.168.1.XX
```

> **Astuce :** Sur Windows, utilise PowerShell ou le Terminal Windows.
> Le mot de passe est celui de ton compte admin DSM.

### 2.4 Créer le dossier de l'application

```bash
# Créer le dossier sur le NAS
sudo mkdir -p /volume1/docker/gestion-locative/logs
```

---

## 3. Configurer GitHub

### 3.1 Vérifier que GitHub Actions a tourné

1. Va sur ton repo GitHub → onglet **Actions**
2. Tu devrais voir un workflow "Build & Deploy" en cours ou terminé
3. Attends qu'il soit vert (&#10003;)

> **C'est quoi ?** À chaque push sur `master`, GitHub construit automatiquement
> l'image Docker et la publie sur GitHub Container Registry (GHCR).

### 3.3 Rendre le package accessible

1. Va sur ton profil GitHub → **Packages**
2. Clique sur `logiciel-gestion-locative`
3. En bas à droite, dans **Danger zone**, change la visibilité en **Public**
   (ou configure un token d'accès, voir section 3.4)

### 3.4 (Optionnel) Si le package est privé

Si tu veux garder l'image Docker privée, il faut un token d'accès sur le NAS :

1. GitHub → **Settings** → **Developer settings** → **Personal access tokens** → **Tokens (classic)**
2. Clique **Generate new token**
3. Coche uniquement `read:packages`
4. Copie le token généré

Puis sur le NAS (en SSH) :

```bash
# Se connecter au registre GitHub depuis le NAS
sudo docker login ghcr.io -u TON_USERNAME_GITHUB
# Colle le token comme mot de passe quand demandé
```

> **Important :** Cette étape est nécessaire pour que Watchtower puisse aussi
> télécharger les nouvelles images. Le fichier `docker-compose.synology.yml` monte
> automatiquement `/root/.docker/config.json` dans le conteneur Watchtower.

---

## 4. Premier déploiement sur le NAS

### 4.1 Copier les fichiers de configuration

Depuis ton PC, copie les fichiers sur le NAS :

```bash
# Copier le docker-compose Synology
scp docker-compose.synology.yml admin@192.168.1.XX:/volume1/docker/gestion-locative/docker-compose.yml

# Copier le template d'environnement
scp .env.example admin@192.168.1.XX:/volume1/docker/gestion-locative/.env
```

### 4.2 Configurer le fichier .env

Connecte-toi en SSH au NAS et édite le `.env` :

```bash
ssh admin@192.168.1.XX
sudo vi /volume1/docker/gestion-locative/.env
```

> **Pas à l'aise avec `vi` ?** Utilise File Station dans DSM pour éditer le fichier,
> ou édite-le sur ton PC avant de le copier avec `scp`.

Modifie les valeurs suivantes :

```env
# OBLIGATOIRE : Générer une clé unique
# Sur ton PC, lance : python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
DJANGO_SECRET_KEY=colle-ta-cle-secrete-ici

# Mode production
DJANGO_DEBUG=False

# Chemin de la base de données SQLite (dans le volume persistant)
DJANGO_DB_PATH=/app/data/db.sqlite3

# Ton IP NAS + le nom Tailscale (on le configurera après)
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1,192.168.1.XX

# Origines CSRF autorisées (nécessaire derrière un reverse proxy)
# Adapter plus tard avec ton domaine / IP du NAS en HTTPS
DJANGO_CSRF_TRUSTED_ORIGINS=https://192.168.1.XX,https://gestion.local

# Workers Gunicorn (2 est bien pour le DS218+)
GUNICORN_WORKERS=2

# Ton compte admin initial
DJANGO_SUPERUSER_USERNAME=admin
DJANGO_SUPERUSER_EMAIL=ton@email.com
DJANGO_SUPERUSER_PASSWORD=ChoisisUnVraiMotDePasse!

# Remplacer par ton user/repo GitHub
GITHUB_REPOSITORY=mathiaspayet/logiciel-gestion-locative
```

### 4.3 Lancer l'application

Toujours en SSH sur le NAS :

```bash
cd /volume1/docker/gestion-locative

# Télécharger les images et lancer
sudo docker compose up -d
```

Tu devrais voir :

```
Creating gestion_locative ... done
Creating watchtower       ... done
```

### 4.4 Vérifier que ça tourne

```bash
# Vérifier les conteneurs
sudo docker ps

# Tu devrais voir 2 conteneurs : gestion_locative et watchtower

# Voir les logs de l'application
sudo docker logs gestion_locative
```

Les logs devraient afficher :

```
=== Gestion Locative - Démarrage ===
Application des migrations...
Operations to perform: ...
Lancement de Gunicorn...
```

### 4.5 Premier test

Ouvre ton navigateur sur ton PC (connecté au même réseau) :

```
http://192.168.1.XX:8000/admin/
```

Tu devrais voir la page de connexion Jazzmin. Connecte-toi avec le compte admin défini dans `.env`.

---

## 5. Configurer l'accès distant (Tailscale)

Tailscale crée un réseau privé (VPN) entre tes appareils. C'est la méthode la plus simple et sécurisée pour accéder au NAS depuis l'extérieur.

### 5.1 Créer un compte Tailscale

1. Va sur [tailscale.com](https://tailscale.com)
2. Crée un compte (gratuit pour usage personnel, jusqu'à 100 appareils)
3. Connecte-toi avec ton compte Google/Microsoft/GitHub

### 5.2 Installer Tailscale sur le NAS

1. Dans DSM → **Centre de paquets** → **Paramètres**
2. Onglet **Sources de paquets** → **Ajouter**
   - Nom : `Tailscale`
   - Emplacement : `https://pkgs.tailscale.com/stable/dsm`
3. Clique **OK**
4. Dans le Centre de paquets, cherche **Tailscale** → **Installer**
5. Ouvre Tailscale depuis le menu des applications DSM
6. Connecte-toi avec ton compte Tailscale

> Ton NAS reçoit une adresse Tailscale (ex: `100.x.y.z`) et un nom (ex: `synology-ds218.tail12345.ts.net`).

### 5.3 Installer Tailscale sur ton téléphone

1. Télécharge **Tailscale** depuis l'App Store (iOS) ou le Play Store (Android)
2. Connecte-toi avec le même compte

### 5.4 Installer Tailscale sur ton PC

1. Télécharge Tailscale depuis [tailscale.com/download](https://tailscale.com/download)
2. Installe et connecte-toi avec le même compte

### 5.5 Mettre à jour le .env

Ajoute l'adresse Tailscale du NAS aux hôtes autorisés :

```bash
ssh admin@192.168.1.XX
sudo vi /volume1/docker/gestion-locative/.env
```

Modifie la ligne `DJANGO_ALLOWED_HOSTS` :

```env
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1,192.168.1.XX,100.x.y.z,synology-ds218.tail12345.ts.net
```

Puis redémarre l'app :

```bash
cd /volume1/docker/gestion-locative
sudo docker compose restart gestion-locative
```

### 5.6 Tester l'accès distant

Depuis ton téléphone (en 4G/5G, PAS en WiFi) :

```
http://100.x.y.z:8000/admin/
```

ou

```
http://synology-ds218.tail12345.ts.net:8000/admin/
```

---

## 6. Configurer le reverse proxy HTTPS

Le reverse proxy Synology permet d'avoir HTTPS et un joli nom de domaine local.

### 6.1 Créer le reverse proxy

1. DSM → **Panneau de configuration** → **Portail de connexion** → **Avancé**
2. Clique **Proxy inversé** → **Créer**
3. Remplis :
   - **Nom** : `Gestion Locative`
   - **Source** :
     - Protocole : `HTTPS`
     - Nom d'hôte : `gestion.local` (ou ton nom Tailscale)
     - Port : `443`
   - **Destination** :
     - Protocole : `HTTP`
     - Nom d'hôte : `localhost`
     - Port : `8000`
4. Clique **OK**

### 6.2 (Optionnel) Certificat HTTPS avec Tailscale

Tailscale fournit des certificats HTTPS gratuits automatiquement :

1. DSM → **Panneau de configuration** → **Sécurité** → **Certificat**
2. Tu peux utiliser le certificat Tailscale auto-généré

Ou simplement utiliser `https://synology-ds218.tail12345.ts.net` qui est déjà HTTPS via Tailscale Funnel.

### 6.3 Mettre à jour le .env pour HTTPS

```env
# Ajouter les origines CSRF de confiance
DJANGO_CSRF_TRUSTED_ORIGINS=https://gestion.local,https://synology-ds218.tail12345.ts.net
```

Puis redémarrer :

```bash
cd /volume1/docker/gestion-locative
sudo docker compose restart gestion-locative
```

---

## 7. Vérifier que tout fonctionne

### Checklist finale

- [ ] `http://192.168.1.XX:8000/admin/` → page de connexion (réseau local)
- [ ] Connexion avec le compte admin → Dashboard visible
- [ ] Depuis le téléphone en 4G via Tailscale → page accessible
- [ ] Créer/modifier un bail → fonctionne
- [ ] Générer un PDF (quittance) → PDF téléchargé

---

## 8. Workflow quotidien

### Tu modifies le code sur ton PC

```bash
# 1. Modifier le code
# 2. Commit
git add .
git commit -m "Ma modification"

# 3. Push sur master
git push origin master
```

### Ce qui se passe automatiquement

```
git push
   ↓
GitHub Actions build l'image Docker (2-3 min)
   ↓
Image poussée sur GitHub Container Registry
   ↓
Watchtower sur le NAS détecte la nouvelle image (max 5 min)
   ↓
Watchtower redémarre le conteneur avec la nouvelle version
   ↓
L'app est à jour sur ton NAS !
```

**Délai total : ~5-8 minutes entre ton `git push` et la mise à jour sur le NAS.**

### Vérifier les mises à jour

```bash
# Voir les logs de Watchtower
ssh admin@192.168.1.XX
sudo docker logs watchtower --tail 20
```

---

## 9. Maintenance & Sauvegarde

### Sauvegarder la base de données

La base SQLite est dans le volume Docker `/app/data/`. Pour la sauvegarder :

```bash
# Depuis le NAS en SSH
sudo docker cp gestion_locative:/app/data/db.sqlite3 /volume1/homes/admin/backup_gestion_$(date +%Y%m%d).sqlite3
```

### Automatiser la sauvegarde

Dans DSM → **Panneau de configuration** → **Planificateur de tâches** :

1. Clique **Créer** → **Tâche déclenchée** → **Script défini par l'utilisateur**
2. **Planification** : tous les jours à 3h du matin
3. **Script** :

```bash
#!/bin/bash
BACKUP_DIR="/volume1/homes/admin/backups"
mkdir -p "$BACKUP_DIR"
docker cp gestion_locative:/app/data/db.sqlite3 "$BACKUP_DIR/gestion_$(date +%Y%m%d_%H%M).sqlite3"
# Garder seulement les 30 dernières sauvegardes
ls -t "$BACKUP_DIR"/gestion_*.sqlite3 | tail -n +31 | xargs rm -f 2>/dev/null
```

### Mettre à jour manuellement (si besoin)

```bash
ssh admin@192.168.1.XX
cd /volume1/docker/gestion-locative
sudo docker compose pull
sudo docker compose up -d
```

### Voir les logs de l'application

```bash
# Logs en temps réel
sudo docker logs -f gestion_locative

# Dernières 50 lignes
sudo docker logs --tail 50 gestion_locative
```

### Redémarrer l'application

```bash
cd /volume1/docker/gestion-locative
sudo docker compose restart gestion-locative
```

### Arrêter l'application

```bash
cd /volume1/docker/gestion-locative
sudo docker compose down
```

---

## 10. Dépannage

### "Cannot connect" depuis le navigateur

1. Vérifier que le conteneur tourne : `sudo docker ps`
2. Vérifier les logs : `sudo docker logs gestion_locative`
3. Vérifier que le port 8000 n'est pas bloqué par le pare-feu DSM :
   - **Panneau de configuration** → **Sécurité** → **Pare-feu** → autoriser le port 8000

### "CSRF verification failed" quand je me connecte

Ajouter l'URL dans `.env` :

```env
DJANGO_CSRF_TRUSTED_ORIGINS=https://ton-adresse-ici
```

Puis redémarrer : `sudo docker compose restart gestion-locative`

### Watchtower ne met pas à jour

```bash
# Vérifier les logs
sudo docker logs watchtower

# Forcer une vérification
sudo docker restart watchtower
```

Si les logs affichent une erreur d'authentification (401/403) lors du pull depuis GHCR :

1. Vérifie que tu es connecté au registre GHCR sur le NAS :

```bash
sudo docker login ghcr.io -u TON_USERNAME_GITHUB
# Colle ton Personal Access Token (avec le scope read:packages) comme mot de passe
```

2. Vérifie que le fichier de credentials existe :

```bash
sudo cat /root/.docker/config.json
# Tu devrais voir une entrée pour ghcr.io
```

3. Redémarre Watchtower pour qu'il utilise les nouvelles credentials :

```bash
cd /volume1/docker/gestion-locative
sudo docker compose -f docker-compose.yml down watchtower
sudo docker compose -f docker-compose.yml up -d watchtower
```

### L'image Docker n'est pas trouvée

```bash
# Vérifier l'accès au registre
sudo docker pull ghcr.io/mathiaspayet/logiciel-gestion-locative:latest

# Si erreur d'authentification, se reconnecter
sudo docker login ghcr.io -u TON_USERNAME_GITHUB
```

### Restaurer une sauvegarde

```bash
# Arrêter l'app
cd /volume1/docker/gestion-locative
sudo docker compose stop gestion-locative

# Restaurer la BDD
sudo docker cp /volume1/homes/admin/backups/gestion_20260206_0300.sqlite3 gestion_locative:/app/data/db.sqlite3

# Redémarrer
sudo docker compose start gestion-locative
```

---

## Schéma récapitulatif

```
┌─────────────────────────────────────────────────────────────┐
│                        TON PC                               │
│  Code → git push → GitHub                                   │
└────────────────────────────┬────────────────────────────────┘
                             │
                    ┌────────▼────────┐
                    │  GitHub Actions  │
                    │  Build Docker    │
                    │  Push sur GHCR   │
                    └────────┬────────┘
                             │
              ┌──────────────▼──────────────┐
              │     Synology DS218+         │
              │                             │
              │  ┌─────────────────────┐    │
              │  │   Watchtower        │    │
              │  │   (auto-update)     │    │
              │  └──────────┬──────────┘    │
              │             │ pull & restart │
              │  ┌──────────▼──────────┐    │
              │  │  Gestion Locative   │    │
              │  │  Django + Gunicorn  │    │
              │  │  Port 8000          │    │
              │  └─────────────────────┘    │
              │                             │
              │  ┌─────────────────────┐    │
              │  │  Tailscale VPN      │    │
              │  │  Accès distant      │    │
              │  └─────────────────────┘    │
              └─────────────────────────────┘
                        ▲           ▲
                        │           │
               ┌────────┘           └────────┐
               │                             │
        ┌──────┴──────┐              ┌───────┴─────┐
        │  Téléphone  │              │     PC      │
        │  (4G/WiFi)  │              │  (maison/   │
        │             │              │   bureau)   │
        └─────────────┘              └─────────────┘
```
