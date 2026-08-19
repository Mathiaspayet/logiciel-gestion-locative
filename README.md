# Logiciel de Gestion Locative

Une application professionnelle et complète pour gérer vos biens immobiliers, locataires, baux, quittances et régularisations de charges. Conforme aux exigences de la gestion locative française (IRL, régularisation de charges, TVA).

## 🚀 Installation Rapide

### En production (Synology NAS)

Voir `GUIDE_INSTALLATION_NAS.md` : l'image Docker est construite par GitHub Actions
et déployée automatiquement par Watchtower.

### En développement local

```bash
python3 -m venv venv
source venv/bin/activate          # Windows : venv\Scripts\activate
pip install -r requirements.txt

cd gestion_locative
DJANGO_DEBUG=True python manage.py migrate
DJANGO_DEBUG=True python manage.py createsuperuser
DJANGO_DEBUG=True python manage.py runserver
```

L'interface est alors accessible sur `http://127.0.0.1:8000/app/` (nouvelle interface)
ou `http://127.0.0.1:8000/admin/` (admin Django legacy).

En production, `DJANGO_SECRET_KEY` est **obligatoire** : l'application refuse de
démarrer sans, plutôt que de retomber sur une clé connue.

### Tests

```bash
cd gestion_locative
DJANGO_DEBUG=True python manage.py test core
```

## ✨ Fonctionnalités Principales

### 🏢 Gestion des Biens
*   **Immeubles & Locaux :** Créez vos appartements, parkings, bureaux, commerces.
*   **Propriétaires :** Gérez plusieurs propriétaires (SCI, Nom propre, Indivision).
*   **Baux :** Gestion des baux mensuels ou trimestriels, avec ou sans TVA.
*   **Occupants :** Locataires, co-locataires, garants avec rôles distincts.

### 📄 Documents PDF (Génération Automatique)
*   **Quittances de Loyer :** Génération mensuelle ou par lot (ex: toute l'année). Design professionnel avec en-têtes bailleur/locataire.
*   **Avis d'Échéance :** Appels de loyer avec date limite de paiement et récapitulatif des montants.
*   **Régularisation de Charges :** Calcul précis au prorata temporis avec **historique tarifaire** (supporte les changements de charges en cours d'année).
*   **Solde de Tout Compte :** Arrêté de compte en fin de bail avec calculs automatiques.
*   **Révision de Loyer (IRL/ILC) :** Assistant manuel avec calcul automatique et validation avant application.

### 💰 Gestion Financière
*   **Dépenses :** Saisie des factures (Taxe Foncière, Assurance, Travaux...) avec période de validité.
*   **Compteurs :** Relevés d'eau/électricité avec gestion des périodes de consommation et prorata.
*   **Clés de Répartition :** Répartition par tantièmes, surface, ou consommation réelle (compteurs).
*   **Régularisations :** Suivi des paiements (payé/non payé, date de paiement, notes).

### 🔄 Historique Tarifaire
*   **Traçabilité Complète :** Chaque changement de loyer, charges ou taxes est enregistré avec dates d'application.
*   **Audit Trail :** Qui, quand, pourquoi pour chaque modification tarifaire.
*   **Calculs Précis :** Les PDFs utilisent automatiquement le bon tarif pour chaque période (même en cas de changement en cours d'année).
*   **Révision IRL/ILC :** Assistant manuel qui calcule le nouveau loyer mais **exige une validation** avant application (aucune mise à jour automatique).

### 📈 Gestion de Patrimoine
*   **Dashboard Patrimoine :** Vue d'ensemble de votre patrimoine immobilier avec graphiques et indicateurs.
*   **Valorisation :** Suivi de la valeur de vos biens dans le temps.
*   **Rentabilité :** Calcul du rendement brut et du cashflow mensuel.
*   **Projection :** Évolution de votre patrimoine sur 10 ans.
*   **Assistant Crédit Immobilier :** Formulaire intelligent avec calculs automatiques pour créer vos crédits (3 modes selon les données connues).

## 📊 Architecture Technique

### Stack Technologique
*   **Backend :** Django 6.0 (Python 3.x)
*   **Base de données :** SQLite (production) / PostgreSQL compatible
*   **PDF :** ReportLab
*   **Interface custom :** Django Templates + HTMX + Tailwind CSS + Chart.js (accessible sur `/app/`)
*   **Admin legacy :** Django Admin avec Jazzmin (accessible sur `/admin/`)

### Modèles Principaux

**Gestion Locative :**
*   `Proprietaire` : Propriétaires des biens
*   `Immeuble` : Bâtiments (avec prix achat, régime fiscal)
*   `Local` : Appartements, commerces, parkings, bureaux
*   `Bail` : Contrats de location
*   `BailTarification` : **Historique des tarifs** (loyer, charges, taxes avec périodes d'application)
*   `Occupant` : Locataires et garants
*   `Ajustement` : Ajustements ponctuels de loyer
*   `Regularisation` : Régularisations de charges avec suivi de paiement

**Gestion des Charges :**
*   `CleRepartition` : Clés de répartition des charges
*   `QuotePart` : Tantièmes par local
*   `Depense` : Charges et dépenses
*   `Consommation` : Relevés de compteurs

**Gestion Patrimoniale :**
*   `EstimationValeur` : Historique des estimations de valeur des immeubles
*   `CreditImmobilier` : Crédits immobiliers (amortissable, in fine)
*   `EcheanceCredit` : Échéancier détaillé des crédits
*   `ChargeFiscale` : Charges déductibles (intérêts, assurances, travaux, taxes)
*   `Amortissement` : Tableau d'amortissement LMNP
*   `VacanceLocative` : Périodes de vacance des locaux

### Migrations Importantes
*   `0011` : Ajout suivi des paiements de régularisations
*   `0012` : Création du modèle BailTarification
*   `0013` : Migration automatique des tarifs existants vers BailTarification
*   `0014` : Suppression des champs obsolètes (loyer_hc, charges, taxes) du modèle Bail
*   `0015` : Ajout des modèles de gestion patrimoniale (EstimationValeur, CreditImmobilier, etc.)
*   `0016` : Correction contrainte unique_together sur QuotePart

> **Note :** Les champs `loyer_hc`, `charges`, `taxes`, `indice_reference`, `trimestre_reference` sont désormais accessibles uniquement via des **properties** qui lisent depuis le modèle BailTarification.

## 📚 Documentation Technique

Pour les détails d'implémentation, consultez `DOCUMENTATION_TECHNIQUE.md` qui contient :
*   Architecture détaillée du système d'historique tarifaire
*   Guide de création de tarifications
*   Explication des calculs de régularisation
*   Détails des fonctions PDF
*   Guide de maintenance et de debugging

## 🐳 Installation sur NAS (Docker)

Pour installer sur un Synology ou QNAP :
1.  Copiez le dossier complet dans le dossier `docker` du NAS.
2.  Utilisez le fichier `docker-compose.yml` fourni.
3.  L'application sera accessible sur le port `8000`.

## 🔐 Sécurité et Backup

*   **Backup régulier recommandé :** Copiez régulièrement le fichier `db.sqlite3`
*   **Avant migrations :** **TOUJOURS** faire un backup de la base de données
*   **Production :** Utilisez PostgreSQL pour plus de robustesse
*   **Secrets :** Modifiez `SECRET_KEY` en production dans `settings.py`

## 🆘 Support et Maintenance

### Commandes Utiles

```bash
# Créer des migrations après modification des modèles
python manage.py makemigrations

# Appliquer les migrations
python manage.py migrate

# Créer un super-utilisateur
python manage.py createsuperuser

# Vérifier l'intégrité
python manage.py check

# Shell interactif
python manage.py shell
```

### Rollback d'une Migration

```bash
# Revenir à la migration précédente (ex: revenir à 0013)
python manage.py migrate core 0013

# ATTENTION : Restaurer depuis backup si données perdues
```

## 📝 Changelog

### Version 3.0 (Fevrier 2026) - Interface Custom Complete
- ✅ Nouvelle interface utilisateur sur mesure (Django Templates + HTMX + Tailwind CSS + Chart.js)
- ✅ Dashboard portfolio avec KPIs (valeur patrimoine, CRD, valeur nette, cashflow)
- ✅ Navigation centree sur les biens immobiliers (click immeuble → onglets)
- ✅ Vue detaillee immeuble avec 5 onglets HTMX (General, Locaux, Finances, Consommations, Estimations)
- ✅ Vue detaillee bail avec 4 onglets HTMX (Informations, Occupants, Regularisations, Documents)
- ✅ CRUD complet via modals HTMX pour 13 modeles (Immeuble, Local, Bail, Tarification, Occupant, Estimation, Credit, Depense, Cle, QuotePart, Consommation, Regularisation, Ajustement)
- ✅ Dashboard patrimoine avec graphiques Chart.js et projection 10 ans
- ✅ Bilan fiscal annuel par immeuble (revenus, charges deductibles, declaration 2044)
- ✅ Formulaire rapide d'ajout de depense optimise mobile
- ✅ Page de connexion custom + sidebar responsive
- ✅ 88 routes, 20 templates, 14 formulaires
- ✅ Coexistence avec l'admin Django legacy (/admin/)

### Version 2.1 (Février 2026)
- ✅ Dashboard Patrimoine avec graphiques et projection 10 ans
- ✅ Dashboard détail par immeuble (30+ indicateurs)
- ✅ Assistant Crédit Immobilier intelligent (3 modes de calcul)
- ✅ Gestion complète des crédits et échéanciers
- ✅ Suivi des charges fiscales et amortissements
- ✅ Gestion des vacances locatives
- ✅ Admin standalone pour Ajustements et Quote-parts
- ✅ Correction validation des chevauchements de tarifications

### Version 2.0 (Janvier 2026)
- ✅ Système d'historique tarifaire complet
- ✅ Assistant de révision de loyer (validation manuelle)
- ✅ Calcul mois par mois pour régularisations
- ✅ Suivi des paiements de régularisations
- ✅ Design harmonisé pour tous les PDFs

### Version 1.0
- ✅ Gestion immeubles, locaux, baux
- ✅ Génération PDF (quittances, avis d'échéance, régularisations)
- ✅ Clés de répartition et compteurs
- ✅ Interface admin Jazzmin

---

**Développé avec Django & Python** | Conforme aux exigences de gestion locative française (IRL, TVA, Régularisations)