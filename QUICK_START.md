# Quick Start Guide - Pour Développeurs / IA

**Objectif** : Reprendre le projet rapidement et comprendre l'essentiel en 10 minutes.

---

## 🎯 Contexte du Projet

**Quoi** : Application de gestion locative professionnelle pour propriétaires français.

**Stack** : Django 6.0 + Python 3.14 + SQLite + ReportLab

**Utilisateurs** : Propriétaires/Gestionnaires immobiliers (SCI, particuliers)

**Fonctionnalités Clés** :
- Gestion patrimoine (immeubles, locaux, baux)
- Génération documents PDF (quittances, régularisations, avis d'échéance)
- **Historique tarifaire complet** (v2.0) - changements loyers/charges tracés
- Régularisation charges au prorata temporis
- Révision loyers IRL/ILC
- **Assistant Crédit Immobilier** - Calcul automatique des données manquantes

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
http://127.0.0.1:8000/admin/
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
http://127.0.0.1:8000/admin/
```

---

## 📁 Structure du Projet (Fichiers Importants)

```
gestion_locative/
├── core/
│   ├── models.py          ⭐ MODÈLES - 18 modèles (Bail, BailTarification, CreditImmobilier...)
│   ├── views.py           ⭐ VUES - Fonctions génération documents PDF + dashboards
│   ├── pdf_generator.py   📄 GÉNÉRATEUR - Classe PDFGenerator
│   ├── calculators.py     🧮 CALCULATEURS - Logique métier baux
│   ├── patrimoine_calculators.py  📊 CALCULATEURS - Patrimoine, rentabilité, crédits
│   ├── exceptions.py      ❗ EXCEPTIONS - TarificationNotFoundError, etc.
│   ├── admin.py           ⭐ ADMIN - 16+ classes admin + actions
│   ├── urls.py            🔗 Routes (11 endpoints)
│   └── migrations/        📂 Historique BDD (0011-0016 importants)
├── gestion_locative/
│   └── settings.py        ⚙️ Configuration Django
├── db.sqlite3             💾 BASE DE DONNÉES
├── README.md              📖 Doc utilisateur
├── DOCUMENTATION_TECHNIQUE.md  📚 Doc complète (LIRE EN PRIORITÉ)
├── CHANGELOG.md           📝 Historique des modifications
└── QUICK_START.md         ⚡ Ce fichier
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

### Scénario 1 : Générer une Quittance

```
Admin → Baux → Sélectionner bail → Action "Télécharger quittance PDF"
→ Formulaire : Sélectionner périodes
→ Cliquer "Générer"
→ PDF téléchargé
```

**Code impliqué** : `views.py::generer_quittance_pdf` (lignes 31-319)

### Scénario 2 : Réviser un Loyer IRL

```
Admin → Baux → Sélectionner bail → Action "Révision du Loyer"
→ Formulaire : Nouvel indice IRL, trimestre
→ Cocher "Mettre à jour le loyer"
→ Redirection vers formulaire de validation
→ Modifier si besoin, valider
→ Nouvelle tarification créée + PDF notification
```

**Code impliqué** :
- `views.py::generer_revision_loyer_pdf` (lignes 1003-1249)
- `views.py::creer_tarification_from_revision` (lignes 1460-1643)

### Scénario 3 : Calculer Régularisation Charges

```
Admin → Baux → Sélectionner bail → Action "Générer Régularisation Charges"
→ Formulaire : Année N-1, montant réel charges
→ Cocher "Enregistrer dans historique" (optionnel)
→ PDF généré avec calcul détaillé
→ Si enregistré : visible dans Admin → Régularisations
```

**Code impliqué** : `views.py::generer_regularisation_pdf` (lignes 556-1001)

### Scénario 4 : Créer une Nouvelle Tarification Manuellement

```
Admin → Tarifications → Ajouter
→ Remplir : Bail, Date début, Loyer, Charges, Taxes, Motif
→ Sauvegarder

⚠️ IMPORTANT : Fermer l'ancienne tarification
Admin → Tarifications → Sélectionner ancienne → date_fin = veille nouvelle
```

**Code impliqué** : `models.py::BailTarification.clean()` (validation)

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
3. **DOCUMENTATION_TECHNIQUE.md** (30-60 min) - Tout le détail
   - Section 1-2 : Architecture & Modèles
   - Section 3 : Système historique tarifaire
   - Section 4 : Fonctions PDF (algorithmes)
   - Section 8 : Debugging
   - Section 9 : Assistant Crédit Immobilier
   - Section 10 : Dashboards Patrimoine
   - Section 11 : Évolutions futures
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

## 🎯 Checklist Premier Jour

- [ ] Lire README.md (vue d'ensemble)
- [ ] Lire ce QUICK_START.md
- [ ] Installer et lancer le projet en local
- [ ] Se connecter à l'admin (créer superuser)
- [ ] Explorer l'interface : Baux, Tarifications, Régularisations
- [ ] Générer une quittance test
- [ ] Lire Section 3 de DOCUMENTATION_TECHNIQUE.md (système historique)
- [ ] Consulter `models.py` lignes 57-219 (Bail + BailTarification)
- [ ] Consulter `views.py` lignes 31-319 (generer_quittance_pdf)

**Temps estimé** : 2-3 heures pour être opérationnel

---

## 💡 Conseils pour une IA

**Pour comprendre rapidement** :
1. Commencer par lire ce fichier (Quick Start)
2. Lire Section 3 de DOCUMENTATION_TECHNIQUE.md (Système d'historique tarifaire)
3. Lire le code de `models.py` (BailTarification)
4. Regarder un exemple de fonction PDF (`generer_quittance_pdf`)

**Pour modifier du code** :
1. Toujours faire un backup de `db.sqlite3` d'abord
2. Vérifier dans DOCUMENTATION_TECHNIQUE.md si le cas est documenté
3. Utiliser `python manage.py shell` pour tester la logique
4. Créer migration si modification des modèles
5. Tester la génération PDF après modification

**Pour ajouter une fonctionnalité** :
1. Consulter Section 10 de DOCUMENTATION_TECHNIQUE.md (Évolutions futures)
2. Exemples de code souvent déjà fournis
3. Respecter les patterns existants (properties, validation, etc.)

---

**Dernière mise à jour** : Février 2026 (v2.1)
**Difficulté de prise en main** : Moyenne (Django intermédiaire requis)
**Temps pour être autonome** : 1 journée
