# Documentation Technique - Système de Gestion Locative

**Version** : 3.0 (Interface Custom)
**Dernière mise à jour** : Février 2026

---

## Table des Matières

1. [Architecture Générale](#1-architecture-générale)
2. [Modèles de Données](#2-modèles-de-données)
3. [Système d'Historique Tarifaire](#3-système-dhistorique-tarifaire)
4. [Fonctions PDF](#4-fonctions-pdf)
5. [Migrations](#5-migrations)
6. [Règles de Gestion](#6-règles-de-gestion)
7. [Guide de Maintenance](#7-guide-de-maintenance)
8. [Debugging et Troubleshooting](#8-debugging-et-troubleshooting)
9. [Assistant Crédit Immobilier](#9-assistant-crédit-immobilier)
10. [Dashboards Patrimoine](#10-dashboards-patrimoine) (v2.1)
    - 10.1 Dashboard Patrimoine Global
    - 10.2 Dashboard Détail Immeuble
    - 10.3 Modèles Patrimoine
    - 10.4 Bilan Fiscal par Immeuble
11. [Interface Custom](#11-interface-custom) (v3.0 - Complete)
    - 11.1 Architecture et Stack
    - 11.2 Structure des Fichiers
    - 11.3 Routes et Vues
    - 11.4 Templates et Composants
    - 11.5 Patterns HTMX
    - 11.6 Formulaires (ModelForms)
    - 11.7 CRUD Modal Pattern
    - 11.8 Pages Patrimoine
12. [Évolutions Futures](#12-évolutions-futures)

---

## 1. Architecture Générale

### 1.1 Stack Technologique

*   **Langage** : Python 3.14+
*   **Framework Web** : Django 6.0
*   **Base de Données** : SQLite (développement) / PostgreSQL compatible
*   **Génération PDF** : ReportLab
*   **Interface Admin (legacy)** : Django Admin avec Jazzmin 3.0.1 (accessible sur `/admin/`)
*   **Interface Custom (v3.0)** : Django Templates + HTMX + Tailwind CSS (accessible sur `/app/`)
*   **Templates** : Django Templates

### 1.2 Structure du Projet

```
logiciel gestion locative/
├── gestion_locative/          # Projet Django principal
│   ├── core/                  # Application principale
│   │   ├── models.py          # Modèles de données (18 modèles)
│   │   ├── views.py           # Vues et fonctions PDF
│   │   ├── admin.py           # Configuration admin (16+ classes)
│   │   ├── urls.py            # Routes (11 endpoints)
│   │   ├── pdf_generator.py   # Générateur de PDFs (classe PDFGenerator)
│   │   ├── calculators.py     # Calculateurs métier (BailCalculator)
│   │   ├── patrimoine_calculators.py  # Calculateurs patrimoine
│   │   ├── exceptions.py      # Exceptions personnalisées
│   │   ├── views_app.py       # Vues interface custom (/app/)
│   │   ├── urls_app.py        # Routes interface custom
│   │   ├── forms.py           # 14 ModelForms (CRUD interface custom)
│   │   ├── context_processors.py # Navigation context (sidebar)
│   │   ├── templatetags/
│   │   │   └── app_filters.py # Filtres templates (|euro, |pct)
│   │   ├── templates/
│   │   │   ├── app/           # Templates interface custom (Tailwind + HTMX)
│   │   │   ├── pdf_forms/     # Templates formulaires PDF
│   │   │   ├── admin/core/    # Templates dashboards admin
│   │   │   └── credit_forms/  # Template assistant credit
│   │   └── migrations/        # 17 migrations
│   ├── gestion_locative/
│   │   ├── settings.py        # Configuration Django
│   │   └── urls.py            # Routes principales
│   ├── manage.py              # CLI Django
│   └── db.sqlite3             # Base de données (SQLite)
├── README.md                  # Documentation utilisateur
├── DOCUMENTATION_TECHNIQUE.md # Ce fichier
├── QUICK_START.md             # Guide de démarrage rapide
├── CHANGELOG.md               # Historique des modifications
└── requirements.txt           # Dépendances Python
```

### 1.3 Philosophie de Conception

Le système repose sur **3 principes fondamentaux** :

1. **Historisation Complète** : Tous les changements tarifaires sont conservés avec audit trail (qui, quand, pourquoi).

2. **Contrôle Manuel Total** : Aucune mise à jour automatique. Toute modification nécessite validation utilisateur.

3. **Calculs Basés sur l'Historique** : Les documents utilisent automatiquement le bon tarif pour chaque période.

### 1.4 Choix d'Architecture

**Architecture Monolithique Django + Interface Custom**

Le projet utilise une architecture monolithique Django avec une interface custom (v3.0) :

1. **Interface Custom (v3.0)** : Templates Django + HTMX + Tailwind CSS via CDN. Pas de build JS, zero config. Navigation centree sur les biens immobiliers. Accessible sur `/app/`.

2. **Admin Legacy** : Django Admin + Jazzmin reste accessible sur `/admin/` pendant la transition. Sera supprime une fois l'interface custom complete.

3. **Simplicité de Déploiement** : Un seul processus Python, pas d'orchestration complexe. Tailwind et HTMX via CDN.

4. **Maintenance Réduite** : Moins de dépendances et de composants à maintenir.

**Base de Données**

*   **Développement** : SQLite (portable, zéro configuration)
*   **Production** : Migration facile vers PostgreSQL si volume important
*   **Avantage** : Pas de serveur DB à gérer pour petites installations

### 1.5 Justifications Techniques

#### Génération PDF : ReportLab

**Choix** : `reportlab` (génération bas niveau via Canvas)

**Alternatives rejetées** :
- WeasyPrint : Nécessite des dépendances système lourdes (Cairo, Pango)
- wkhtmltopdf : Dépendance binaire externe, difficile à maintenir

**Avantages de ReportLab** :
- ✅ Très rapide (génération directe sans conversion HTML)
- ✅ Aucune dépendance externe système
- ✅ Positionnement au pixel près (design précis)
- ✅ Portable (fonctionne sur Windows, Linux, Mac, Docker)

**Implémentation** :
```python
# Vues Django classiques retournant HttpResponse
def generer_quittance_pdf(request, pk):
    response = HttpResponse(content_type='application/pdf')
    p = canvas.Canvas(response, pagesize=A4)
    # Dessin direct avec coordonnées
    p.drawString(2*cm, 27*cm, "QUITTANCE DE LOYER")
    p.showPage()
    p.save()
    return response
```

#### Interface Utilisateur : Django Templates + HTMX + Tailwind CSS (v3.0)

**Choix** : Interface custom remplacant progressivement Django Admin

**Avantages** :
- Interface centree sur les biens (navigation intuitive vs liste de modeles admin)
- Mobile-first (formulaire depense rapide depuis telephone)
- HTMX pour l'interactivite (onglets, modals) sans ecrire de JavaScript
- Tailwind CSS via CDN (zero build, zero config)
- Pas de dependance NPM/Node.js

**Admin Django legacy** (accessible sur `/admin/`) :
- Reste disponible pendant la transition
- Utile pour operations avancees et debug
- Sera supprime une fois l'interface custom complete (Phase 7)

---

## 2. Modèles de Données

### 2.1 Vue d'Ensemble

```
Proprietaire
    └── Immeuble ─────────────────────────┐
            │                              │
            ├── Local                      ├── EstimationValeur (historique valeurs)
            │       └── Bail               ├── CreditImmobilier
            │               ├── Occupant   │       └── EcheanceCredit
            │               ├── Ajustement ├── ChargeFiscale
            │               ├── BailTarification ◄─── (v2.0)
            │               └── Regularisation    ├── Amortissement
            │                              │
            └── VacanceLocative ───────────┘

CleRepartition
    ├── QuotePart (tantièmes)
    ├── Depense
    └── Consommation (compteurs)
```

### 2.1bis Logique Métier des Entités

#### Entités Patrimoniales

**Proprietaire** : Entité légale possédant le bien
- Peut être : Personne physique, SCI, Indivision
- Attributs : Nom, Adresse, Type (Nom propre, SCI, Indivision)

**Immeuble** : Bâtiment
- Lié à un Proprietaire (ForeignKey)
- Attributs : Nom, Adresse, Ville, Code postal

**Local** : Unité locative (appartement, commerce, parking, bureau)
- Lié à un Immeuble (ForeignKey)
- Attributs : Surface (m²), Étage, Type, Numéro de porte
- **Logique** : Un local peut avoir plusieurs baux (historique), mais un seul avec `actif=True` à un instant T

#### Entités Contractuelles

**Bail** : Contrat de location
- Lié à un Local (ForeignKey)
- **Gestion financière** : via BailTarification (historique)
- **Gestion TVA** : soumis_tva, taux_tva (pour baux commerciaux)
- **Logique** : Un local peut avoir plusieurs baux successifs, un seul actif

**Occupant** : Personne physique liée à un Bail
- Rôle : LOCATAIRE ou GARANT (champ `choices`)
- Attributs : Nom, Prénom, Email, Téléphone
- **Logique** : Un bail peut avoir plusieurs occupants (co-location, garants)

#### Entités Comptables (Système de Charges)

Le système de répartition des charges est inspiré de la gestion de copropriété pour être flexible.

**CleRepartition** : Catégorie de charges
- Modes de répartition :
  - `TANTIEMES` : Répartition classique par quote-parts (ex: Taxe Foncière)
  - `CONSOMMATION` : Répartition par relevés de compteurs avec prix unitaire (ex: Eau)
- Attributs : Nom, Mode, Prix unitaire (si consommation)

**QuotePart** : Table de liaison pour tantièmes
- Lié à : CleRepartition + Local
- Attribut : Tantièmes (ex: 100/1000)
- **Logique** : Définit la part de chaque local dans une clé de répartition

**Depense** : Facture réelle enregistrée
- Liée à : Immeuble + CleRepartition
- Attributs : Date, Libelle, Montant, date_debut, date_fin (période)
- **Logique** : Les dates de période permettent le prorata temporis

**Consommation** : Relevés d'index pour compteurs
- Liée à : Local + CleRepartition
- Attributs : Index début, Index fin, Date début, Date relevé
- **Logique** : Quantité = Index fin - Index début, proratisée sur période

**Ajustement** : Ligne comptable manuelle
- Liée à : Bail
- Attributs : Montant (peut être négatif), Libellé, Date
- **Logique** : Crédit/Débit exceptionnel (ex: avoir pour travaux)

### 2.2 Modèle Bail

**Fichier** : `gestion_locative/core/models.py` (lignes 57-155)

**Champs** :
```python
class Bail(models.Model):
    local = ForeignKey(Local)
    type_charges = CharField  # PROVISION ou FORFAIT
    frequence_paiement = CharField  # MENSUEL ou TRIMESTRIEL
    date_debut = DateField
    date_fin = DateField (nullable)
    depot_garantie = DecimalField
    actif = BooleanField
    soumis_tva = BooleanField
    taux_tva = DecimalField
```

**⚠️ Champs SUPPRIMÉS** (Migration 0014) :
- `loyer_hc` → Désormais property
- `charges` → Désormais property
- `taxes` → Désormais property
- `indice_reference` → Désormais property
- `trimestre_reference` → Désormais property

**Properties de Backward Compatibility** :
```python
@property
def loyer_hc(self):
    """Loyer HC de la tarification actuelle."""
    tarif = self.tarification_actuelle
    return tarif.loyer_hc if tarif else 0

@property
def tarification_actuelle(self):
    """Tarification active aujourd'hui."""
    from django.utils import timezone
    return self.get_tarification_at(timezone.now().date())
```

**Méthodes Clés** :
```python
def get_tarification_at(self, target_date):
    """Récupère la tarification active à une date donnée."""
    return self.tarifications.filter(
        date_debut__lte=target_date,
        Q(date_fin__gte=target_date) | Q(date_fin__isnull=True)
    ).first()

def get_tarifications_for_period(self, start_date, end_date):
    """Récupère toutes les tarifications qui chevauchent une période."""
    return self.tarifications.filter(
        Q(date_debut__lte=end_date) &
        (Q(date_fin__gte=start_date) | Q(date_fin__isnull=True))
    ).order_by('date_debut')
```

### 2.3 Modèle BailTarification ⭐ NOUVEAU

**Fichier** : `gestion_locative/core/models.py` (lignes 127-219)

**Description** : Enregistre l'historique de tous les changements tarifaires avec périodes d'application.

**Champs** :
```python
class BailTarification(models.Model):
    # Relations
    bail = ForeignKey(Bail, related_name='tarifications')

    # Période de validité
    date_debut = DateField  # Date d'entrée en vigueur
    date_fin = DateField (nullable)  # None = encore active

    # Montants
    loyer_hc = DecimalField
    charges = DecimalField
    taxes = DecimalField

    # Indexation
    indice_reference = DecimalField (nullable)
    trimestre_reference = CharField

    # Audit trail
    created_at = DateTimeField (auto_now_add)
    reason = CharField  # Motif du changement
    notes = TextField
```

**Validation** :
```python
# Validation basique dans le modèle (models.py)
def clean(self):
    # 1. date_fin > date_debut
    if self.date_fin and self.date_fin <= self.date_debut:
        raise ValidationError("date_fin doit être > date_debut")
    # 2. date_debut >= bail.date_debut

# Validation des chevauchements dans le FormSet (admin.py)
class BailTarificationFormSet(BaseInlineFormSet):
    def clean(self):
        # Vérifie les chevauchements entre TOUTES les tarifications
        # du formulaire (y compris modifications non sauvegardées)
```

> **Note v2.1** : La validation des chevauchements a été déplacée du modèle vers le FormSet admin pour permettre la modification simultanée de plusieurs tarifications (fermeture ancienne + création nouvelle en une seule sauvegarde).

**Exemple de Données** :
```
| bail_id | date_debut | date_fin   | loyer_hc | charges | reason                  |
|---------|------------|------------|----------|---------|-------------------------|
| 1       | 2022-01-01 | 2024-12-31 | 420.00   | 30.00   | Tarification initiale   |
| 1       | 2025-01-01 | 2025-12-31 | 435.00   | 30.00   | Révision IRL T4 2024    |
| 1       | 2026-01-01 | NULL       | 450.00   | 35.00   | Révision IRL + charges  |
```

### 2.4 Modèle Regularisation

**Champs ajoutés (Migration 0011)** :
```python
class Regularisation(models.Model):
    bail = ForeignKey(Bail)
    date_creation = DateTimeField
    date_debut = DateField
    date_fin = DateField
    montant_reel = DecimalField
    montant_provisions = DecimalField
    solde = DecimalField

    # NOUVEAUX (v2.0)
    payee = BooleanField  # Suivi paiement
    date_paiement = DateField (nullable)
    notes = TextField
```

---

## 3. Système d'Historique Tarifaire

### 3.1 Principe de Fonctionnement

**Avant (v1.0)** :
```python
# Modification directe → perte de l'historique
bail.loyer_hc = 450.00
bail.save()
# ❌ L'ancien loyer (420.00) est perdu
```

**Maintenant (v2.0)** :
```python
# Création d'une nouvelle tarification
nouvelle_tarif = BailTarification.objects.create(
    bail=bail,
    date_debut=date(2026, 1, 1),
    date_fin=None,  # Active
    loyer_hc=450.00,
    charges=35.00,
    reason="Révision IRL T4 2025"
)

# Fermer l'ancienne
ancienne_tarif = bail.tarification_actuelle
ancienne_tarif.date_fin = date(2025, 12, 31)
ancienne_tarif.save()

# ✅ L'historique est conservé !
```

### 3.2 Workflow de Révision de Loyer

**Étape 1 : Calcul** (`generer_revision_loyer_pdf`)

Utilisateur remplit :
- Date d'application : 01/01/2026
- Nouvel indice IRL : 145.50
- Nouveau trimestre : T4 2025

Le système calcule :
```python
nouveau_loyer = ancien_loyer * (nouvel_indice / ancien_indice)
# Ex: 420.00 * (145.50 / 142.00) = 430.49
```

Si "Mettre à jour le loyer" coché :
```python
# Stocker dans session
request.session['nouvelle_tarification'] = {
    'bail_id': bail.id,
    'nouveau_loyer_hc': 430.49,
    'charges': 30.00,
    'nouvel_indice': 145.50,
    # ...
}

# Rediriger vers assistant
return redirect('creer_tarification_from_revision', pk=bail.pk)
```

**Étape 2 : Validation** (`creer_tarification_from_revision`)

Formulaire pré-rempli avec :
- Date de fin ancienne tarif : 31/12/2025 (auto)
- Date de début nouvelle : 01/01/2026
- Nouveau loyer : 430.49€ (modifiable)
- Charges : 30.00€ (modifiable)
- Motif : "Révision IRL T4 2024 → T4 2025"

Utilisateur valide → Création effective :
```python
# 1. Fermer ancienne
tarif_actuel.date_fin = date_fin_ancienne
tarif_actuel.save()

# 2. Créer nouvelle
BailTarification.objects.create(...)

# 3. Générer PDF notification locataire
```

### 3.3 Règles de Gestion

1. **Une seule tarification active** : `date_fin = None` sur une seule tarification par bail.

2. **Continuité temporelle** : Pas de trou entre les périodes.
   ```
   ✅ Bon : [01/01/2022 - 31/12/2024] puis [01/01/2025 - NULL]
   ❌ Mauvais : [01/01/2022 - 30/06/2024] puis [01/09/2024 - NULL]
   ```

3. **Protection de l'historique** : Tarifications de migration initiale non supprimables.

4. **Audit obligatoire** : Champ `reason` toujours rempli.

---

## 4. Fonctions PDF

### 4.1 Architecture Commune

**Pattern général** :
```python
def generer_xxx_pdf(request, pk):
    bail = Bail.objects.get(pk=pk)

    # 1. Formulaire (GET)
    if request.method != 'POST':
        return HttpResponse(html_form)

    # 2. Récupération paramètres (POST)
    date_xxx = request.POST.get('date_xxx')

    # 3. Récupération tarification
    tarif = bail.get_tarification_at(date_xxx)
    if not tarif:
        return HttpResponse("ERREUR: Aucune tarification", status=400)

    # 4. Calculs avec tarif.loyer_hc, tarif.charges, tarif.taxes

    # 5. Génération PDF
    response = HttpResponse(content_type='application/pdf')
    p = canvas.Canvas(response, pagesize=A4)
    # ... dessin ...
    p.showPage()
    p.save()
    return response
```

### 4.2 generer_quittance_pdf

**Fichier** : `views.py` (lignes 31-319)

**Spécificité** : Gère plusieurs périodes dans un seul PDF.

```python
for current_date in sorted_dates:
    # Tarif POUR CHAQUE PÉRIODE
    tarif = bail.get_tarification_at(current_date)
    if not tarif:
        return HttpResponse("ERREUR: Aucune tarification...", status=400)

    # Utiliser tarif.loyer_hc au lieu de bail.loyer_hc
    montant_loyer = tarif.loyer_hc
    montant_charges = tarif.charges
    montant_taxes = tarif.taxes
```

**Design** : En-tête gris #E0E0E0 avec cadres bailleur/locataire.

### 4.3 generer_regularisation_pdf ⭐ COMPLEXE

**Fichier** : `views.py` (lignes 556-1001)

**Spécificité** : Calcul **mois par mois** avec tarifs historiques.

**Pourquoi mois par mois ?**
- Si charges changent en cours d'année (ex: 30€ → 35€ au 01/07), le calcul doit utiliser les 2 tarifs.

**Algorithme** :
```python
total_provisions = 0.0
curr = date(start_year, start_month, 1)

while curr <= end_date:
    # Fin du mois
    last_day = calendar.monthrange(curr.year, curr.month)[1]
    month_end = date(curr.year, curr.month, last_day)

    # Intersection avec occupation
    p_start = max(curr, start_date)
    p_end = min(month_end, end_date)

    if p_start <= p_end:
        # TARIF DU 1ER DU MOIS
        tarif_mois = bail.get_tarification_at(curr)

        if not tarif_mois:
            return HttpResponse("ERREUR: Aucune tarification...", status=400)

        nb_jours_presence = (p_end - p_start).days + 1
        nb_jours_mois = last_day

        if nb_jours_presence == nb_jours_mois:
            montant_mois = float(tarif_mois.charges)
        else:
            montant_mois = float(tarif_mois.charges) * (nb_jours_presence / nb_jours_mois)

        total_provisions += montant_mois

    # Mois suivant
    curr = date(curr.year if curr.month < 12 else curr.year + 1,
                curr.month + 1 if curr.month < 12 else 1, 1)
```

**Exemple** :
```
Période : 01/01/2025 - 31/12/2025
Tarif 1 : 01/01 - 30/06 → 30€/mois
Tarif 2 : 01/07 - 31/12 → 35€/mois

Calcul :
- Janvier à Juin : 6 mois × 30€ = 180€
- Juillet à Décembre : 6 mois × 35€ = 210€
Total provisions : 390€ (au lieu de 360€ ou 420€ si on ne gérait pas l'historique)
```

### 4.4 generer_solde_tout_compte_pdf

**Fichier** : `views.py` (lignes 1251-1458)

**Spécificité** : Utilise le tarif à la date de sortie.

```python
tarif_sortie = bail.get_tarification_at(date_sortie)
if not tarif_sortie:
    return HttpResponse("ERREUR: Aucune tarification...", status=400)

montant_periode = float(tarif_sortie.loyer_hc)
loyer_prorata = montant_periode * (nb_jours_presence / nb_jours_periode)
```

**Design** : Harmonisé avec quittance/régularisation (en-tête gris, cadres).

### 4.5 Assistant de Révision

**Fichiers** :
- `generer_revision_loyer_pdf` (lignes 1003-1249)
- `creer_tarification_from_revision` (lignes 1460-1643)

**Workflow** : Voir section 3.2

---

## 5. Migrations

### 6.1 Chronologie

| Migration | Date | Description |
|-----------|------|-------------|
| 0011 | Jan 2026 | Suivi paiements régularisations (payee, date_paiement, notes) |
| 0012 | Jan 2026 | Création table BailTarification |
| 0013 | Jan 2026 | Migration automatique données → BailTarification |
| 0014 | Jan 2026 | Suppression champs obsolètes (loyer_hc, charges, taxes...) |
| 0015 | Jan 2026 | Modèles patrimoine (EstimationValeur, CreditImmobilier, EcheanceCredit, ChargeFiscale, Amortissement, VacanceLocative) |
| 0016 | Fév 2026 | Correction unique_together sur QuotePart |

### 5.2 Migration 0013 : Migration des Données

**Fichier** : `core/migrations/0013_migrate_bail_to_tarifications.py`

**Fonction** :
```python
def migrate_bail_tarifications(apps, schema_editor):
    Bail = apps.get_model('core', 'Bail')
    BailTarification = apps.get_model('core', 'BailTarification')

    for bail in Bail.objects.all():
        date_debut_tarif = bail.date_debut or date(2020, 1, 1)

        BailTarification.objects.create(
            bail=bail,
            date_debut=date_debut_tarif,
            date_fin=None,  # Active
            loyer_hc=bail.loyer_hc,
            charges=bail.charges,
            taxes=bail.taxes,
            indice_reference=bail.indice_reference,
            trimestre_reference=bail.trimestre_reference or '',
            reason="Tarification initiale (migration automatique)"
        )
```

**Rollback** :
```python
def reverse_migration(apps, schema_editor):
    BailTarification = apps.get_model('core', 'BailTarification')
    BailTarification.objects.all().delete()
```

### 5.3 Migration 0014 : Suppression Champs

**Opérations** :
```python
operations = [
    migrations.RemoveField(model_name='bail', name='loyer_hc'),
    migrations.RemoveField(model_name='bail', name='charges'),
    migrations.RemoveField(model_name='bail', name='taxes'),
    migrations.RemoveField(model_name='bail', name='indice_reference'),
    migrations.RemoveField(model_name='bail', name='trimestre_reference'),
]
```

**⚠️ ATTENTION** : Irréversible sans restauration backup.

### 5.4 Commandes Utiles

```bash
# Créer migration
python manage.py makemigrations core

# Appliquer toutes
python manage.py migrate

# Appliquer jusqu'à 0013
python manage.py migrate core 0013

# Voir état
python manage.py showmigrations core

# Voir SQL (sans appliquer)
python manage.py sqlmigrate core 0014

# Rollback
python manage.py migrate core 0013
```

---

## 6. Règles de Gestion

### 6.0 Glossaire des Termes Métier

| Terme | Définition | Exemple |
|-------|------------|---------|
| **IRL** | Indice de Référence des Loyers (INSEE) - Logements vides | 142.56 (T4 2024) |
| **ILC** | Indice des Loyers Commerciaux - Baux commerciaux | 125.83 (T4 2024) |
| **ILAT** | Indice des Loyers des Activités Tertiaires | 131.45 (T4 2024) |
| **Régularisation de charges** | Ajustement annuel : Charges réelles - Provisions versées = Solde | Réel: 350€, Provisions: 360€ → Avoir: 10€ |
| **Prorata temporis** | Au prorata du temps (proportionnel aux jours) | 15j sur 30j = 50% du montant |
| **Tantièmes** | Quote-part d'un local dans les charges | Local A: 100/1000 = 10% |
| **Loyer HC** | Loyer Hors Charges | 420.00€ |
| **Provisions sur charges** | Avances mensuelles/trimestrielles pour charges (régularisées annuellement) | 30€/mois appelés, régul en fin d'année |
| **Forfait de charges** | Charges fixes incluses dans le loyer, pas de régularisation | Loyer tout compris |
| **Quittance** | Reçu attestant du paiement du loyer (document justificatif) | "Je soussigné certifie avoir reçu..." |
| **Avis d'échéance** | Appel de loyer avant paiement (facture) | "Montant à payer avant le..." |
| **Solde de tout compte** | Arrêté de compte en fin de bail (restitution dépôt) | Dépôt: 840€ - Retenues: 50€ = 790€ |
| **Dépôt de garantie** | Caution versée par le locataire (max 1 mois vide, 2 mois commercial) | 420€ (1 mois de loyer HC) |
| **Clé de répartition** | Méthode de calcul pour répartir une charge | Par tantièmes, consommation, surface |
| **Tantièmes généraux** | Quote-part pour charges communes bâtiment | Ascenseur, gardien, toiture |
| **Tantièmes spéciaux** | Quote-part pour charges spécifiques | Eau (compteurs), chauffage collectif |
| **Quote-part** | Part attribuée à un local dans une clé de répartition | 100/1000 = 10% des charges |
| **Ajustement** | Correction manuelle du compte locataire | Avoir pour travaux: -50€ |
| **Bail précaire** | Bail court (< 3 ans habitation, < 2 ans commercial) | Bail étudiant 9 mois |
| **Bail 3/6/9** | Bail commercial classique (3 ans, renouvelable par périodes de 3 ans) | Commerce: 9 ans max avant révision |
| **Taxe foncière** | Impôt sur la propriété (parfois refacturé au locataire) | 1200€/an pour l'immeuble |
| **TOM** | Taxe Ordures Ménagères (souvent refacturée au locataire) | 180€/an au prorata |
| **TVA immobilière** | TVA sur loyers commerciaux meublés (20%) | Loyer HC+Charges × 20% |

### 6.1 Proratisation des Charges (Régularisation)

**Formule Dépenses** :
```
Si dépense avec période (ex: Taxe Foncière 01/01-31/12) :

Montant Dû = Montant Facture
           × (Tantièmes Local / Total Tantièmes)
           × (Jours Présence / Jours Facture)
```

**Formule Provisions** (avec historique tarifaire) :
```
Provisions Dues = Σ (Charges du tarif actif au 1er du mois × Prorata du mois)

Pour chaque mois de la période :
    Tarif = get_tarification_at(1er du mois)
    Si mois complet : Montant = Tarif.charges
    Sinon : Montant = Tarif.charges × (Jours présence / Jours mois)
```

### 6.2 Gestion des Compteurs

**Si relevé couvre une période plus large que régularisation** :
```
Consommation Régul = Consommation Totale
                   × (Jours Régul / Jours Relevé)
```

### 6.3 TVA et Baux Commerciaux

**Si `bail.soumis_tva = True`** :
```
TVA = (Loyer HC + Charges) × Taux TVA / 100
Loyer TTC = Loyer HC + Charges + Taxes + TVA

Note : Taxes (TF, TOM) ne sont PAS soumises à TVA
```

---

## 7. Guide de Maintenance

### 7.1 Créer une Tarification Manuellement

**Via Admin** :
```
1. Admin → Tarifications → Ajouter
2. Remplir :
   - Bail
   - Date début : 01/01/2026
   - Date fin : Vide
   - Loyer HC, Charges, Taxes
   - Motif : "Révision annuelle"
3. Fermer ancienne tarification :
   - Aller dans tarification précédente
   - date_fin = 31/12/2025
   - Sauvegarder
```

**Via Code** :
```python
from core.models import Bail, BailTarification
from datetime import date

bail = Bail.objects.get(pk=1)

# 1. Fermer ancienne
tarif_actuel = bail.tarification_actuelle
tarif_actuel.date_fin = date(2025, 12, 31)
tarif_actuel.save()

# 2. Créer nouvelle
BailTarification.objects.create(
    bail=bail,
    date_debut=date(2026, 1, 1),
    date_fin=None,
    loyer_hc=450.00,
    charges=35.00,
    taxes=0.00,
    reason="Révision IRL T4 2025"
)
```

### 7.2 Vérifier Continuité des Tarifications

**Script de diagnostic** :
```python
python manage.py shell

from core.models import Bail
from datetime import timedelta

for bail in Bail.objects.filter(actif=True):
    tarifs = bail.tarifications.order_by('date_debut')

    for i in range(len(tarifs) - 1):
        current = tarifs[i]
        next = tarifs[i+1]

        if current.date_fin:
            expected = current.date_fin + timedelta(days=1)
            if next.date_debut != expected:
                print(f"⚠️ Trou: {bail} entre {current.date_fin} et {next.date_debut}")
```

### 7.3 Backup et Restauration

**Backup** :
```bash
# Backup simple
cp gestion_locative/db.sqlite3 backups/db_backup_$(date +%Y%m%d).sqlite3

# Avec timestamp
cp gestion_locative/db.sqlite3 "backups/db_$(date +%Y%m%d_%H%M%S).sqlite3"
```

**Restauration** :
```bash
# Arrêter serveur
# Ctrl+C dans le terminal du serveur

# Restaurer
cp backups/db_backup_20260118.sqlite3 gestion_locative/db.sqlite3

# Redémarrer
python manage.py runserver
```

### 7.4 Mise à Jour du Code

```bash
# 1. BACKUP OBLIGATOIRE
cp gestion_locative/db.sqlite3 backups/db_avant_maj.sqlite3

# 2. Pull modifications (si Git)
git pull

# 3. Dépendances
pip install -r requirements.txt

# 4. Migrations
python manage.py migrate

# 5. Collecte fichiers statiques (production)
python manage.py collectstatic --noinput

# 6. Redémarrer
```

---

## 8. Debugging et Troubleshooting

### 8.1 Erreur : "Aucune tarification définie"

**Symptôme** :
```
ERREUR: Aucune tarification définie pour 15/06/2025.
```

**Diagnostic** :
```python
python manage.py shell

from core.models import Bail
from datetime import date

bail = Bail.objects.get(pk=1)
target = date(2025, 6, 15)

tarif = bail.get_tarification_at(target)
print(f"Tarif trouvé : {tarif}")

print("\nTarifications existantes :")
for t in bail.tarifications.all():
    print(f"  {t.date_debut} → {t.date_fin or 'en cours'}")
```

**Solution** :
- Créer tarification pour combler le trou
- OU modifier date_fin de la tarification précédente

### 8.2 Erreur : "Property loyer_hc returns 0"

**Cause** : Aucune tarification active aujourd'hui.

**Diagnostic** :
```python
from core.models import Bail
from django.utils import timezone

bail = Bail.objects.get(pk=1)
today = timezone.now().date()

print(f"Aujourd'hui : {today}")
print(f"Tarif actuel : {bail.tarification_actuelle}")
print(f"Loyer (property) : {bail.loyer_hc}")

for t in bail.tarifications.all():
    active = "ACTIVE" if (not t.date_fin or t.date_fin >= today) else "FERMÉE"
    print(f"{active} - {t.date_debut} → {t.date_fin or '∞'} - {t.loyer_hc}€")
```

### 8.3 Performance : Requêtes N+1

**Problème** :
```python
# Mauvais (N+1 queries)
baux = Bail.objects.all()
for bail in baux:
    print(bail.loyer_hc)  # Query pour CHAQUE bail
```

**Solution** :
```python
# Bon (2 queries seulement)
baux = Bail.objects.prefetch_related('tarifications').all()
for bail in baux:
    print(bail.loyer_hc)  # Pas de query supplémentaire
```

### 8.4 Migration Bloquée

**Diagnostic** :
```bash
python manage.py showmigrations core
python manage.py migrate --plan
```

**Solutions** :

1. **Forcer l'état** (DANGER) :
```bash
python manage.py migrate --fake core 0014
```

2. **Rollback** :
```bash
python manage.py migrate core 0013
```

3. **Restauration complète** :
```bash
cp backups/db_backup_avant_tarif.sqlite3 gestion_locative/db.sqlite3
python manage.py migrate
```

### 8.5 Compatibilité Jazzmin / Django 6.0

**Symptôme** :
```
TypeError at /admin/core/xxx/
args or kwargs must be provided.
Exception Location: jazzmin/templatetags/jazzmin.py, line 256
```

**Cause** : Django 6.0 a modifié `format_html()` pour exiger des arguments.

**Solution** : Patch local de Jazzmin (en attendant une mise à jour officielle)

1. Localiser le fichier :
```bash
# Windows (Python 3.14)
C:\Users\<user>\AppData\Roaming\Python\Python314\site-packages\jazzmin\templatetags\jazzmin.py
```

2. Modifier ligne ~256-257 :
```python
# AVANT
return format_html(html_str)

# APRÈS
# Patch pour Django 6.0: format_html() exige maintenant des arguments
return mark_safe(html_str)
```

3. Supprimer le cache Python :
```bash
rm jazzmin/templatetags/__pycache__/jazzmin.cpython-*.pyc
```

4. Redémarrer le serveur Django.

**Note** : `mark_safe` est déjà importé dans le fichier.

### 8.6 Activer les Logs SQL

**Dans `settings.py`** :
```python
DEBUG = True

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'loggers': {
        'django.db.backends': {
            'handlers': ['console'],
            'level': 'DEBUG',
        },
    },
}
```

**Voir queries dans shell** :
```python
from django.db import connection
from django.test.utils import override_settings

with override_settings(DEBUG=True):
    bail = Bail.objects.get(pk=1)
    print(bail.loyer_hc)

    for query in connection.queries:
        print(query['sql'])
```

---

## 9. Assistant Crédit Immobilier

### 9.1 Principe de Fonctionnement

L'Assistant Crédit Immobilier est un **formulaire intelligent** qui calcule automatiquement les données manquantes lors de la création d'un crédit.

**Problème résolu** : Lors de la négociation d'un crédit, on ne connaît généralement pas toutes les données. L'assistant permet de renseigner uniquement ce qu'on connaît et calcule le reste.

### 9.2 Les 3 Modes de Calcul

#### Mode 1 : Capital connu

**Données à saisir** :
- Capital emprunté
- Taux d'intérêt
- Durée (mois)

**Calculé automatiquement** :
- Mensualité hors assurance
- Coût total du crédit

**Formule utilisée** (crédit amortissable) :
```
M = C × (r × (1+r)^n) / ((1+r)^n - 1)

Où :
- M = Mensualité
- C = Capital
- r = Taux mensuel (taux annuel / 12)
- n = Nombre de mois
```

#### Mode 2 : Mensualité connue

**Données à saisir** :
- Mensualité hors assurance
- Taux d'intérêt
- Durée (mois)

**Calculé automatiquement** :
- Capital emprunté

**Formule utilisée** (inverse de la formule amortissable) :
```
C = M × ((1+r)^n - 1) / (r × (1+r)^n)
```

#### Mode 3 : Capital + Mensualité connus

**Données à saisir** :
- Capital emprunté
- Mensualité hors assurance
- Durée (mois)

**Calculé automatiquement** :
- Taux d'intérêt

**Méthode utilisée** : **Newton-Raphson**

Résolution numérique itérative car il n'existe pas de formule analytique directe pour calculer le taux.

```python
def calculateTaux(capital, mensualite, duree):
    taux = 0.05  # Estimation initiale 5%
    tolerance = 0.0001
    maxIterations = 100

    for i in range(maxIterations):
        tauxMensuel = taux / 12
        mensualiteCalculee = capital * (tauxMensuel * (1 + tauxMensuel)^duree) / ((1 + tauxMensuel)^duree - 1)

        if abs(mensualiteCalculee - mensualite) < tolerance:
            return taux * 100  # Convergence atteinte

        # Calcul dérivée et mise à jour
        derivee = ...
        taux = taux - (mensualiteCalculee - mensualite) / derivee

    return taux * 100
```

### 9.3 Support des Crédits In Fine

L'assistant détecte automatiquement le type de crédit et adapte les formules :

**Crédit Amortissable** : Capital + intérêts remboursés mensuellement
**Crédit In Fine** : Intérêts mensuels uniquement, capital en fin de période

**Formule In Fine** :
```
M = C × (taux_annuel / 12)
```

### 9.4 Interface Utilisateur

**Fichier** : `core/templates/credit_forms/assistant_credit.html`

**Technologies** :
- HTML5 / CSS3 (design moderne gradient violet/bleu)
- JavaScript vanilla (calculs temps réel côté client)
- Django Templates (backend)

**Fonctionnalités UX** :
- Sélection du mode par cartes cliquables
- Calculs instantanés lors de la saisie (événements `input`)
- Champs calculés en lecture seule (grisés)
- Affichage des résultats avant enregistrement
- Validation HTML5 des champs requis

### 9.5 Vue Django

**Fichier** : `core/views.py` (lignes 675-736)

```python
@staff_member_required
def assistant_credit(request, immeuble_id=None):
    """
    Assistant intelligent pour créer un crédit immobilier.
    """
    immeubles = Immeuble.objects.all()

    if request.method == 'POST':
        # Récupération des données (déjà calculées côté client)
        capital_emprunte = Decimal(request.POST.get('capital_emprunte'))
        taux_interet = Decimal(request.POST.get('taux_interet'))
        duree_mois = int(request.POST.get('duree_mois'))

        # Création du crédit
        credit = CreditImmobilier.objects.create(...)

        # Redirection vers l'admin du crédit
        return redirect('admin:core_creditimmobilier_change', args=[credit.pk])

    return render(request, 'credit_forms/assistant_credit.html', {'immeubles': immeubles})
```

### 9.6 Routes

**Fichier** : `core/urls.py`

```python
urlpatterns = [
    # ...
    path('assistant-credit/', assistant_credit, name='assistant_credit'),
    path('assistant-credit/<int:immeuble_id>/', assistant_credit, name='assistant_credit_immeuble'),
]
```

**URLs accessibles** :
- `/api/assistant-credit/` - Formulaire générique
- `/api/assistant-credit/5/` - Formulaire avec immeuble pré-sélectionné

### 9.7 Intégration dans l'Admin

**Configuration Jazzmin** (`settings.py`) :

```python
JAZZMIN_SETTINGS = {
    "custom_links": {
        "core": [
            {
                "name": "Assistant Crédit Immobilier",
                "url": "/api/assistant-credit/",
                "icon": "fas fa-calculator",
            },
        ]
    },
    "topmenu_links": [
        {"name": "Assistant Crédit", "url": "/api/assistant-credit/", "icon": "fas fa-calculator"},
    ],
}
```

**Accès** :
1. Menu latéral → Section "Core" → "Assistant Crédit Immobilier"
2. Menu du haut → "Assistant Crédit"

### 9.8 Exemple d'Utilisation

**Scénario** : Vous négociez avec votre banque et connaissez la mensualité.

1. Ouvrir l'assistant (`/api/assistant-credit/`)
2. Cliquer sur le mode **"Mensualité connue"**
3. Remplir :
   - Immeuble : "Résidence Les Pins"
   - Banque : "Crédit Agricole"
   - Date début : 01/01/2024
   - **Mensualité** : 850 € (hors assurance)
   - **Taux** : 2.5 %
   - **Durée** : 240 mois (20 ans)
   - Assurance : 15 €/mois
4. Le formulaire calcule instantanément :
   - **Capital** : ~156 500 €
   - **Coût total** : 207 600 €
5. Valider → Crédit enregistré et redirection vers sa fiche admin

### 9.9 Avantages

- ✅ **Gain de temps** : Plus besoin de calculatrice ou Excel
- ✅ **Précision** : Formules mathématiques exactes
- ✅ **Flexibilité** : 3 modes selon les données disponibles
- ✅ **Intégré** : Directement dans l'interface admin Django
- ✅ **Temps réel** : Calculs instantanés côté client (pas de rechargement)
- ✅ **Validation** : Vérification avant enregistrement

### 9.10 Limites et Évolutions Possibles

**Limites actuelles** :
- Calcul du taux (mode 3) : précision ~0.001% (suffisant pour usage pratique)
- Support uniquement crédits amortissables et in fine classiques
- Pas de gestion des différés ou modulations

**Évolutions futures** :
- **Simulation comparative** : Afficher plusieurs scénarios côte à côte
- **Import depuis offre bancaire** : Parsing PDF/email pour pré-remplir
- **Calculateur de TAEG** : Inclure frais de dossier, assurances, garanties
- **Optimisation fiscale** : Suggestion répartition capital/intérêts pour déclaration

---

## 10. Dashboards Patrimoine ⭐ NOUVEAU (v2.1)

### 10.1 Dashboard Patrimoine Global

**URL** : `/api/patrimoine/dashboard/`
**Accès** : `@staff_member_required`

**Indicateurs affichés** :
- Valeur totale du patrimoine
- Capital restant dû (tous crédits)
- Valeur nette (valeur - CRD)
- Cash-flow mensuel global
- Nombre total de locaux

**Graphiques** :
- Répartition valeur par immeuble (camembert)
- Projection sur 10 ans (courbes valeur, CRD, valeur nette)

**Calculateurs utilisés** (`patrimoine_calculators.py`) :
- `PatrimoineCalculator.get_valeur_actuelle()` - Dernière estimation ou prix achat
- `PatrimoineCalculator.get_capital_restant_du()` - Somme CRD tous crédits
- `RentabiliteCalculator.get_cashflow_mensuel()` - Loyers - mensualités crédits
- `RentabiliteCalculator.get_rendement_brut()` - (Loyers annuels / Valeur) × 100

### 10.2 Dashboard Détail Immeuble

**URL** : `/api/patrimoine/immeuble/<id>/`
**Accès** : `@staff_member_required`

**30+ indicateurs organisés en sections** :

**Section Patrimoine** :
- Valeur actuelle, CRD, Valeur nette, Plus-value latente
- Coût d'acquisition (prix + frais)

**Section Surface** :
- Surface totale, Prix/m² achat, Prix/m² actuel

**Section Loyers** :
- Loyers mensuels/annuels, Charges mensuelles
- Nombre locaux loués/vacants

**Section Rentabilité** :
- Rendement brut, Rendement net
- Cash-flow mensuel/annuel

**Section Ratios** :
- Taux d'occupation, Taux de vacance
- Ratio d'endettement

**Détails par local** :
- Liste des locaux avec statut, loyer, surface

**Crédits associés** :
- Liste des crédits avec CRD, mensualité, date fin

**Optimisation requêtes** :
```python
immeuble = get_object_or_404(
    Immeuble.objects.prefetch_related(
        'credits', 'locaux__baux__tarifications', 'locaux__baux__occupants',
        'estimations', 'charges_fiscales', 'locaux__vacances'
    ),
    pk=immeuble_id
)
```

### 10.3 Modèles Patrimoine

**EstimationValeur** :
```python
immeuble = ForeignKey(Immeuble)
date_estimation = DateField
valeur = DecimalField  # En euros
source = CharField  # MANUELLE, AGENT, NOTAIRE, DVF
notes = TextField
```

**CreditImmobilier** :
```python
immeuble = ForeignKey(Immeuble)
banque = CharField
type_credit = CharField  # AMORTISSABLE, IN_FINE
capital_emprunte = DecimalField
taux_interet = DecimalField
duree_mois = IntegerField
date_debut = DateField
assurance_mensuelle = DecimalField

# Properties calculées
@property def mensualite  # Mensualité totale (capital + intérêts + assurance)
@property def capital_restant_du  # CRD à aujourd'hui
```

**EcheanceCredit** :
```python
credit = ForeignKey(CreditImmobilier)
numero_echeance = IntegerField
date_echeance = DateField
capital_rembourse = DecimalField
interets = DecimalField
assurance = DecimalField
capital_restant_du = DecimalField
payee = BooleanField
```

**ChargeFiscale** :
```python
immeuble = ForeignKey(Immeuble)
type_charge = CharField  # INTERETS, ASSURANCE_EMPRUNT, ASSURANCE_PNO, TRAVAUX, TAXE_FONCIERE, etc.
annee = IntegerField
montant = DecimalField
libelle = CharField
justificatif = FileField  # Optionnel
```

**VacanceLocative** :
```python
local = ForeignKey(Local)
date_debut = DateField
date_fin = DateField (nullable)
motif = CharField  # TRAVAUX, RECHERCHE, DELIBERE, AUTRE
notes = TextField

@property def duree_jours  # Nombre de jours de vacance
```

### 10.4 Bilan Fiscal par Immeuble

**URL** : `/api/fiscal/immeuble/<id>/`
**Accès** : `@staff_member_required`

**Description** : Génère un récapitulatif fiscal annuel pour un immeuble, calculant automatiquement les charges déductibles.

**Calculs automatiques** :

1. **Intérêts d'emprunt** (depuis `EcheanceCredit`)
```python
echeances_annee = credit.echeances.filter(
    date_echeance__gte=date(annee, 1, 1),
    date_echeance__lte=date(annee, 12, 31)
)
total_interets = sum(e.interets for e in echeances_annee)
```

2. **Assurance emprunt** (depuis `EcheanceCredit`)
```python
total_assurance = sum(e.assurance for e in echeances_annee)
```

3. **Autres charges** (depuis `ChargeFiscale`)
```python
charges_manuelles = immeuble.charges_fiscales.filter(annee=annee)
```

**Récapitulatif fiscal** :
```
Revenus bruts (loyers encaissés)     + X €
Intérêts d'emprunt                   - X €
Assurance emprunt                    - X €
Autres charges déductibles           - X €
────────────────────────────────────────────
RÉSULTAT FONCIER                     = X €
```

**Si déficit foncier** :
- Affichage du montant reportable
- Rappel des règles fiscales (limite 10 700€, report 10 ans)

**Types de charges fiscales supportés** (`ChargeFiscale.type_charge`) :
- `INTERETS` - Intérêts d'emprunt (calcul automatique si EcheanceCredit)
- `ASSURANCE_EMPRUNT` - Assurance emprunt (calcul automatique si EcheanceCredit)
- `ASSURANCE_PNO` - Assurance propriétaire non occupant
- `TRAVAUX` - Travaux déductibles
- `TAXE_FONCIERE` - Taxe foncière
- `FRAIS_GESTION` - Frais de gestion
- `AUTRE` - Autres charges déductibles

**Accès depuis l'admin** :
1. Admin → Immeubles → Sélectionner un immeuble
2. Actions → "Voir bilan fiscal"

**Template** : `core/templates/admin/core/bilan_fiscal.html`

---

## 11. Interface Custom (v3.0 - Complete)

### 11.1 Architecture et Stack

**Objectif** : Remplacer l'interface Django Admin par une interface sur mesure, centree sur les biens immobiliers, optimisee mobile.

**Stack Frontend** :
- **Tailwind CSS** via CDN (`@tailwindcss/browser@4`) - Styling utilitaire, zero build
- **HTMX** via CDN (`htmx.org@2.0.4`) - Interactivite (onglets, modals, formulaires) sans JavaScript custom
- **Chart.js** via CDN - Graphiques patrimoine (camembert repartition, courbes projection)

**Principe de coexistence** :
- Interface custom : `/app/` (point d'entree principal, `@login_required`)
- Admin Django legacy : `/admin/` (accessible pour operations avancees)
- Racine `/` redirige vers `/app/`
- `LOGIN_URL = '/app/login/'` et `LOGIN_REDIRECT_URL = '/app/'`

**Aucune nouvelle dependance Python requise**. Tout le frontend est charge via CDN.

### 11.2 Structure des Fichiers

```
core/
├── views_app.py           # ~50 vues (dashboard, detail, CRUD, patrimoine)
├── urls_app.py            # 88 routes /app/...
├── forms.py               # 14 ModelForms
├── context_processors.py  # Injection navigation (liste immeubles)
├── templatetags/
│   ├── __init__.py
│   └── app_filters.py    # Filtres |euro et |pct
└── templates/app/
    ├── base.html                  # Layout : sidebar, CDN, modal container
    ├── _modal_form.html           # Template modal generique pour CRUD
    ├── _modal_confirm_delete.html # Confirmation suppression
    ├── auth/
    │   └── login.html             # Page de connexion
    ├── dashboard/
    │   └── index.html             # Dashboard portfolio (KPIs + cartes)
    ├── depenses/
    │   └── quick_add.html         # Formulaire rapide (mobile-first)
    ├── immeubles/
    │   ├── detail.html            # Vue detaillee (5 onglets HTMX)
    │   ├── _tab_general.html      # Infos, acquisition, regime fiscal
    │   ├── _tab_locaux.html       # Locaux avec CRUD
    │   ├── _tab_finances.html     # Credits, depenses, cles repartition avec CRUD
    │   ├── _tab_consommations.html # Releves compteurs avec CRUD
    │   └── _tab_estimations.html  # Historique valorisations avec CRUD
    ├── baux/
    │   ├── detail.html            # Vue detaillee bail (4 onglets HTMX)
    │   ├── _tab_info.html         # Informations + tarifications avec CRUD
    │   ├── _tab_occupants.html    # Locataires et garants avec CRUD
    │   ├── _tab_regularisations.html # Regularisations + ajustements avec CRUD
    │   └── _tab_documents.html    # Generation PDF
    ├── patrimoine/
    │   ├── dashboard.html         # Dashboard patrimoine (graphiques Chart.js)
    │   └── bilan_fiscal.html      # Bilan fiscal annuel par immeuble
    └── charges/
        └── cle_detail.html        # Detail cle repartition + quotes-parts
```

### 11.3 Routes et Vues

**Fichier** : `core/urls_app.py` (88 routes)

**Auth et navigation** :

| URL | Vue | Description |
|-----|-----|-------------|
| `/app/login/` | `login_view` | Page de connexion custom |
| `/app/logout/` | `logout_view` | Deconnexion |
| `/app/` | `dashboard_view` | Dashboard portfolio (KPIs + immeubles) |
| `/app/depenses/ajouter/` | `depense_quick_add_view` | Formulaire rapide depense (mobile-first) |

**Immeubles** :

| URL | Vue | Description |
|-----|-----|-------------|
| `/app/immeubles/<pk>/` | `immeuble_detail_view` | Vue detaillee immeuble |
| `/app/immeubles/<pk>/tab/<tab>/` | `immeuble_tab_view` | Partial HTMX (general, locaux, finances, consommations, estimations) |
| `/app/immeubles/creer/` | `immeuble_create_view` | Creation immeuble (modal) |
| `/app/immeubles/<pk>/modifier/` | `immeuble_edit_view` | Modification immeuble (modal) |
| `/app/immeubles/<pk>/supprimer/` | `immeuble_delete_view` | Suppression immeuble (modal) |

**Locaux** :

| URL | Vue | Description |
|-----|-----|-------------|
| `/app/immeubles/<pk>/locaux/creer/` | `local_create_view` | Creation local (modal) |
| `/app/locaux/<pk>/modifier/` | `local_edit_view` | Modification local (modal) |
| `/app/locaux/<pk>/supprimer/` | `local_delete_view` | Suppression local (modal) |

**Baux** :

| URL | Vue | Description |
|-----|-----|-------------|
| `/app/baux/<pk>/` | `bail_detail_view` | Vue detaillee bail |
| `/app/baux/<pk>/tab/<tab>/` | `bail_tab_view` | Partial HTMX (info, occupants, regularisations, documents) |
| `/app/locaux/<pk>/baux/creer/` | `bail_create_view` | Creation bail (modal) |
| `/app/baux/<pk>/modifier/` | `bail_edit_view` | Modification bail (modal) |

**Tarifications, Occupants** :

| URL | Vue | Description |
|-----|-----|-------------|
| `/app/baux/<pk>/tarifications/creer/` | `tarification_create_view` | Nouvelle tarification (modal) |
| `/app/baux/<pk>/occupants/creer/` | `occupant_create_view` | Ajouter occupant (modal) |
| `/app/occupants/<pk>/modifier/` | `occupant_edit_view` | Modifier occupant (modal) |
| `/app/occupants/<pk>/supprimer/` | `occupant_delete_view` | Supprimer occupant (modal) |

**Estimations, Credits** :

| URL | Vue | Description |
|-----|-----|-------------|
| `/app/immeubles/<pk>/estimations/creer/` | `estimation_create_view` | Nouvelle estimation (modal) |
| `/app/estimations/<pk>/supprimer/` | `estimation_delete_view` | Supprimer estimation (modal) |
| `/app/immeubles/<pk>/credits/creer/` | `credit_create_view` | Nouveau credit (modal) |
| `/app/credits/<pk>/modifier/` | `credit_edit_view` | Modifier credit (modal) |
| `/app/credits/<pk>/supprimer/` | `credit_delete_view` | Supprimer credit (modal) |

**Depenses, Cles de repartition** :

| URL | Vue | Description |
|-----|-----|-------------|
| `/app/immeubles/<pk>/depenses/creer/` | `depense_create_view` | Nouvelle depense (modal) |
| `/app/depenses/<pk>/modifier/` | `depense_edit_view` | Modifier depense (modal) |
| `/app/depenses/<pk>/supprimer/` | `depense_delete_view` | Supprimer depense (modal) |
| `/app/immeubles/<pk>/cles/creer/` | `cle_create_view` | Nouvelle cle repartition (modal) |
| `/app/cles/<pk>/` | `cle_detail_view` | Detail cle + quotes-parts |
| `/app/cles/<pk>/modifier/` | `cle_edit_view` | Modifier cle (modal) |
| `/app/cles/<pk>/supprimer/` | `cle_delete_view` | Supprimer cle (modal) |

**Quotes-parts, Consommations** :

| URL | Vue | Description |
|-----|-----|-------------|
| `/app/cles/<pk>/quotesparts/creer/` | `quotepart_create_view` | Nouvelle quote-part (modal) |
| `/app/quotesparts/<pk>/modifier/` | `quotepart_edit_view` | Modifier quote-part (modal) |
| `/app/quotesparts/<pk>/supprimer/` | `quotepart_delete_view` | Supprimer quote-part (modal) |
| `/app/immeubles/<pk>/consommations/creer/` | `consommation_create_view` | Nouveau releve (modal) |
| `/app/consommations/<pk>/modifier/` | `consommation_edit_view` | Modifier releve (modal) |
| `/app/consommations/<pk>/supprimer/` | `consommation_delete_view` | Supprimer releve (modal) |

**Regularisations, Ajustements** :

| URL | Vue | Description |
|-----|-----|-------------|
| `/app/baux/<pk>/regularisations/creer/` | `regularisation_create_view` | Nouvelle regularisation (modal) |
| `/app/regularisations/<pk>/modifier/` | `regularisation_edit_view` | Modifier regularisation (modal) |
| `/app/regularisations/<pk>/supprimer/` | `regularisation_delete_view` | Supprimer regularisation (modal) |
| `/app/baux/<pk>/ajustements/creer/` | `ajustement_create_view` | Nouvel ajustement (modal) |
| `/app/ajustements/<pk>/modifier/` | `ajustement_edit_view` | Modifier ajustement (modal) |
| `/app/ajustements/<pk>/supprimer/` | `ajustement_delete_view` | Supprimer ajustement (modal) |

**Patrimoine** :

| URL | Vue | Description |
|-----|-----|-------------|
| `/app/patrimoine/` | `patrimoine_dashboard_view` | Dashboard patrimoine (graphiques) |
| `/app/immeubles/<pk>/fiscal/` | `bilan_fiscal_view` | Bilan fiscal annuel |

**Calculateurs reutilises dans les vues** :
- `PatrimoineCalculator` : `get_valeur_actuelle()`, `get_capital_restant_du()`, `get_valeur_nette()`, `get_plus_value_latente()`
- `RentabiliteCalculator` : `get_rendement_brut()`, `get_rendement_net()`, `get_cashflow_mensuel()`, `get_charges_annuelles()`, `get_interets_annuels()`
- `RatiosCalculator` : `get_taux_occupation()`
- `FiscaliteCalculator` : `generer_bilan_fiscal()` (revenus, charges deductibles, resultat foncier)

### 11.4 Templates et Composants

**`base.html`** - Layout principal :
- Sidebar fixe (desktop) / hamburger menu (mobile)
- Liste des immeubles dans la sidebar (via context processor `navigation_context`)
- Lien patrimoine dans la sidebar
- Barre superieure avec titre de page
- Zone de messages Django (success, error, warning)
- Modal container (`<dialog>`) avec gestion auto ouverture/fermeture
- CSRF token injecte dans les headers HTMX

**`_modal_form.html`** - Template modal generique :
- Titre dynamique
- Rendu formulaire avec classes Tailwind
- Boutons Annuler / Sauvegarder
- Utilise `hx-post` pour soumission AJAX

**`_modal_confirm_delete.html`** - Confirmation suppression :
- Message d'alerte
- Boutons Annuler / Confirmer (rouge)

**`dashboard/index.html`** - Dashboard portfolio :
- 4 cartes KPI : valeur patrimoine, CRD, valeur nette, cashflow
- Bouton "Ajouter une depense" (acces rapide)
- Grille de cartes immeubles cliquables (rendement, cashflow, taux occupation)
- Badge couleur pour taux d'occupation (vert >= 80%, jaune >= 50%, rouge < 50%)

**`immeubles/detail.html`** - Vue detaillee immeuble :
- KPIs immeuble en haut (valeur, valeur nette, rendement, cashflow)
- Barre d'onglets HTMX (5 onglets, chargement partiel sans rechargement)
- Boutons modifier/supprimer immeuble

**`baux/detail.html`** - Vue detaillee bail :
- Informations bail et locataire principal
- Barre d'onglets HTMX (4 onglets)
- Lien retour vers l'immeuble

**`patrimoine/dashboard.html`** - Dashboard patrimoine :
- KPIs (valeur totale, CRD, valeur nette, cashflow)
- Graphique camembert repartition valeur (Chart.js)
- Graphique courbes projection 10 ans (Chart.js)
- Tableau detail par immeuble avec lien bilan fiscal

**`patrimoine/bilan_fiscal.html`** - Bilan fiscal :
- Selecteur d'annee fiscale
- KPIs (revenus bruts, charges deductibles, resultat foncier, deficit)
- Detail credits et interets
- Detail charges par type
- Recap declaration 2044

**`charges/cle_detail.html`** - Detail cle repartition :
- Infos cle (mode, prix unitaire, total tantiemes)
- Tableau quotes-parts par local avec pourcentages
- CRUD quotes-parts

**Design responsive** :
- Toutes les listes ont une vue mobile (cartes `lg:hidden`) et une vue desktop (tableau `hidden lg:block`)

### 11.5 Patterns HTMX

**Onglets dynamiques** :
```html
<button hx-get="/app/immeubles/1/tab/locaux/"
        hx-target="#tab-content"
        hx-swap="innerHTML">
    Locaux
</button>
<div id="tab-content"><!-- Contenu charge dynamiquement --></div>
```

**Modal CRUD** :
```html
<!-- Bouton ouvre la modal -->
<button hx-get="/app/immeubles/1/locaux/creer/"
        hx-target="#modal-content"
        hx-swap="innerHTML">
    Ajouter un local
</button>

<!-- Container modal dans base.html -->
<dialog id="modal">
    <div id="modal-content"></div>
</dialog>
```

La vue retourne `_modal_form.html` (GET) ou HTTP 204 avec headers (POST) :
```python
def _modal_success():
    response = HttpResponse(status=204)
    response['HX-Trigger'] = 'closeModal'
    response['HX-Refresh'] = 'true'
    return response
```

**Filtres templates** (`app_filters.py`) :
- `{{ valeur|euro }}` → `1 234,56 EUR`
- `{{ taux|pct }}` → `5,25 %`

### 11.6 Formulaires (ModelForms)

**Fichier** : `core/forms.py` (14 formulaires)

**Decorateur `_apply_css`** : Applique automatiquement les classes Tailwind a tous les widgets d'un formulaire.

```python
def _apply_css(form_class):
    """Applique les classes CSS Tailwind a tous les widgets."""
    # Ajoute INPUT_CLASS a chaque champ sans classe existante
```

**Liste des formulaires** :

| Formulaire | Modele | Particularites |
|-----------|--------|----------------|
| `DepenseQuickForm` | Depense | Classes mobile-first, champs optionnels |
| `ImmeubleForm` | Immeuble | 10 champs, dates avec `type=date` |
| `LocalForm` | Local | 5 champs |
| `BailForm` | Bail | 9 champs, date_fin optionnelle |
| `BailTarificationForm` | BailTarification | 10 champs, notes en textarea |
| `OccupantForm` | Occupant | 6 champs, email/tel optionnels |
| `EstimationValeurForm` | EstimationValeur | 5 champs |
| `CreditImmobilierForm` | CreditImmobilier | 9 champs, step precis pour taux |
| `DepenseForm` | Depense | Kwarg `immeuble` filtre les cles |
| `CleRepartitionForm` | CleRepartition | 4 champs, prix_unitaire optionnel |
| `QuotePartForm` | QuotePart | Kwarg `cle` filtre les locaux |
| `ConsommationForm` | Consommation | Kwarg `immeuble` filtre locaux et cles |
| `RegularisationForm` | Regularisation | 9 champs, date_paiement optionnelle |
| `AjustementForm` | Ajustement | 4 champs |

**Pattern kwarg pour filtrage queryset** :
```python
@_apply_css
class DepenseForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        immeuble = kwargs.pop('immeuble', None)
        super().__init__(*args, **kwargs)
        if immeuble:
            self.fields['cle_repartition'].queryset = CleRepartition.objects.filter(immeuble=immeuble)
```

### 11.7 CRUD Modal Pattern

**Pattern complet pour une entite** (exemple : Depense) :

**1. URL** (`urls_app.py`) :
```python
path('immeubles/<int:immeuble_pk>/depenses/creer/', views_app.depense_create_view, name='app_depense_create'),
path('depenses/<int:pk>/modifier/', views_app.depense_edit_view, name='app_depense_edit'),
path('depenses/<int:pk>/supprimer/', views_app.depense_delete_view, name='app_depense_delete'),
```

**2. Vue** (`views_app.py`) :
```python
@login_required
def depense_create_view(request, immeuble_pk):
    immeuble = get_object_or_404(Immeuble, pk=immeuble_pk)
    action_url = f'/app/immeubles/{immeuble_pk}/depenses/creer/'
    if request.method == 'POST':
        form = DepenseForm(request.POST, immeuble=immeuble)
        if form.is_valid():
            form.save()
            return _modal_success()  # HTTP 204 + HX-Trigger: closeModal
    else:
        form = DepenseForm(initial={'immeuble': immeuble, 'date': date.today()}, immeuble=immeuble)
    form.fields['immeuble'].widget = django_forms.HiddenInput()  # Masquer FK parent
    return _modal_form_response(request, form, 'Nouvelle depense', action_url)
```

**3. Template** (`_modal_form.html`) : Template generique reutilise par toutes les vues create/edit.

**4. Bouton dans le template onglet** :
```html
<button hx-get="{% url 'app_depense_create' immeuble_pk=immeuble.pk %}"
        hx-target="#modal-content" hx-swap="innerHTML"
        class="...">
    Nouvelle depense
</button>
```

**Helpers internes** :
- `_modal_form_response(request, form, title, action_url)` : Rend le template modal avec le formulaire
- `_modal_success()` : Retourne HTTP 204 avec `HX-Trigger: closeModal` et `HX-Refresh: true`
- `_modal_delete_response(request, obj, title, action_url)` : Rend le template de confirmation de suppression

### 11.8 Pages Patrimoine

**Dashboard Patrimoine** (`/app/patrimoine/`) :
- Reutilise `PatrimoineCalculator` et `RentabiliteCalculator`
- KPIs : valeur totale, CRD, valeur nette, cashflow mensuel
- Graphique camembert : repartition valeur par immeuble (Chart.js)
- Graphique courbes : projection 10 ans valeur / CRD / valeur nette (Chart.js)
- Tableau par immeuble : rendement, cashflow, taux occupation, lien bilan fiscal

**Bilan Fiscal** (`/app/immeubles/<pk>/fiscal/`) :
- Reutilise `FiscaliteCalculator.generer_bilan_fiscal()`
- Selecteur annee fiscale (dernier/precedent/etc.)
- KPIs : revenus bruts, charges deductibles, resultat foncier, deficit reportable
- Detail par credit : interets, assurance
- Detail charges par type (travaux, assurance PNO, taxe fonciere, etc.)
- Recap declaration 2044

### 11.9 Phases d'implementation (toutes terminees)

| Phase | Description | Statut |
|-------|-------------|--------|
| Phase 0 | Fondation (branche, squelette, login, layout) | Termine |
| Phase 1 | Dashboard avec vraies donnees + depense rapide | Termine |
| Phase 2 | Vue detaillee immeuble (onglets HTMX) | Termine |
| Phase 3 | Vue detaillee bail + generation PDF | Termine |
| Phase 4 | CRUD via modals HTMX (tous les modeles principaux) | Termine |
| Phase 5 | Migration vues patrimoine (dashboard, bilan fiscal) | Termine |
| Phase 6 | Gestion charges + CRUD avance (7 modeles supplementaires) | Termine |
| Phase 7 | Polish (onglet consommations, cleanup) | Termine |

---

## 12. Évolutions Futures

### 12.1 Améliorations Techniques

#### Stockage de Fichiers

**Besoin** : Archiver les scans de factures, contrats de bail, états des lieux

**Implémentation** :
```python
# Dans models.py - Depense
class Depense(models.Model):
    # ... champs existants ...
    document_scan = models.FileField(
        upload_to='factures/%Y/%m/',
        null=True,
        blank=True,
        verbose_name="Scan de la facture"
    )
```

**Configuration** :
```python
# Dans settings.py
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')
MEDIA_URL = '/media/'

# Dans urls.py (développement)
from django.conf import settings
from django.conf.urls.static import static

urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
```

**Note** : Préparé dans le modèle mais actuellement commenté.

#### Génération PDF Asynchrone (Celery)

**Besoin** : Si le volume de PDFs augmente (ex: génération groupée de 50 quittances)

**Stack** :
- Celery + Redis (broker)
- Tâche asynchrone : `generate_quittances.delay(bail_ids)`
- Notification utilisateur par email quand terminé

**Exemple** :
```python
# Dans tasks.py
from celery import shared_task

@shared_task
def generate_multiple_quittances(bail_ids):
    for bail_id in bail_ids:
        bail = Bail.objects.get(pk=bail_id)
        # Générer PDF...
        # Envoyer par email...
```

#### Migration PostgreSQL

**Quand** : Si plus de 100 baux ou utilisation multi-utilisateurs

**Avantages** :
- Transactions ACID robustes
- Locks concurrents (plusieurs utilisateurs simultanés)
- Performance sur gros volumes

**Migration** :
```bash
# 1. Dump SQLite
python manage.py dumpdata > data.json

# 2. Configurer PostgreSQL dans settings.py
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'gestion_locative',
        'USER': 'postgres',
        'PASSWORD': 'xxx',
        'HOST': 'localhost',
        'PORT': '5432',
    }
}

# 3. Recréer structure
python manage.py migrate

# 4. Importer données
python manage.py loaddata data.json
```

### 12.2 Nouvelles Fonctionnalités

#### Envoi Automatique par Email

**Besoin** : Envoyer automatiquement les quittances aux locataires

**Implémentation** :
```python
from django.core.mail import EmailMessage

def envoyer_quittance_email(bail, pdf_content):
    locataire = bail.occupants.filter(role='LOCATAIRE').first()

    if locataire and locataire.email:
        email = EmailMessage(
            subject=f"Quittance de loyer - {bail.local.numero_porte}",
            body=f"Bonjour {locataire.prenom},\n\nVeuillez trouver ci-joint votre quittance de loyer.",
            from_email='gestion@example.com',
            to=[locataire.email]
        )
        email.attach('quittance.pdf', pdf_content, 'application/pdf')
        email.send()
```

**Configuration** :
```python
# Dans settings.py
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = 'votre-email@gmail.com'
EMAIL_HOST_PASSWORD = 'votre-mot-de-passe'
```

**Action Admin** :
```python
@admin.action(description='Générer et envoyer quittances par email')
def generer_et_envoyer_quittances(self, request, queryset):
    for bail in queryset:
        pdf = generer_quittance_pdf_bytes(bail)  # Version modifiée
        envoyer_quittance_email(bail, pdf)
    self.message_user(request, f'{queryset.count()} quittances envoyées.')
```

#### Révision Groupée des Loyers

**Besoin** : Appliquer la révision IRL sur tous les baux actifs en une seule action

**Implémentation** :
```python
@admin.action(description='Révision IRL groupée (tous les baux)')
def revision_irl_groupee(self, request, queryset):
    # 1. Formulaire pour saisir nouvel indice
    if request.method != 'POST':
        return render(request, 'admin/revision_groupee_form.html')

    nouvel_indice = float(request.POST.get('nouvel_indice'))
    nouveau_trimestre = request.POST.get('nouveau_trimestre')
    date_application = request.POST.get('date_application')

    # 2. Pour chaque bail
    for bail in queryset:
        tarif_actuel = bail.tarification_actuelle

        if tarif_actuel.indice_reference:
            nouveau_loyer = float(tarif_actuel.loyer_hc) * (nouvel_indice / float(tarif_actuel.indice_reference))

            # Fermer ancienne
            tarif_actuel.date_fin = date_application - timedelta(days=1)
            tarif_actuel.save()

            # Créer nouvelle
            BailTarification.objects.create(
                bail=bail,
                date_debut=date_application,
                date_fin=None,
                loyer_hc=round(nouveau_loyer, 2),
                charges=tarif_actuel.charges,
                taxes=tarif_actuel.taxes,
                indice_reference=nouvel_indice,
                trimestre_reference=nouveau_trimestre,
                reason=f"Révision groupée IRL {nouveau_trimestre}"
            )

    self.message_user(request, f'{queryset.count()} loyers révisés.')
```

**⚠️ Note** : Nécessite validation manuelle avant application !

#### Tableau de Bord Propriétaire

**Besoin** : Vue d'ensemble financière

**Métriques à afficher** :
- Total loyers mensuels
- Taux d'occupation (locaux occupés / total)
- Régularisations en attente de paiement
- Prochaines échéances de révision IRL
- Graphique évolution loyers (historique)

**Implémentation** : Vue Django personnalisée ou extension Jazzmin Dashboard

#### Application Mobile Locataire

**Besoin** : Consultation autonome par le locataire

**Fonctionnalités** :
- Consultation quittances (PDF)
- Historique des paiements
- Solde de charges
- Déclaration d'incident (ticket)

**Stack** : React Native + API REST (à développer)

**Endpoints à créer** :
```python
GET /api/locataires/me/quittances/
GET /api/locataires/me/solde/
POST /api/locataires/me/incidents/
```

**Note** : Nécessiterait le développement d'une API REST dédiée avec authentification locataire.

### 12.3 Optimisations

#### Cache des Calculs de Régularisation

**Problème** : Calcul complexe refait à chaque affichage

**Solution** : Cacher le résultat dans le modèle Regularisation

```python
class Regularisation(models.Model):
    # ... champs existants ...
    calcul_cache = models.JSONField(null=True, blank=True)

    def recalculer(self):
        # Exécuter calcul complexe
        resultat = calculer_regularisation(self.bail, self.date_debut, self.date_fin)
        self.calcul_cache = resultat
        self.save()
```

#### Index Base de Données

**Si performances dégradées** :

```python
class BailTarification(models.Model):
    class Meta:
        indexes = [
            models.Index(fields=['bail', 'date_debut']),
            models.Index(fields=['bail', 'date_fin']),
        ]
```

### 12.4 Sécurité

#### Authentification à Deux Facteurs (2FA)

**Package** : `django-otp`

```bash
pip install django-otp qrcode
```

**Configuration** :
```python
INSTALLED_APPS += [
    'django_otp',
    'django_otp.plugins.otp_totp',
]

MIDDLEWARE += [
    'django_otp.middleware.OTPMiddleware',
]
```

#### Logs d'Audit

**Tracer toutes les modifications** :

```python
# Package : django-auditlog
pip install django-auditlog

# Configuration
INSTALLED_APPS += ['auditlog']

# Dans models.py
from auditlog.registry import auditlog

auditlog.register(Bail)
auditlog.register(BailTarification)
auditlog.register(Regularisation)
```

**Résultat** : Historique complet des modifications (qui, quand, quoi).

---

## Contact et Support

**Fichiers clés pour intervention** :
- `core/models.py` - Modèles de données et logique métier
- `core/views.py` - Vues, fonctions PDF et formulaires
- `core/pdf_generator.py` - Générateur de PDFs
- `core/calculators.py` - Calculateurs métier
- `core/admin.py` - Configuration interface admin
- `core/migrations/` - Historique base de données

**Commandes de diagnostic** :
```bash
python manage.py check              # Vérifier intégrité
python manage.py showmigrations     # État migrations
python manage.py shell              # Console interactive
```

**En cas de problème grave** :
1. Restaurer backup
2. Vérifier logs Django
3. Utiliser `python manage.py shell` pour debug interactif
4. Consulter cette documentation

---

**Document maintenu par** : Équipe de développement
**Dernière révision** : Février 2026 (v3.0 - Interface Custom)
