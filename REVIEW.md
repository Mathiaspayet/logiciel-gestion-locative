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
8. [Corrections Appliquées](#8-corrections-appliquées)
9. [Reste à Faire](#9-reste-à-faire)

---

## 1. Résumé Exécutif

### Scores par catégorie

| Catégorie | Avant corrections | Après corrections | Commentaire |
|-----------|:-:|:-:|-------------|
| **Fonctionnalités** | 9/10 | 9/10 | Couverture fonctionnelle très complète |
| **Design / Ergonomie** | 6.5/10 | 6.5/10 | Bonne base, manque de cohérence et d'accessibilité |
| **Logique Métier** | 6/10 | **8/10** | Calculs Decimal, validation chevauchement, bugs corrigés |
| **Fiabilité / Stabilité** | 5/10 | **7/10** | Transactions atomiques, validation d'entrées, retry INSEE |
| **Sécurité** | 3/10 | **7/10** | Authentification, headers, config externalisée |
| **Note globale** | **5.9/10** | **7.5/10** | **Application déployable en production (avec HTTPS)** |

### Verdict

L'application offre une **couverture fonctionnelle remarquable** pour la gestion locative française (baux, quittances, régularisation de charges, suivi patrimonial, crédit, fiscalité LMNP). L'architecture Django est bien structurée et le code est lisible.

Les corrections appliquées couvrent les failles critiques de sécurité, la fiabilité des calculs financiers et l'intégrité des données. **L'application est maintenant déployable en production** à condition de configurer les variables d'environnement et un reverse proxy HTTPS.

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
│   ├── models.py              (680+ lignes - 18 modèles)
│   ├── views.py               (1090+ lignes - 12 vues)
│   ├── admin.py               (740 lignes - 16+ classes admin)
│   ├── pdf_generator.py       (910+ lignes - génération PDF)
│   ├── calculators.py         (239 lignes - calculs facturation)
│   ├── patrimoine_calculators.py (542 lignes - calculs patrimoniaux)
│   ├── exceptions.py          (47 lignes - exceptions métier)
│   ├── templates/             (10 templates HTML)
│   └── migrations/            (17 migrations)
├── gestion_locative/
│   ├── settings.py            (350+ lignes)
│   └── urls.py
└── db.sqlite3
```

### Observations architecture

**Points forts :**
- Architecture monolithique adaptée au périmètre fonctionnel
- Séparation claire : modèles / vues / calculateurs / générateur PDF
- Système d'historisation des tarifications (BailTarification) bien conçu
- Support Docker pour le déploiement
- Configuration sécurisée via variables d'environnement

**Points faibles (restants) :**
- Aucun test unitaire ou d'intégration
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
| Crédits immobiliers | OK | Amortissable/In Fine, échéancier complet en Decimal |
| Charges fiscales | OK | 9 types de charges déductibles, justificatifs |
| Amortissements (LMNP) | OK | 3 types de biens, calcul VNC au mois près |
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
| Récupération indices INSEE | OK | IRL et ILC avec retry automatique et fallback manuel |

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

### 4.4 Problèmes d'ergonomie restants

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

### 5.1 Problèmes CORRIGÉS

| Problème | Correction | Commit |
|----------|-----------|--------|
| Calculs financiers en `float` | Passage en `Decimal` (échéancier, mensualité, CRD, TVA, amortissement) | `df5ccbe` |
| Plafonnement incorrect `mois_actifs` | Borne inférieure ajoutée `max(0, min(..., 12))` | `df5ccbe` |
| Débordement mois > 12 dans `get_loyers_annuels` | Recalcul correct avec offset mois/année | `df5ccbe` |
| Pas de validation chevauchement tarifications | `clean()` vérifie les chevauchements en base | `df5ccbe` |
| Amortissement arrondi au seuil 6 mois | Prorata au mois près (mensuel) | `df5ccbe` |

### 5.2 Problèmes restants (ÉLEVÉS)

| Problème | Fichier:Ligne | Impact |
|----------|---------------|--------|
| Division par zéro si `ancien_loyer=0` | `calculators.py:126` | Crash `ZeroDivisionError` |
| Quote-parts peuvent sommer à != 100% | `models.py:309-321` | Répartition des charges incorrecte |
| Deux chemins de prorata incohérents pour les dépenses | `pdf_generator.py:525-554` | Même dépense = allocation différente selon format |
| Consommation sans `date_debut` = 100% alloué | `pdf_generator.py:581-619` | Ignore la présence réelle du locataire |
| Bail retourne `0` au lieu de `None` si pas de tarification | `models.py:148-176` | Masque silencieusement les données manquantes |

### 5.3 Problèmes restants (MOYENS)

| Problème | Fichier:Ligne | Impact |
|----------|---------------|--------|
| `duree_jours` vacance incohérent avec `RatiosCalculator` | `models.py:669` vs `patrimoine_calculators.py:502` | Taux de vacance > 100% possible |
| Continuité tarifications ne vérifie pas le début | `calculators.py:202-239` | Trou possible entre début bail et première tarification |
| Avis d'échéance : date limite = date courante (hardcodé) | `pdf_generator.py:393` | Pas de distinction terme à échoir / terme échu |

### 5.4 Score Logique Métier : 8/10 (avant : 6/10)

Le passage à `Decimal` élimine les erreurs d'arrondi sur les calculs financiers. La validation de chevauchement et la contrainte unique protègent l'intégrité des tarifications. Quelques edge cases restent à traiter.

---

## 6. Fiabilité & Stabilité

### 6.1 Problèmes CORRIGÉS

| Problème | Correction | Commit |
|----------|-----------|--------|
| Création tarification sans transaction | `transaction.atomic()` sur fermeture + création | `df5ccbe` |
| Échéancier crédit sans transaction | `@transaction.atomic` sur `creer_echeances_en_base` | `df5ccbe` |
| Conversion float sans validation | `try/except ValueError` sur toutes les entrées utilisateur | `df5ccbe` |
| INSEE : timeout 3s, pas de retry | Retry 3x avec backoff exponentiel, timeout 10s | `df5ccbe` |
| Erreurs 500 exposent détails internes | Message générique renvoyé, détails uniquement dans les logs | `df5ccbe` |
| N+1 queries dans régularisation PDF | Pré-chargement quote-parts et `select_related` | `df5ccbe` |

### 6.2 Problèmes restants

| Problème | Sévérité | Impact |
|----------|----------|--------|
| Bail créable sans tarification initiale | Élevé | `None` silencieux dans l'application |
| Condition de concurrence sur sessions (2 onglets révision) | Moyen | Écrasement de données de session |
| Pas de pagination dans les dashboards | Moyen | OOM sur grands volumes |
| `print()` au lieu de `logger` dans migration 0013 | Faible | Logs perdus |
| Pas de verrouillage optimiste sur les tarifications | Moyen | Last-Write-Wins en multi-utilisateur |

### 6.3 Tests

**Aucun test unitaire ou d'intégration n'a été détecté.** C'est le principal point d'amélioration restant.

### 6.4 Score Fiabilité/Stabilité : 7/10 (avant : 5/10)

Les transactions atomiques protègent contre les incohérences de données. La validation des entrées et le retry INSEE améliorent la robustesse. L'absence de tests reste le principal risque.

---

## 7. Sécurité

### 7.1 Failles CORRIGÉES

| Faille | Correction | Commit |
|--------|-----------|--------|
| 6 vues API sans authentification | `@staff_member_required` sur les 10 vues | `f919487` |
| `SECRET_KEY` en dur dans le code | Externalisée via `os.environ.get('DJANGO_SECRET_KEY')` | `df5ccbe` |
| `DEBUG = True` en dur | Via `os.environ.get('DJANGO_DEBUG')`, défaut `True` en dev | `df5ccbe` |
| `ALLOWED_HOSTS = ['*']` | Via `os.environ.get('DJANGO_ALLOWED_HOSTS')`, défaut `localhost,127.0.0.1` | `df5ccbe` |
| Pas de `X_FRAME_OPTIONS` | `X_FRAME_OPTIONS = 'DENY'` | `df5ccbe` |
| Pas de `SECURE_CONTENT_TYPE_NOSNIFF` | `SECURE_CONTENT_TYPE_NOSNIFF = True` | `df5ccbe` |
| `SESSION_COOKIE_HTTPONLY` non configuré | `SESSION_COOKIE_HTTPONLY = True` | `df5ccbe` |
| Cookies non sécurisés en HTTPS | `CSRF_COOKIE_SECURE`, `SESSION_COOKIE_SECURE`, `HSTS` activés si `DEBUG=False` | `df5ccbe` |
| Pas de limite d'upload | `DATA_UPLOAD_MAX_MEMORY_SIZE = 10MB` | `df5ccbe` |
| Erreurs exposant détails internes | Message générique en réponse HTTP 500 | `df5ccbe` |

### 7.2 Failles restantes

| Faille | Sévérité | Détail |
|--------|----------|--------|
| Pas de contrôle d'autorisation (IDOR) | Élevé | Un staff peut accéder aux baux de tous les propriétaires |
| Pas de validation de type de fichier sur upload | Moyen | `justificatif` FileField sans restriction mime/extension |
| Pas de rate limiting | Moyen | Génération PDF illimitée, risque DoS |
| Nom de fichier PDF non sanitizé | Faible | `nom_locataire` utilisé directement dans filename |

### 7.3 Points positifs

- Toutes les vues protégées par `@staff_member_required`
- Protection CSRF activée via middleware Django
- Pas de requêtes SQL brutes (protection injection SQL via ORM)
- Templates Django avec auto-escaping (protection XSS)
- 4 validateurs de mot de passe configurés
- Headers de sécurité configurés (clickjacking, MIME sniffing, HSTS)
- Configuration externalisée via variables d'environnement
- Cookies sécurisés en production

### 7.4 Score Sécurité : 7/10 (avant : 3/10)

Les failles critiques (authentification, configuration) sont corrigées. L'application peut être exposée en production derrière un reverse proxy HTTPS. Le contrôle IDOR reste à implémenter pour un usage multi-propriétaire.

---

## 8. Corrections Appliquées

### Commit 1 : `f919487` — Authentification API

- `@staff_member_required` ajouté sur les 6 vues PDF non protégées
- Import déplacé en haut du fichier `views.py`

### Commit 2 : `df5ccbe` — Sécurité, fiabilité, calculs, performance

**Sécurité (`settings.py`)**
- `SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS` via variables d'environnement
- Headers : `X_FRAME_OPTIONS`, `SECURE_CONTENT_TYPE_NOSNIFF`, `HSTS`
- `SESSION_COOKIE_HTTPONLY`, cookies sécurisés en production
- Limite uploads 10MB
- Messages d'erreur 500 ne divulguent plus les détails internes

**Fiabilité (`views.py`, `patrimoine_calculators.py`)**
- `transaction.atomic()` sur création tarification et régénération échéancier
- Validation `try/except` sur les entrées `float()` des formulaires
- Retry avec backoff exponentiel sur INSEE (3 essais, timeout 10s)

**Calculs financiers — float → Decimal (`models.py`, `patrimoine_calculators.py`)**
- `CreditGenerator.generer_echeancier()` : Decimal
- `CreditImmobilier.mensualite_hors_assurance` : Decimal
- `CreditImmobilier.get_capital_restant_du_at()` : Decimal
- `Bail.montant_tva` / `loyer_ttc` : Decimal
- `Amortissement.dotation_annuelle` / `get_valeur_nette_comptable()` : Decimal + prorata mensuel
- `EcheanceCredit.mensualite_totale` : Decimal natif

**Intégrité des données (`models.py`)**
- `BailTarification.clean()` : validation de chevauchement (était formset-only)
- `UniqueConstraint` : une seule tarification active par bail (`date_fin IS NULL`)
- Migration `0017` pour la contrainte

**Performance (`pdf_generator.py`)**
- Pré-chargement des quote-parts et totaux (supprime N+1 queries)
- `select_related('cle_repartition')` sur dépenses et consommations

**Bugs (`patrimoine_calculators.py`)**
- Débordement mois > 12 dans `get_loyers_annuels()`
- Borne inférieure manquante sur `mois_actifs`

---

## 9. Reste à Faire

### Priorité haute

| # | Correction | Catégorie | Effort |
|---|-----------|-----------|--------|
| 1 | Écrire les tests unitaires des calculateurs financiers | Fiabilité | Élevé |
| 2 | Ajouter un contrôle IDOR par propriétaire sur les vues | Sécurité | Moyen |
| 3 | Valider que les quote-parts somment à un total cohérent | Logique | Moyen |
| 4 | Gérer le cas `ancien_loyer=0` (division par zéro) | Logique | Faible |

### Priorité moyenne

| # | Correction | Catégorie | Effort |
|---|-----------|-----------|--------|
| 5 | Ajouter la pagination aux dashboards | Performance | Moyen |
| 6 | Valider les types de fichiers sur upload justificatifs | Sécurité | Faible |
| 7 | Ajouter un rate limiting sur les vues | Sécurité | Moyen |
| 8 | Corriger la condition de concurrence session (2 onglets) | Fiabilité | Moyen |
| 9 | Unifier la palette de couleurs des templates | Design | Moyen |

### Priorité basse (amélioration continue)

| # | Correction | Catégorie |
|---|-----------|-----------|
| 10 | Ajouter des balises sémantiques HTML aux dashboards | Accessibilité |
| 11 | Ajouter l'export CSV/Excel sur les dashboards | Fonctionnalité |
| 12 | Ajouter des `aria-label` aux graphiques Chart.js | Accessibilité |
| 13 | Ajouter un système de notifications (loyers impayés) | Fonctionnalité |
| 14 | Ajouter un audit log des actions utilisateur | Fiabilité |

---

### Configuration pour la production

Pour déployer en production, configurer ces variables d'environnement :

```bash
export DJANGO_SECRET_KEY='votre-clé-secrète-unique-et-longue'
export DJANGO_DEBUG='False'
export DJANGO_ALLOWED_HOSTS='votre-domaine.fr,www.votre-domaine.fr'
```

Et s'assurer qu'un reverse proxy HTTPS (nginx, Caddy) est en place pour activer automatiquement les cookies sécurisés et HSTS.
