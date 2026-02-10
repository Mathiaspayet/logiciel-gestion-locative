# Quick Start Guide - Pour Développeurs / IA

**Objectif** : Reprendre le projet rapidement et comprendre l'essentiel en 10 minutes.

---

## 🎯 Contexte du Projet

**Quoi** : Application de gestion locative professionnelle pour propriétaires français.

**Stack** : Django 6.0 + Python 3.14 + SQLite + ReportLab + HTMX + Tailwind CSS

**Utilisateurs** : Propriétaires/Gestionnaires immobiliers (SCI, particuliers)

**Fonctionnalites Cles** :
- **Interface custom complete** (v3.0) - Navigation centree sur les biens, CRUD complet pour 13 modeles (HTMX + Tailwind + Chart.js)
- Dashboard portfolio avec KPIs et cartes immeubles
- Dashboard patrimoine avec graphiques et projection 10 ans
- Bilan fiscal annuel par immeuble (declaration 2044)
- Generation documents PDF (quittances, regularisations, avis d'echeance)
- **Historique tarifaire complet** (v2.0) - changements loyers/charges traces
- Regularisation charges au prorata temporis
- Revision loyers IRL/ILC
- **Assistant Credit Immobilier** - Calcul automatique des donnees manquantes

---

## 🚀 Installation (5 minutes)

### Windows

```bash
# 1. Cloner/Télécharger le projet
cd "D:\...\logiciel gestion locative"

# 2. Lancer l'installation (créé venv + installe dépendances)
1_INSTALLATION.bat

# 3. Lancer le serveur
3_LANCER_LOGICIEL.bat

# 4. Accéder à l'interface
http://127.0.0.1:8000/app/    # Interface custom
# ou http://127.0.0.1:8000/admin/  # Admin legacy
```

### Linux/Mac

```bash
# 1. Créer environnement virtuel
python3 -m venv venv
source venv/bin/activate

# 2. Installer dépendances
pip install -r requirements.txt

# 3. Appliquer migrations
cd gestion_locative
python manage.py migrate

# 4. Créer super-utilisateur
python manage.py createsuperuser

# 5. Lancer serveur
python manage.py runserver

# 6. Accéder à l'interface
http://127.0.0.1:8000/app/    # Interface custom
# ou http://127.0.0.1:8000/admin/  # Admin legacy
```

---

## 📁 Structure du Projet (Fichiers Importants)

```
gestion_locative/
├── core/
│   ├── models.py          # 18 modeles (Bail, BailTarification, CreditImmobilier...)
│   ├── views.py           # Vues generation documents PDF + dashboards admin
│   ├── views_app.py       # ~50 vues interface custom (/app/) - CRUD, onglets, patrimoine
│   ├── urls_app.py        # 88 routes interface custom
│   ├── forms.py           # 14 ModelForms (CRUD tous les modeles)
│   ├── context_processors.py # Navigation sidebar (liste immeubles)
│   ├── templatetags/app_filters.py # Filtres |euro, |pct
│   ├── pdf_generator.py   # Classe PDFGenerator
│   ├── calculators.py     # Logique metier baux (BailCalculator)
│   ├── patrimoine_calculators.py  # Patrimoine, rentabilite, fiscalite
│   ├── exceptions.py      # TarificationNotFoundError, etc.
│   ├── admin.py           # 16+ classes admin + actions
│   ├── urls.py            # Routes admin/PDF (11 endpoints)
│   ├── templates/app/     # 20 templates interface custom (Tailwind + HTMX)
│   └── migrations/        # Historique BDD (0011-0017 importants)
├── gestion_locative/
│   └── settings.py        # Configuration Django
├── db.sqlite3             # Base de donnees SQLite
├── README.md              # Doc utilisateur
├── DOCUMENTATION_TECHNIQUE.md  # Doc complete (LIRE EN PRIORITE)
├── CHANGELOG.md           # Historique des modifications
└── QUICK_START.md         # Ce fichier
```

---

## 🧠 Concepts Clés à Comprendre

### 1. Système d'Historique Tarifaire (v2.0) ⭐ CRUCIAL

**Problème résolu** :
- Avant : Modifier `bail.loyer_hc` écrasait l'ancien montant → perte historique
- Maintenant : Chaque changement crée une `BailTarification` avec dates début/fin

**Modèle BailTarification** :
```python
class BailTarification(models.Model):
    bail = ForeignKey(Bail)
    date_debut = DateField       # Début validité
    date_fin = DateField (null)  # None = encore active
    loyer_hc = DecimalField
    charges = DecimalField
    taxes = DecimalField
    reason = CharField           # Motif du changement
```

**Backward Compatibility** :
```python
# bail.loyer_hc n'existe plus en BDD (supprimé migration 0014)
# Mais fonctionne via property :
@property
def loyer_hc(self):
    tarif = self.tarification_actuelle  # Tarif actif aujourd'hui
    return tarif.loyer_hc if tarif else 0
```

**Utilisation dans les PDFs** :
```python
# Au lieu de :
montant = bail.loyer_hc  # ❌ Utiliserait toujours le tarif actuel

# On fait :
tarif = bail.get_tarification_at(date_quittance)  # ✅ Tarif historique
montant = tarif.loyer_hc
```

### 2. Génération PDF avec ReportLab

**Pattern** :
```python
def generer_xxx_pdf(request, pk):
    bail = Bail.objects.get(pk=pk)

    # 1. Formulaire (GET)
    if request.method != 'POST':
        return HttpResponse(html_form)

    # 2. Récupérer tarification historique
    tarif = bail.get_tarification_at(target_date)
    if not tarif:
        return HttpResponse("ERREUR: Aucune tarification", status=400)

    # 3. Génération PDF
    response = HttpResponse(content_type='application/pdf')
    p = canvas.Canvas(response, pagesize=A4)
    p.drawString(2*cm, 27*cm, "TITRE")
    p.showPage()
    p.save()
    return response
```

**Pourquoi ReportLab ?**
- Rapide, portable, aucune dépendance externe
- Positionnement pixel-perfect

### 3. Régularisation de Charges (Complexe) ⚠️

**Calcul mois par mois** avec tarifs historiques :

```python
# Exemple : Charges changent de 30€ → 35€ au 01/07/2025
# Période régul : 01/01/2025 - 31/12/2025

total_provisions = 0.0
for mois in range(1, 13):
    curr = date(2025, mois, 1)
    tarif_mois = bail.get_tarification_at(curr)  # Tarif du 1er du mois

    # Janvier-Juin : 6 × 30€ = 180€
    # Juillet-Décembre : 6 × 35€ = 210€
    total_provisions += tarif_mois.charges

# Total = 390€ (et non 360€ ou 420€)
```

**Fichier** : `views.py` lignes 937-986

### 4. Révision de Loyer IRL/ILC

**Workflow en 2 étapes** (contrôle manuel total) :

**Étape 1** : Calcul (`generer_revision_loyer_pdf`)
```python
nouveau_loyer = ancien_loyer * (nouvel_indice / ancien_indice)

# Stocker dans session (pas de mise à jour auto !)
request.session['nouvelle_tarification'] = {...}
return redirect('creer_tarification_from_revision')
```

**Étape 2** : Validation (`creer_tarification_from_revision`)
```python
# Formulaire pré-rempli → Utilisateur valide manuellement
# Puis :
# 1. Fermer ancienne tarification
# 2. Créer nouvelle tarification
# 3. Générer PDF notification locataire
```

**Aucune mise à jour automatique** → Contrôle total utilisateur

---

## 🔍 Scénarios d'Usage Typiques

### Scenario 1 : Navigation quotidienne (interface custom)

```
/app/ → Dashboard portfolio (KPIs globaux + cartes immeubles)
→ Cliquer sur un immeuble → Vue detaillee (5 onglets)
→ Onglet Locaux → Cliquer sur un bail → Vue detaillee bail (4 onglets)
→ Onglet Documents → Generer quittance PDF
```

**Code implique** : `views_app.py` (dashboard_view, immeuble_detail_view, bail_detail_view)

### Scenario 2 : Ajouter une depense rapidement

```
/app/depenses/ajouter/ (ou bouton dans sidebar)
→ Remplir : Bien, Montant, Description, Date
→ Options avancees : Cle repartition, Periode
→ Enregistrer → Confirmation
```

**Code implique** : `views_app.py::depense_quick_add_view`, `forms.py::DepenseQuickForm`

### Scenario 3 : CRUD via modal (exemple : ajouter un local)

```
/app/immeubles/1/ → Onglet Locaux → Bouton "Nouveau local"
→ Modal s'ouvre avec formulaire
→ Remplir et sauvegarder → Modal se ferme, page rafraichie
```

**Code implique** : `views_app.py::local_create_view`, `forms.py::LocalForm`

### Scenario 4 : Generer une Quittance (via admin legacy)

```
/admin/ → Baux → Selectionner bail → Action "Telecharger quittance PDF"
→ Formulaire : Selectionner periodes
→ Cliquer "Generer"
→ PDF telecharge
```

**Code implique** : `views.py::generer_quittance_pdf`

### Scenario 5 : Consulter le bilan fiscal

```
/app/patrimoine/ → Dashboard patrimoine (graphiques, KPIs)
→ Cliquer "Bilan fiscal" sur un immeuble
→ Selecteur annee → Revenus, Charges deductibles, Resultat foncier
```

**Code implique** : `views_app.py::bilan_fiscal_view`, `patrimoine_calculators.py::FiscaliteCalculator`

---

## 🗂️ Glossaire des Termes Métier

| Terme | Définition |
|-------|------------|
| **IRL** | Indice de Référence des Loyers (publié par l'INSEE) - Logements vides |
| **ILC** | Indice des Loyers Commerciaux - Baux commerciaux |
| **Régularisation de charges** | Ajustement annuel : Charges réelles - Provisions versées |
| **Prorata temporis** | Au prorata du temps (calcul proportionnel aux jours) |
| **Tantièmes** | Quote-part d'un local dans les charges (ex: 100/1000) |
| **Loyer HC** | Loyer Hors Charges |
| **Provisions sur charges** | Avances mensuelles/trimestrielles pour charges (régularisées annuellement) |
| **Forfait de charges** | Charges fixes, pas de régularisation |
| **Quittance** | Reçu attestant du paiement du loyer |
| **Avis d'échéance** | Appel de loyer (avant paiement) |
| **Solde de tout compte** | Arrêté de compte en fin de bail |
| **Dépôt de garantie** | Caution versée par le locataire (max 1 ou 2 mois selon type bail) |
| **Clé de répartition** | Méthode de calcul pour répartir une charge (tantièmes, consommation, surface) |

---

## 🛠️ Commandes Utiles

```bash
# Créer des migrations après modification models.py
python manage.py makemigrations core

# Appliquer migrations
python manage.py migrate

# Shell interactif (debug)
python manage.py shell

# Vérifier intégrité projet
python manage.py check

# Voir état migrations
python manage.py showmigrations core

# Rollback migration
python manage.py migrate core 0013

# Créer super-utilisateur
python manage.py createsuperuser

# Collecter fichiers statiques (production)
python manage.py collectstatic
```

---

## 🔴 Points d'Attention Critiques

### 1. TOUJOURS Faire un Backup Avant Migration

```bash
cp gestion_locative/db.sqlite3 backups/db_backup_$(date +%Y%m%d).sqlite3
```

**Migrations irréversibles** :
- Migration 0014 (suppression champs) → Impossible de revenir sans backup

### 2. Continuité des Tarifications

⚠️ **ERREUR FRÉQUENTE** :
```
Tarif 1 : 01/01/2022 - 30/06/2024
Tarif 2 : 01/09/2024 - NULL
         ↑
    Trou de 2 mois !
```

**Conséquence** : Erreur lors génération PDF pour dates dans le trou.

**Solution** : Vérifier continuité avec script (section 8.2 DOCUMENTATION_TECHNIQUE.md)

### 3. Une Seule Tarification Active par Bail

✅ **BON** :
```
Tarif 1 : date_fin = 31/12/2024
Tarif 2 : date_fin = NULL  ← Seule active
```

❌ **MAUVAIS** :
```
Tarif 1 : date_fin = NULL  ← Deux actives !
Tarif 2 : date_fin = NULL  ← Conflit !
```

### 4. Prorata Temporis dans Régularisation

Le calcul **doit** être mois par mois si les charges ont changé en cours d'année.

**Fichier** : `views.py` lignes 937-986 (algorithme détaillé)

---

## 📚 Documentation Complète

Pour approfondir, consulter dans l'ordre :

1. **README.md** (5 min) - Vue d'ensemble fonctionnalités
2. **Ce fichier QUICK_START.md** (10 min) - Prise en main rapide
3. **DOCUMENTATION_TECHNIQUE.md** (30-60 min) - Tout le detail
   - Section 1-2 : Architecture & Modeles
   - Section 3 : Systeme historique tarifaire
   - Section 4 : Fonctions PDF (algorithmes)
   - Section 8 : Debugging
   - Section 9 : Assistant Credit Immobilier
   - Section 10 : Dashboards Patrimoine
   - Section 11 : Interface Custom (routes, templates, CRUD, patterns HTMX)
   - Section 12 : Evolutions futures
4. **CHANGELOG.md** - Historique des modifications

---

## 🆘 En Cas de Problème

### Erreur : "Aucune tarification définie pour XX/XX/XXXX"

**Diagnostic** :
```python
python manage.py shell

from core.models import Bail
from datetime import date

bail = Bail.objects.get(pk=1)
tarif = bail.get_tarification_at(date(2025, 6, 15))
print(tarif)  # None = pas de tarif pour cette date

# Lister toutes les tarifications
for t in bail.tarifications.all():
    print(f"{t.date_debut} → {t.date_fin or 'en cours'}")
```

**Solution** : Créer tarification ou modifier date_fin

### Erreur : Migration bloquée

```bash
# Voir état
python manage.py showmigrations core

# Rollback
python manage.py migrate core 0013

# Restaurer backup si nécessaire
cp backups/db_backup.sqlite3 gestion_locative/db.sqlite3
```

### Performance : Requêtes N+1

```python
# Mauvais
baux = Bail.objects.all()
for bail in baux:
    print(bail.loyer_hc)  # Query pour chaque bail

# Bon
baux = Bail.objects.prefetch_related('tarifications').all()
for bail in baux:
    print(bail.loyer_hc)  # Pas de query supplémentaire
```

---

## Checklist Premier Jour

- [ ] Lire README.md (vue d'ensemble)
- [ ] Lire ce QUICK_START.md
- [ ] Installer et lancer le projet en local
- [ ] Se connecter sur `/app/` (creer superuser si besoin)
- [ ] Explorer le dashboard portfolio et cliquer sur un immeuble
- [ ] Naviguer les 5 onglets immeuble et les 4 onglets bail
- [ ] Tester le CRUD modal (ajouter/modifier/supprimer une entite)
- [ ] Explorer le dashboard patrimoine et le bilan fiscal
- [ ] Lire Section 3 de DOCUMENTATION_TECHNIQUE.md (systeme historique)
- [ ] Lire Section 11 de DOCUMENTATION_TECHNIQUE.md (interface custom)
- [ ] Consulter `models.py` (Bail + BailTarification)
- [ ] Consulter `views_app.py` (vues interface custom)

**Temps estime** : 2-3 heures pour etre operationnel

---

## Conseils pour une IA

**Pour comprendre rapidement** :
1. Commencer par lire ce fichier (Quick Start)
2. Lire Section 3 de DOCUMENTATION_TECHNIQUE.md (Systeme d'historique tarifaire)
3. Lire Section 11 de DOCUMENTATION_TECHNIQUE.md (Interface custom, CRUD patterns)
4. Lire le code de `models.py` (BailTarification)
5. Regarder `views_app.py` pour comprendre le pattern CRUD modal HTMX

**Pour modifier du code** :
1. Toujours faire un backup de `db.sqlite3` d'abord
2. Verifier dans DOCUMENTATION_TECHNIQUE.md si le cas est documente
3. Utiliser `python manage.py shell` pour tester la logique
4. Creer migration si modification des modeles
5. Tester la generation PDF apres modification

**Pour ajouter une fonctionnalite** :
1. Consulter Section 12 de DOCUMENTATION_TECHNIQUE.md (Evolutions futures)
2. Suivre le pattern CRUD modal existant (Section 11.7)
3. Respecter les patterns existants (decorateur `_apply_css`, `_modal_success()`, `_modal_form_response()`)

---

**Dernière mise à jour** : Février 2026 (v3.0 - Interface Custom)
**Difficulté de prise en main** : Moyenne (Django intermédiaire requis)
**Temps pour être autonome** : 1 journée
