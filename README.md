# Logiciel de Gestion Locative

Une application professionnelle et complète pour gérer vos biens immobiliers, locataires, baux, quittances et régularisations de charges. Conforme aux exigences de la gestion locative française (IRL, régularisation de charges, TVA).

## 🚀 Installation Rapide

1.  **Installation :** Double-cliquez sur `1_INSTALLATION.bat` (une seule fois).
2.  **Mise à jour :** Si vous modifiez le code, lancez `2_MISE_A_JOUR.bat`.
3.  **Lancement :** Double-cliquez sur `3_LANCER_LOGICIEL.bat`.

L'interface d'administration s'ouvrira automatiquement dans votre navigateur à l'adresse : `http://127.0.0.1:8000/admin/`

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

## 📊 Architecture Technique

### Stack Technologique
*   **Backend :** Django 6.0 (Python 3.x)
*   **Base de données :** SQLite (production) / PostgreSQL compatible
*   **PDF :** ReportLab
*   **Admin :** Django Admin avec Jazzmin
*   **Interface :** Templates Django

### Modèles Principaux
*   `Proprietaire` : Propriétaires des biens
*   `Immeuble` : Bâtiments
*   `Local` : Appartements, commerces, parkings, bureaux
*   `Bail` : Contrats de location
*   `BailTarification` : **Historique des tarifs** (loyer, charges, taxes avec périodes d'application)
*   `Occupant` : Locataires et garants
*   `Depense` : Charges et dépenses
*   `CleRepartition` : Clés de répartition des charges
*   `QuotePart` : Tantièmes par local
*   `Consommation` : Relevés de compteurs
*   `Regularisation` : Régularisations de charges avec suivi de paiement
*   `Ajustement` : Ajustements ponctuels de loyer

### Migrations Importantes
*   `0011` : Ajout suivi des paiements de régularisations
*   `0012` : Création du modèle BailTarification
*   `0013` : Migration automatique des tarifs existants vers BailTarification
*   `0014` : Suppression des champs obsolètes (loyer_hc, charges, taxes) du modèle Bail

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

### Version 2.0 (Janvier 2026)
- ✅ Système d'historique tarifaire complet
- ✅ Assistant de révision de loyer (validation manuelle)
- ✅ Calcul mois par mois pour régularisations
- ✅ Suivi des paiements de régularisations
- ✅ Design harmonisé pour tous les PDFs
- ✅ API REST avec historique tarifaire

### Version 1.0
- ✅ Gestion immeubles, locaux, baux
- ✅ Génération PDF (quittances, avis d'échéance, régularisations)
- ✅ Clés de répartition et compteurs
- ✅ Interface admin Jazzmin

---

**Développé avec Django & Python** | Conforme aux exigences de gestion locative française (IRL, TVA, Régularisations)