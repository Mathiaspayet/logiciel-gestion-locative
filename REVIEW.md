# Revue Complète - Logiciel de Gestion Locative

**Date :** 2026-02-06
**Périmètre :** Design, Logique métier, Fonctionnalités, Ergonomie, Fiabilité, Stabilité, Sécurité

---

## Table des matières

1. [Résumé Exécutif](#1-résumé-exécutif)
2. [Architecture & Stack Technique](#2-architecture--stack-technique)
3. [Fonctionnalités - Inventaire complet](#3-fonctionnalités---inventaire-complet)
4. [Design & Ergonomie (UI/UX)](#4-design--ergonomie-uiux)
5. [Logique Métier & Calculs](#5-logique-métier--calculs)
6. [Fiabilité & Stabilité](#6-fiabilité--stabilité)
7. [Sécurité](#7-sécurité)
8. [Synthèse & Priorisation des Corrections](#8-synthèse--priorisation-des-corrections)

---

## 1. Résumé Exécutif

### Scores par catégorie

| Catégorie | Note | Commentaire |
|-----------|------|-------------|
| **Fonctionnalités** | 9/10 | Couverture fonctionnelle très complète |
| **Design / Ergonomie** | 6.5/10 | Bonne base, manque de cohérence et d'accessibilité |
| **Logique Métier** | 6/10 | Calculs corrects dans le cas nominal, nombreux edge cases non gérés |
| **Fiabilité / Stabilité** | 5/10 | Absence de transactions atomiques, gestion d'erreurs insuffisante |
| **Sécurité** | 3/10 | Failles critiques d'authentification et de configuration |
| **Note globale** | **5.9/10** | **Application fonctionnelle mais nécessitant des corrections importantes avant mise en production** |

### Verdict

L'application offre une **couverture fonctionnelle remarquable** pour la gestion locative française (baux, quittances, régularisation de charges, suivi patrimonial, crédit, fiscalité LMNP). L'architecture Django est bien structurée et le code est lisible. Cependant, **des failles critiques de sécurité** (vues sans authentification, SECRET_KEY en clair, DEBUG=True) et **des problèmes de fiabilité** (absence de transactions atomiques, calculs en float au lieu de Decimal) doivent être corrigés avant toute mise en production.

---

## 2. Architecture & Stack Technique

### Stack

| Composant | Technologie |
|-----------|-------------|
| Backend | Django 6.0 (Python 3.14+) |
| Base de données | SQLite (dev) / PostgreSQL (prod) |
| Interface | Django Admin + Jazzmin 3.0.1 |
| PDF | ReportLab |
| Conteneurisation | Docker + Docker Compose |
| Authentification | Django Auth (sessions) |

### Structure du projet

```
gestion_locative/
├── core/
│   ├── models.py              (677 lignes - 18 modèles)
│   ├── views.py               (1067 lignes - 12 vues)
│   ├── admin.py               (740 lignes - 16+ classes admin)
│   ├── pdf_generator.py       (895 lignes - génération PDF)
│   ├── calculators.py         (239 lignes - calculs facturation)
│   ├── patrimoine_calculators.py (542 lignes - calculs patrimoniaux)
│   ├── exceptions.py          (47 lignes - exceptions métier)
│   ├── templates/             (10 templates HTML)
│   └── migrations/            (16 migrations)
├── gestion_locative/
│   ├── settings.py            (329 lignes)
│   └── urls.py
└── db.sqlite3
```

### Observations architecture

**Points forts :**
- Architecture monolithique adaptée au périmètre fonctionnel
- Séparation claire : modèles / vues / calculateurs / générateur PDF
- Système d'historisation des tarifications (BailTarification) bien conçu
- Support Docker pour le déploiement

**Points faibles :**
- Aucun test unitaire ou d'intégration détecté
- Pas de fichier `.env` pour les variables sensibles
- Pas d'API REST formalisée (pas de sérialiseurs, pas de DRF)
- Couplage fort entre vues et logique métier (pas de couche service)

---

## 3. Fonctionnalités - Inventaire complet

### 3.1 Gestion locative de base

| Fonctionnalité | Status | Détail |
|----------------|--------|--------|
| Gestion des propriétaires | OK | Particulier/Société, adresse complète |
| Gestion des immeubles | OK | Rattachement propriétaire, données acquisition, régime fiscal (5 types) |
| Gestion des locaux | OK | 4 types (appart, commerce, parking, bureau), surface m² |
| Gestion des baux | OK | Fréquence mensuelle/trimestrielle, TVA, dépôt de garantie |
| Gestion des occupants | OK | Locataires et garants, contact complet |
| Historique des tarifications | OK | Système complet avec périodes, audit trail, raison du changement |

### 3.2 Documents PDF (5 types)

| Document | Status | Détail |
|----------|--------|--------|
| Quittance de loyer | OK | Multi-période, génération en lot (ZIP), détail mensuel |
| Avis d'échéance | OK | Préavis de paiement avec ventilation |
| Régularisation de charges | OK | Calcul mois par mois, prorata, enregistrement historique |
| Solde de tout compte | OK | Prorata loyer, retenues, restitution dépôt garantie |
| Révision de loyer (IRL/ILC) | OK | Récupération indices INSEE, calcul automatique, création tarification |

### 3.3 Système de charges

| Fonctionnalité | Status | Détail |
|----------------|--------|--------|
| Clés de répartition | OK | Par tantièmes ou consommation |
| Quote-parts | OK | Attribution par local et clé |
| Dépenses | OK | Avec période de validité optionnelle |
| Relevés de consommation | OK | Index début/fin, calcul quantité |
| Ajustements manuels | OK | Positifs ou négatifs sur un bail |

### 3.4 Gestion patrimoniale

| Fonctionnalité | Status | Détail |
|----------------|--------|--------|
| Estimations de valeur | OK | Sources multiples (manuelle, agent, notaire, DVF) |
| Crédits immobiliers | OK | Amortissable/In Fine, échéancier complet |
| Charges fiscales | OK | 9 types de charges déductibles, justificatifs |
| Amortissements (LMNP) | OK | 3 types de biens, calcul VNC |
| Vacances locatives | OK | Motif, durée, statut en cours/terminé |

### 3.5 Tableaux de bord (3 dashboards)

| Dashboard | Status | Indicateurs |
|-----------|--------|-------------|
| Portfolio global | OK | Valeur totale, dette, valeur nette, cash-flow, projection 10 ans |
| Détail immeuble | OK | 30+ indicateurs (patrimoine, revenus, rentabilité, charges, crédits, occupation) |
| Bilan fiscal | OK | Revenus/charges par année, détail par type, par crédit |

### 3.6 Outils avancés

| Outil | Status | Détail |
|-------|--------|--------|
| Assistant crédit | OK | 3 modes de calcul, génération échéancier automatique |
| Génération ZIP en lot | OK | Quittances multiples en une action |
| Vérification continuité tarifications | OK | Détection des trous dans l'historique |
| Récupération indices INSEE | OK | IRL et ILC automatiques (avec fallback manuel) |

### Fonctionnalités manquantes identifiées

- Pas d'export CSV/Excel des données
- Pas de système de notifications (loyers impayés, échéances crédit)
- Pas de gestion des documents/pièces jointes (hors justificatifs fiscaux)
- Pas de rapports personnalisables
- Pas de multi-utilisateur avec permissions granulaires
- Pas de journalisation des actions utilisateur (audit log)

---

## 4. Design & Ergonomie (UI/UX)

### 4.1 Navigation

**Points forts :**
- Menu sidebar Jazzmin bien organisé avec icônes Font Awesome
- Hiérarchie logique : Propriétaire → Immeuble → Local → Bail
- Liens rapides vers dashboards et assistant crédit dans la navigation
- Fil d'Ariane (date hierarchy) sur les listes clés

**Points faibles :**
- Navigation profonde : accéder aux charges nécessite plusieurs clics
- Pas de recherche globale rapide
- Pas d'accès rapide aux éléments récents ou favoris
- Pas de navigation mobile optimisée (sidebar uniquement)

### 4.2 Formulaires

**Assistant crédit** (`assistant_credit.html`, 895 lignes) : **Excellent**
- Système de badges colorés indiquant l'état des champs (calculé/requis/optionnel)
- Validation en temps réel avec messages de statut
- Légende explicative des couleurs
- 3 modes de calcul avec auto-détection

**Formulaires PDF** : **Bon**
- Sections claires avec en-têtes
- Aide contextuelle sur les champs sensibles
- Sélection par cases à cocher pour les périodes

**Admin Django** : **Moyen**
- 5 inlines sur la page Bail (peut surcharger l'interface)
- Pas d'indication visuelle champs obligatoires vs optionnels
- BailTarificationInline avec 9 colonnes (scroll horizontal sur mobile)

### 4.3 Dashboards

**Portfolio global** (`dashboard_patrimoine.html`) : **Excellent** (9/10)
- Cartes résumé en haut, graphiques au milieu, tableau détaillé en bas
- Code couleur positif/négatif/neutre cohérent
- Grille responsive avec `auto-fit`

**Détail immeuble** (`dashboard_immeuble_detail.html`) : **Excellent** (9/10)
- 30+ indicateurs organisés en sections thématiques
- Barres de progression pour le remboursement des crédits
- Boutons d'actions rapides en bas de page
- Graphiques Chart.js (valeur, crédit, loyers)

**Bilan fiscal** (`bilan_fiscal.html`) : **Très bon** (8/10)
- Sélecteur d'année pratique
- Détail par type de charge
- Résultat coloré positif/négatif

### 4.4 Problèmes d'ergonomie identifiés

| Problème | Sévérité | Localisation |
|----------|----------|-------------|
| 3 palettes de couleurs différentes (violet, bleu, bleu-gris) | Moyenne | Templates variés |
| Emojis utilisés comme icônes sans alternative texte | Haute | `dashboard_immeuble_detail.html` |
| Pas de balises sémantiques `<h2>`, `<h3>` (div avec classes) | Haute | Tous les dashboards |
| Tableaux non accessibles (pas de `<thead>`, `<tbody>`) | Haute | `dashboard_patrimoine.html` |
| Pas d'états de chargement (spinners) sur les formulaires | Moyenne | Tous les formulaires |
| Pas de confirmation avant actions destructives | Moyenne | Admin actions |
| Pas d'export des tableaux de bord | Haute | Tous les dashboards |
| Contraste insuffisant sur certains textes gris | Moyenne | `.no-data` dans `bilan_fiscal.html` |
| Aucun skip link pour la navigation clavier | Haute | Tous les templates |
| Graphiques Chart.js non accessibles aux lecteurs d'écran | Haute | Dashboards |

### 4.5 Score Design/Ergonomie : 6.5/10

Bonne base visuelle avec Jazzmin, dashboards de qualité, mais manque de cohérence inter-pages, accessibilité WCAG insuffisante, et fonctionnalités UX manquantes (export, filtres, états de chargement).

---

## 5. Logique Métier & Calculs

### 5.1 Problèmes CRITIQUES

#### 5.1.1 Calculs financiers en `float` au lieu de `Decimal`

**Fichiers concernés :**
- `patrimoine_calculators.py:32-75` — Génération d'échéancier crédit
- `calculators.py:71` — Prorata des provisions mensuelles
- `pdf_generator.py:259-263` — Calcul TVA
- `models.py:514-537` — Capital restant dû

**Problème :** L'arithmétique `float` accumule des erreurs d'arrondi. Sur 240+ mensualités de crédit, l'erreur peut atteindre 10-50€.

```python
# patrimoine_calculators.py:31-59 (ACTUEL)
capital = float(self.credit.capital_emprunte)
taux_mensuel = float(self.credit.taux_interet) / 100 / 12
interets = capital_restant * taux_mensuel  # Propagation d'erreurs float

# CORRECTION RECOMMANDÉE
from decimal import Decimal
capital = Decimal(str(self.credit.capital_emprunte))
taux_mensuel = Decimal(str(self.credit.taux_interet)) / 100 / 12
```

#### 5.1.2 Plafonnement incorrect des mois actifs

**Fichier :** `patrimoine_calculators.py:223-224`

```python
mois_actifs = (fin_effective.year - debut_effectif.year) * 12 + (...)
mois_actifs = min(mois_actifs, 12)  # ERREUR : plafonne à 12 même pour calcul annuel
```

**Impact :** Le calcul des loyers annuels peut sous-estimer les revenus.

#### 5.1.3 Pas de validation de chevauchement des tarifications au niveau modèle

**Fichier :** `models.py:266-289` (méthode `clean()` de BailTarification)

```python
def clean(self):
    # Vérifie seulement :
    # 1. date_fin > date_debut
    # 2. date_debut >= bail.date_debut
    # MANQUANT : vérification de chevauchement avec d'autres tarifications !
```

**Impact :** Deux tarifications actives simultanées sont possibles. `get_tarification_at()` retourne la plus récente, ignorant silencieusement l'autre.

### 5.2 Problèmes ÉLEVÉS

| Problème | Fichier:Ligne | Impact |
|----------|---------------|--------|
| Division par zéro si `ancien_loyer=0` | `calculators.py:126` | Crash `ZeroDivisionError` |
| Pas de validation que `nouvel_indice > 0` | `views.py:450` | Loyer révisé potentiellement négatif |
| Quote-parts peuvent sommer à != 100% | `models.py:309-321` | Répartition des charges incorrecte |
| `CRD` masque les erreurs avec `max(0, crd)` | `models.py:537` | Cache les erreurs d'arrondi |
| Deux chemins de prorata incohérents pour les dépenses | `pdf_generator.py:525-554` | Même dépense = allocation différente selon format |
| Consommation sans `date_debut` = 100% alloué | `pdf_generator.py:581-619` | Ignore la présence réelle du locataire |
| Bail retourne `0` au lieu de `None` si pas de tarification | `models.py:148-176` | Masque silencieusement les données manquantes |

### 5.3 Problèmes MOYENS

| Problème | Fichier:Ligne | Impact |
|----------|---------------|--------|
| Amortissement arrondi à l'année (seuil 6 mois) | `models.py:628-639` | Déclaration LMNP potentiellement inexacte |
| `duree_jours` vacance incohérent avec `RatiosCalculator` | `models.py:669` vs `patrimoine_calculators.py:502` | Taux de vacance > 100% possible |
| Continuité tarifications ne vérifie pas le début | `calculators.py:202-239` | Trou possible entre début bail et première tarification |
| Avis d'échéance : date limite = date courante (hardcodé) | `pdf_generator.py:393` | Pas de distinction terme à échoir / terme échu |

### 5.4 Score Logique Métier : 6/10

Les calculs sont corrects dans le cas nominal, mais de nombreux edge cases ne sont pas gérés. L'utilisation de `float` pour les calculs financiers est un défaut structurel à corriger en priorité.

---

## 6. Fiabilité & Stabilité

### 6.1 Problèmes CRITIQUES

#### 6.1.1 Absence de transactions atomiques

Les opérations multi-étapes ne sont pas encapsulées dans des transactions `@transaction.atomic()`. Si une erreur survient entre deux étapes, la base de données reste dans un état incohérent.

**Cas critiques :**

| Opération | Fichier:Ligne | Risque |
|-----------|---------------|--------|
| Création tarification après révision (ferme ancienne + crée nouvelle) | `views.py:523-566` | Bail sans tarification active |
| Suppression + recréation échéancier crédit | `patrimoine_calculators.py:79-110` | Échéances supprimées sans remplacement |
| Marquage en lot des paiements | `admin.py:209-213` | Mise à jour partielle |
| Génération ZIP de quittances | `admin.py:343-398` | ZIP incomplet sans avertissement |

#### 6.1.2 Bail créable sans tarification initiale

**Fichier :** `models.py:80-183`

Aucune contrainte modèle n'impose qu'un bail ait au moins une `BailTarification`. Un bail créé manuellement après la migration 0013 n'aura aucune tarification, provoquant des `None` silencieux dans toute l'application.

### 6.2 Problèmes ÉLEVÉS

#### 6.2.1 Gestion d'erreurs générique

Toutes les vues PDF utilisent un `except Exception` générique qui attrape tout (y compris `SystemExit`, `MemoryError`) :

```python
# views.py:171-173 (répété 7 fois)
except Exception as e:
    logger.exception(f"Erreur inattendue...")
    return HttpResponse(f"Erreur: {str(e)}", status=500)  # Expose les détails internes
```

#### 6.2.2 Conversion float sans validation

```python
# views.py:326 - Crash si input non numérique
montant_retenues = float(request.POST.get('montant_retenues') or 0)

# views.py:434 - AttributeError si None
nouvel_indice = float(request.POST.get('nouvel_indice_manuel').replace(',', '.'))
```

#### 6.2.3 Dépendance INSEE sans retry ni fallback

```python
# views.py:360-385
with urllib.request.urlopen(req, timeout=3) as response:  # Timeout 3s seulement
    html = response.read().decode('utf-8')
    # Parsing HTML avec regex (fragile si structure change)
```

**Impacts :** Si INSEE est indisponible, le formulaire s'affiche sans indices, sans message d'erreur clair.

#### 6.2.4 Condition de concurrence sur les sessions

**Fichier :** `views.py:453-467`

Les données de révision de loyer sont stockées en session. Si un utilisateur ouvre deux onglets de révision, la seconde écrase la première. Pas de verrouillage optimiste non plus sur les tarifications.

### 6.3 Problèmes MOYENS

| Problème | Fichier:Ligne | Impact |
|----------|---------------|--------|
| Pas de pagination dans les dashboards (tous les immeubles chargés) | `views.py:591` | OOM sur grands volumes |
| N+1 queries dans le calcul de régularisation | `pdf_generator.py:516-619` | Lenteur sur nombreuses dépenses |
| `print()` au lieu de `logger` dans la migration | `migrations/0013:24,40,50` | Logs perdus |
| Contexte utilisateur absent des logs d'erreur | `views.py:169,226,288` | Debugging difficile |
| `prefetch_related` sans limite sur dashboard détail | `views.py:691-697` | Chargement mémoire excessif |

### 6.4 Tests

**Aucun test unitaire ou d'intégration n'a été détecté dans le projet.** C'est un point bloquant pour garantir la fiabilité :
- Pas de tests des calculateurs financiers
- Pas de tests des vues PDF
- Pas de tests des modèles et contraintes
- Pas de tests de performance

### 6.5 Score Fiabilité/Stabilité : 5/10

L'absence de transactions atomiques et de tests est préoccupante. L'application fonctionne en usage normal mais peut produire des incohérences de données en cas d'erreur.

---

## 7. Sécurité

### 7.1 Failles CRITIQUES

#### 7.1.1 Vues API sans authentification

**6 vues de génération PDF n'ont aucun décorateur d'authentification :**

| Vue | URL | Risque |
|-----|-----|--------|
| `generer_quittance_pdf` | `/api/quittance/<pk>/` | Accès aux quittances de n'importe quel bail |
| `generer_avis_echeance_pdf` | `/api/avis_echeance/<pk>/` | Accès aux avis d'échéance |
| `generer_regularisation_pdf` | `/api/regularisation/<pk>/` | Accès aux régularisations |
| `generer_solde_tout_compte_pdf` | `/api/solde_tout_compte/<pk>/` | Accès aux soldes de tout compte |
| `generer_revision_loyer_pdf` | `/api/revision_loyer/<pk>/` | Modification des loyers |
| `creer_tarification_from_revision` | `/api/creer_tarification_revision/<pk>/` | Création de tarifications |

**Impact :** Un utilisateur non authentifié peut accéder aux données financières de TOUS les baux en itérant sur les IDs (`/api/quittance/1/`, `/api/quittance/2/`, etc.) et **modifier les tarifications** sans autorisation.

**Note :** Seules les 4 vues dashboard sont protégées par `@staff_member_required`.

#### 7.1.2 Pas de contrôle d'autorisation (IDOR)

Même si l'authentification était ajoutée, il n'y a **aucun contrôle que l'utilisateur connecté a le droit d'accéder au bail demandé** :

```python
# views.py:119 - Récupère n'importe quel bail par son ID
bail = get_object_or_404(Bail, pk=pk)  # Pas de filtre par utilisateur/propriétaire
```

#### 7.1.3 Configuration Django dangereuse

```python
# settings.py:23
SECRET_KEY = 'django-insecure-nqcblgw@xfv%j-z*#zr((z*aw9d=gdkhzxj*0qf74f74dwltlt'

# settings.py:26
DEBUG = True  # Stack traces exposées aux utilisateurs

# settings.py:28
ALLOWED_HOSTS = ['*']  # Accepte les requêtes de n'importe quel host
```

**Impact :** Détournement de sessions, bypass CSRF, injection d'en-tête Host, divulgation de code source et requêtes SQL dans les pages d'erreur.

### 7.2 Failles ÉLEVÉES

| Faille | Détail | Fichier:Ligne |
|--------|--------|---------------|
| Pas de validation de type de fichier sur upload | `justificatif` FileField sans restriction mime/extension | `models.py:590` |
| Pas de limite de taille d'upload | Aucun `MAX_UPLOAD_SIZE` configuré | `settings.py` |
| Erreurs exposant les détails internes | `HttpResponse(f"Erreur: {str(e)}", status=500)` | `views.py:172` |
| Pas de rate limiting | Génération PDF illimitée, risque DoS | Toutes les vues API |
| Nom de fichier PDF non sanitizé | `nom_locataire` utilisé directement dans filename | `views.py:159` |

### 7.3 Failles MOYENNES

| Faille | Détail |
|--------|--------|
| `SESSION_COOKIE_SECURE` non configuré | Sessions transmises en clair sur HTTP |
| `SESSION_COOKIE_HTTPONLY` non configuré | Sessions accessibles via JavaScript |
| Pas de `SECURE_BROWSER_XSS_FILTER` | Protection XSS navigateur désactivée |
| Pas de `X_FRAME_OPTIONS` | Risque de clickjacking |
| Pas de `SECURE_CONTENT_TYPE_NOSNIFF` | Risque d'exécution de contenu uploadé |
| Pas de support HTTPS natif | À configurer via reverse proxy |
| Pas de `python-dotenv` | Secrets directement dans le code source |

### 7.4 Points positifs

- Protection CSRF activée via middleware Django
- Pas de requêtes SQL brutes (protection injection SQL via ORM)
- Templates Django avec auto-escaping (protection XSS sur les variables)
- 4 validateurs de mot de passe configurés
- Usage correct de `mark_safe()` uniquement sur du HTML statique

### 7.5 Score Sécurité : 3/10

Les failles d'authentification manquante sur les vues API et la configuration Django en mode développement représentent des risques critiques immédiats. L'application **ne doit pas être exposée sur Internet** en l'état.

---

## 8. Synthèse & Priorisation des Corrections

### 8.1 Corrections URGENTES (avant mise en production)

| # | Correction | Fichier(s) | Effort |
|---|-----------|------------|--------|
| 1 | Ajouter `@login_required` ou `@staff_member_required` sur les 6 vues API | `views.py` | Faible |
| 2 | Remplacer `SECRET_KEY` par variable d'environnement | `settings.py` | Faible |
| 3 | Passer `DEBUG = False` en production | `settings.py` | Faible |
| 4 | Restreindre `ALLOWED_HOSTS` | `settings.py` | Faible |
| 5 | Ajouter `@transaction.atomic()` sur `creer_tarification_from_revision` | `views.py:492` | Faible |
| 6 | Ajouter `@transaction.atomic()` sur `creer_echeances_en_base` | `patrimoine_calculators.py:79` | Faible |
| 7 | Installer `python-dotenv` et externaliser les secrets | `settings.py` | Moyen |
| 8 | Configurer les headers de sécurité (SECURE_*, X_FRAME_OPTIONS, etc.) | `settings.py` | Faible |

### 8.2 Corrections PRIORITAIRES (sprint suivant)

| # | Correction | Fichier(s) | Effort |
|---|-----------|------------|--------|
| 9 | Remplacer `float` par `Decimal` dans tous les calculs financiers | `patrimoine_calculators.py`, `calculators.py`, `pdf_generator.py` | Élevé |
| 10 | Ajouter la validation de chevauchement des tarifications dans `clean()` | `models.py:266-289` | Moyen |
| 11 | Corriger le plafonnement `min(mois_actifs, 12)` | `patrimoine_calculators.py:224` | Faible |
| 12 | Ajouter try/except sur les conversions `float()` dans les vues | `views.py:326,434,537` | Faible |
| 13 | Ajouter la contrainte unique sur tarification active | `models.py` (migration) | Moyen |
| 14 | Valider que les quote-parts somment à 100% | `models.py:309-321` | Moyen |
| 15 | Ajouter un contrôle d'autorisation par propriétaire sur les vues | `views.py` (toutes les vues) | Moyen |
| 16 | Écrire les tests unitaires des calculateurs | Nouveau fichier `tests/` | Élevé |

### 8.3 Corrections RECOMMANDÉES (amélioration continue)

| # | Correction | Catégorie |
|---|-----------|-----------|
| 17 | Unifier la palette de couleurs (3 palettes → 1) | Design |
| 18 | Ajouter des balises sémantiques HTML aux dashboards | Accessibilité |
| 19 | Ajouter l'export CSV/Excel sur les dashboards | Fonctionnalité |
| 20 | Ajouter des `aria-label` aux graphiques Chart.js | Accessibilité |
| 21 | Implémenter un retry avec backoff sur la requête INSEE | Fiabilité |
| 22 | Ajouter la pagination aux dashboards | Performance |
| 23 | Résoudre les N+1 queries dans la régularisation | Performance |
| 24 | Ajouter un système de notifications (loyers impayés, échéances) | Fonctionnalité |
| 25 | Ajouter un rate limiting sur les vues API | Sécurité |
| 26 | Valider les types de fichiers sur l'upload de justificatifs | Sécurité |

---

### Conclusion

Ce logiciel de gestion locative est **fonctionnellement très complet** et couvre les besoins essentiels de la gestion locative française. La structure du code est propre et le modèle de données est bien pensé, notamment le système d'historisation des tarifications.

Les **corrections urgentes (items 1-8)** sont majoritairement simples à implémenter et permettraient de sécuriser l'application pour un usage en production. Les **corrections prioritaires (items 9-16)** concernent la robustesse des calculs financiers et la fiabilité des données, essentielles pour un logiciel manipulant des montants réels.

L'investissement le plus important serait la mise en place d'une **suite de tests** couvrant les calculateurs financiers, les vues et les contraintes de données, ce qui garantirait la fiabilité à long terme de l'application.
