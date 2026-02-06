"""
Vues refactorisées pour la génération de documents PDF.
Version optimisée utilisant PDFGenerator et templates Django.
"""
import logging
from datetime import datetime, date, timedelta
from io import BytesIO

from django.http import HttpResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.db.models import Q
from django.middleware.csrf import get_token
from django.contrib.admin.views.decorators import staff_member_required

from .models import Immeuble, Bail, Local
from .pdf_generator import PDFGenerator
from .calculators import BailCalculator
from .exceptions import TarificationNotFoundError
from .patrimoine_calculators import PatrimoineCalculator, RentabiliteCalculator

# Configuration logging
logger = logging.getLogger(__name__)


# ============================================================================
# HELPERS
# ============================================================================

# Traduction des mois en français
MOIS_FR = {
    1: 'Janvier', 2: 'Février', 3: 'Mars', 4: 'Avril',
    5: 'Mai', 6: 'Juin', 7: 'Juillet', 8: 'Août',
    9: 'Septembre', 10: 'Octobre', 11: 'Novembre', 12: 'Décembre'
}


def generer_periodes_disponibles(bail, nb_periodes=None):
    """
    Génère la liste des périodes disponibles pour un bail.

    Génère toutes les périodes depuis la date de début du bail jusqu'à aujourd'hui,
    permettant de générer des documents pour des tarifications terminées.
    Les périodes sont triées du plus récent au plus ancien.

    Args:
        bail: Instance de Bail
        nb_periodes: Ignoré (conservé pour compatibilité). Toutes les périodes
                     depuis le début du bail sont générées.

    Returns:
        list: Liste de dict {label, value}
    """
    periodes = []
    today = date.today()

    # Déterminer la date de début : date du bail ou première tarification
    date_debut_bail = bail.date_debut
    if not date_debut_bail:
        # Fallback : première tarification
        premiere_tarif = bail.tarifications.order_by('date_debut').first()
        if premiere_tarif:
            date_debut_bail = premiere_tarif.date_debut
        else:
            # Aucune tarification : générer 24 mois par défaut
            date_debut_bail = date(today.year - 2, today.month, 1)

    # Commencer au 1er du mois de début du bail
    current = date(date_debut_bail.year, date_debut_bail.month, 1)

    # Date limite : mois actuel
    date_limite = date(today.year, today.month, 1)

    if bail.frequence_paiement == 'TRIMESTRIEL':
        # Trimestres : générer depuis le début du bail jusqu'à aujourd'hui
        while current <= date_limite:
            label = f"{MOIS_FR[current.month]} {current.year} - Trimestre"
            periodes.append({
                'label': label,
                'value': current.strftime('%Y-%m-%d')
            })

            # Avancer de 3 mois
            month = current.month + 3
            year = current.year
            while month > 12:
                month -= 12
                year += 1
            current = date(year, month, 1)
    else:
        # Mensuels : générer depuis le début du bail jusqu'à aujourd'hui
        while current <= date_limite:
            label = f"{MOIS_FR[current.month]} {current.year}"
            periodes.append({
                'label': label,
                'value': current.strftime('%Y-%m-%d')
            })

            # Mois suivant
            month = current.month + 1
            year = current.year
            if month > 12:
                month = 1
                year += 1
            current = date(year, month, 1)

    return list(reversed(periodes))  # Du plus récent au plus ancien


# ============================================================================
# VUES PDF (Refactorisées)
# ============================================================================

@staff_member_required
def generer_quittance_pdf(request, pk):
    """
    Génère une quittance de loyer pour un bail.
    Version refactorisée utilisant PDFGenerator et templates Django.
    """
    bail = get_object_or_404(Bail, pk=pk)

    logger.info(f"Demande quittance pour bail {pk} par user {request.user}")

    # GET : Afficher formulaire
    if request.method != 'POST':
        # Préparer contexte
        locataire = bail.occupants.filter(role='LOCATAIRE').first()
        tarif_actuel = bail.tarification_actuelle

        context = {
            'bail': bail,
            'locataire': locataire or "Non renseigné",
            'loyer_hc': tarif_actuel.loyer_hc if tarif_actuel else 0,
            'charges': tarif_actuel.charges if tarif_actuel else 0,
            'total': bail.loyer_ttc,
            'frequence': bail.get_frequence_paiement_display(),
            'periodes_disponibles': generer_periodes_disponibles(bail),
            'type_document': 'quittance',
        }

        return render(request, 'pdf_forms/quittance_form.html', context)

    # POST : Générer PDF
    try:
        periodes_selectionnees = request.POST.getlist('periodes')

        if not periodes_selectionnees:
            return HttpResponse("Erreur: Aucune période sélectionnée.", status=400)

        # Générer PDF
        generator = PDFGenerator(bail)
        pdf_content = generator.generer_quittance(periodes_selectionnees)

        # Préparer nom fichier
        occupant = bail.occupants.filter(role='LOCATAIRE').first()
        nom_locataire = occupant.nom.upper().replace(" ", "_") if occupant else "Inconnu"

        date_debut = min(periodes_selectionnees)
        date_fin = max(periodes_selectionnees)
        periode_str = f"{date_debut}_{date_fin}" if date_debut != date_fin else date_debut

        filename = f"Quittance_{nom_locataire}_{periode_str}.pdf"

        # Retourner PDF
        response = HttpResponse(pdf_content, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'

        logger.info(f"Quittance générée: {filename} ({len(pdf_content)} bytes)")
        return response

    except TarificationNotFoundError as e:
        logger.error(f"Erreur génération quittance bail {pk}: {str(e)}")
        return HttpResponse(str(e), status=400)
    except Exception as e:
        logger.exception(f"Erreur inattendue génération quittance bail {pk}")
        return HttpResponse(f"Erreur: {str(e)}", status=500)


@staff_member_required
def generer_avis_echeance_pdf(request, pk):
    """
    Génère un avis d'échéance pour un bail.
    Version refactorisée utilisant PDFGenerator.
    """
    bail = get_object_or_404(Bail, pk=pk)

    logger.info(f"Demande avis d'échéance pour bail {pk}")

    # GET : Formulaire (réutilise le même template que quittance)
    if request.method != 'POST':
        locataire = bail.occupants.filter(role='LOCATAIRE').first()
        tarif_actuel = bail.tarification_actuelle

        context = {
            'bail': bail,
            'locataire': locataire or "Non renseigné",
            'loyer_hc': tarif_actuel.loyer_hc if tarif_actuel else 0,
            'charges': tarif_actuel.charges if tarif_actuel else 0,
            'total': bail.loyer_ttc,
            'frequence': bail.get_frequence_paiement_display(),
            'periodes_disponibles': generer_periodes_disponibles(bail, nb_periodes=12),
            'type_document': 'avis_echeance',
        }

        return render(request, 'pdf_forms/quittance_form.html', context)

    # POST : Générer PDF
    try:
        periodes_selectionnees = request.POST.getlist('periodes')

        if not periodes_selectionnees:
            return HttpResponse("Erreur: Aucune période sélectionnée.", status=400)

        generator = PDFGenerator(bail)
        pdf_content = generator.generer_avis_echeance(periodes_selectionnees)

        occupant = bail.occupants.filter(role='LOCATAIRE').first()
        nom_locataire = occupant.nom.upper().replace(" ", "_") if occupant else "Inconnu"

        date_debut = min(periodes_selectionnees)
        filename = f"AvisEcheance_{nom_locataire}_{date_debut}.pdf"

        response = HttpResponse(pdf_content, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'

        logger.info(f"Avis d'échéance généré: {filename}")
        return response

    except TarificationNotFoundError as e:
        logger.error(f"Erreur génération avis bail {pk}: {str(e)}")
        return HttpResponse(str(e), status=400)
    except Exception as e:
        logger.exception(f"Erreur génération avis bail {pk}")
        return HttpResponse(f"Erreur: {str(e)}", status=500)


# ============================================================================
# VUES PDF REFACTORISÉES - RÉGULARISATION
# ============================================================================

@staff_member_required
def generer_regularisation_pdf(request, pk):
    """
    Génère le décompte de régularisation de charges sur une période donnée.
    Version refactorisée utilisant PDFGenerator et templates Django.
    """
    bail = get_object_or_404(Bail, pk=pk)

    logger.info(f"Demande régularisation pour bail {pk}")

    # GET : Afficher formulaire
    if request.method != 'POST':
        # Par défaut : Année précédente
        annee_prec = datetime.now().year - 1
        default_start = f"{annee_prec}-01-01"
        default_end = f"{annee_prec}-12-31"

        locataire = bail.occupants.filter(role='LOCATAIRE').first()

        context = {
            'bail': bail,
            'locataire': locataire or "Non renseigné",
            'default_start': default_start,
            'default_end': default_end,
        }

        return render(request, 'pdf_forms/regularisation_form.html', context)

    # POST : Générer PDF
    try:
        date_debut = request.POST.get('date_debut')
        date_fin = request.POST.get('date_fin')
        enregistrer = request.POST.get('enregistrer_historique') == 'on'

        if not date_debut or not date_fin:
            return HttpResponse("Erreur: Dates manquantes.", status=400)

        # Générer PDF
        generator = PDFGenerator(bail)
        pdf_content = generator.generer_regularisation(date_debut, date_fin, enregistrer)

        # Préparer nom fichier
        filename = f"Regularisation_{date_debut}_{date_fin}.pdf"

        # Retourner PDF
        response = HttpResponse(pdf_content, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'

        logger.info(f"Régularisation générée: {filename} ({len(pdf_content)} bytes)")
        return response

    except TarificationNotFoundError as e:
        logger.error(f"Erreur génération régularisation bail {pk}: {str(e)}")
        return HttpResponse(str(e), status=400)
    except Exception as e:
        logger.exception(f"Erreur inattendue génération régularisation bail {pk}")
        return HttpResponse(f"Erreur: {str(e)}", status=500)


# ============================================================================
# VUES PDF REFACTORISÉES - SOLDE DE TOUT COMPTE
# ============================================================================

@staff_member_required
def generer_solde_tout_compte_pdf(request, pk):
    """
    Génère l'arrêté de compte de fin de bail (Solde de tout compte).
    Version refactorisée utilisant PDFGenerator.
    """
    bail = get_object_or_404(Bail, pk=pk)

    logger.info(f"Demande solde tout compte pour bail {pk}")

    # GET : Afficher formulaire
    if request.method != 'POST':
        default_date = bail.date_fin.strftime('%Y-%m-%d') if bail.date_fin else date.today().strftime('%Y-%m-%d')
        locataire = bail.occupants.filter(role='LOCATAIRE').first()

        context = {
            'bail': bail,
            'locataire': locataire or "Non renseigné",
            'depot_garantie': f"{bail.depot_garantie} €",
            'default_date': default_date,
        }

        return render(request, 'pdf_forms/solde_tout_compte_form.html', context)

    # POST : Générer PDF
    try:
        date_sortie = request.POST.get('date_sortie')
        statut_loyer = request.POST.get('statut_loyer')
        montant_retenues = float(request.POST.get('montant_retenues') or 0)
        desc_retenues = request.POST.get('desc_retenues', '')

        if not date_sortie:
            return HttpResponse("Erreur: Date de sortie manquante.", status=400)

        # Générer PDF
        generator = PDFGenerator(bail)
        pdf_content = generator.generer_solde_tout_compte(
            date_sortie, statut_loyer, montant_retenues, desc_retenues
        )

        # Nom du fichier
        filename = f"Solde_Tout_Compte_{bail.local.numero_porte}.pdf"

        # Retourner PDF
        response = HttpResponse(pdf_content, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'

        logger.info(f"Solde tout compte généré: {filename}")
        return response

    except TarificationNotFoundError as e:
        logger.error(f"Erreur génération solde bail {pk}: {str(e)}")
        return HttpResponse(str(e), status=400)
    except Exception as e:
        logger.exception(f"Erreur génération solde bail {pk}")
        return HttpResponse(f"Erreur: {str(e)}", status=500)


# ============================================================================
# VUES PDF REFACTORISÉES - RÉVISION LOYER
# ============================================================================

def fetch_insee_indices(url, limit=8):
    """Récupère les derniers indices (Trimestre, Valeur) sur le site de l'INSEE."""
    import urllib.request
    import re

    indices = []
    try:
        req = urllib.request.Request(
            url,
            data=None,
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
        )
        with urllib.request.urlopen(req, timeout=3) as response:
            html = response.read().decode('utf-8')
            pattern = r'<th[^>]*>(T[1-4] [0-9]{4})</th>[\s\S]*?<td class="nombre">([0-9]+,[0-9]+)</td>'
            matches = re.findall(pattern, html)

            for match in matches[:limit]:
                trimestre = match[0]
                valeur = match[1].replace(',', '.')
                indices.append({'trimestre': trimestre, 'valeur': float(valeur)})
    except Exception as e:
        logger.warning(f"Erreur récupération INSEE : {e}")
    return indices


@staff_member_required
def generer_revision_loyer_pdf(request, pk):
    """
    Génère le courrier de révision de loyer et redirige vers assistant si update_bail.
    Version refactorisée utilisant PDFGenerator.
    """
    bail = get_object_or_404(Bail, pk=pk)

    logger.info(f"Demande révision loyer pour bail {pk}")

    # GET : Afficher formulaire
    if request.method != 'POST':
        # Tentative de récupération des indices INSEE
        url_insee = "https://www.insee.fr/fr/statistiques/serie/001515333"  # IRL
        nom_indice = "IRL"
        if bail.local.type_local != 'APPART':
            url_insee = "https://www.insee.fr/fr/statistiques/serie/001515332"  # ILC
            nom_indice = "ILC"

        indices_dispos = fetch_insee_indices(url_insee)

        tarif_actuel = bail.tarification_actuelle
        loyer_actuel = f"{tarif_actuel.loyer_hc} €" if tarif_actuel else "Non défini"
        indice_actuel = tarif_actuel.indice_reference if tarif_actuel else None
        trimestre_actuel = tarif_actuel.trimestre_reference if tarif_actuel else None

        context = {
            'bail': bail,
            'nom_indice': nom_indice,
            'loyer_actuel': loyer_actuel,
            'indice_actuel': indice_actuel,
            'trimestre_actuel': trimestre_actuel,
            'indices_dispos': indices_dispos,
            'date_today': date.today().strftime('%Y-%m-%d'),
        }

        return render(request, 'pdf_forms/revision_loyer_form.html', context)

    # POST : Calculs
    try:
        choix = request.POST.get('choix_indice')

        if choix and choix != "MANUEL":
            val_str, trim_str = choix.split('|')
            nouvel_indice = float(val_str)
            nouveau_trimestre = trim_str
        else:
            nouvel_indice = float(request.POST.get('nouvel_indice_manuel').replace(',', '.'))
            nouveau_trimestre = request.POST.get('nouveau_trimestre_manuel')

        date_app_str = request.POST.get('date_application')
        date_app = datetime.strptime(date_app_str, '%Y-%m-%d').date()
        update_bail = request.POST.get('update_bail') == 'on'

        # Récupérer ancien indice
        tarif_actuel = bail.tarification_actuelle
        ancien_indice = float(tarif_actuel.indice_reference) if tarif_actuel and tarif_actuel.indice_reference else None

        if not ancien_indice or ancien_indice <= 0:
            return HttpResponse("Erreur : L'indice de référence initial du bail n'est pas renseigné.", status=400)

        # Calcul nouveau loyer
        ancien_loyer = float(bail.loyer_hc)
        nouveau_loyer = ancien_loyer * (nouvel_indice / ancien_indice)

        # Si update_bail : rediriger vers assistant
        if update_bail:
            request.session['nouvelle_tarification'] = {
                'bail_id': bail.id,
                'date_application': date_app.strftime('%Y-%m-%d'),
                'nouveau_loyer_hc': round(nouveau_loyer, 2),
                'charges': float(bail.charges),
                'taxes': float(bail.taxes),
                'nouvel_indice': nouvel_indice,
                'nouveau_trimestre': nouveau_trimestre,
                'ancien_loyer': ancien_loyer,
                'ancien_indice': ancien_indice,
                'reason': f"Révision {tarif_actuel.trimestre_reference or 'loyer'} -> {nouveau_trimestre}"
            }

            return redirect('creer_tarification_from_revision', pk=bail.pk)

        # Sinon : générer juste le PDF
        generator = PDFGenerator(bail)
        pdf_content = generator.generer_revision_loyer(
            nouvel_indice, nouveau_trimestre, date_app, ancien_indice
        )

        filename = f"Revision_Loyer_{bail.local.numero_porte}.pdf"

        response = HttpResponse(pdf_content, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'

        logger.info(f"Révision loyer générée: {filename}")
        return response

    except Exception as e:
        logger.exception(f"Erreur génération révision bail {pk}")
        return HttpResponse(f"Erreur: {str(e)}", status=500)


# ============================================================================
# ASSISTANT CRÉATION TARIFICATION (après révision)
# ============================================================================

@staff_member_required
def creer_tarification_from_revision(request, pk):
    """
    Assistant de création de tarification suite à une révision IRL/ILC.
    Affiche un formulaire pré-rempli pour validation manuelle.
    """
    from .models import BailTarification

    bail = get_object_or_404(Bail, pk=pk)
    data = request.session.get('nouvelle_tarification', {})

    if not data or data.get('bail_id') != bail.id:
        return HttpResponse("Erreur: Aucune révision en cours pour ce bail.", status=400)

    if request.method != 'POST':
        # Afficher formulaire pré-rempli
        tarif_actuel = bail.tarification_actuelle
        date_fin_auto = ""
        if tarif_actuel:
            from datetime import timedelta
            date_fin_suggested = datetime.strptime(data['date_application'], '%Y-%m-%d').date() - timedelta(days=1)
            date_fin_auto = date_fin_suggested.strftime('%Y-%m-%d')

        context = {
            'bail': bail,
            'data': data,
            'date_fin_auto': date_fin_auto,
        }

        return render(request, 'pdf_forms/tarification_revision_form.html', context)

    # POST: Créer la tarification
    try:
        # 1. Fermer l'ancienne tarification
        tarif_actuel = bail.tarification_actuelle
        if tarif_actuel:
            date_fin_ancienne = datetime.strptime(request.POST.get('date_fin_ancienne'), '%Y-%m-%d').date()
            tarif_actuel.date_fin = date_fin_ancienne
            tarif_actuel.save()
            logger.info(f"Tarification {tarif_actuel.pk} fermée au {date_fin_ancienne}")

        # 2. Créer nouvelle tarification
        nouvelle_tarif = BailTarification.objects.create(
            bail=bail,
            date_debut=datetime.strptime(request.POST.get('date_debut'), '%Y-%m-%d').date(),
            date_fin=None,
            loyer_hc=float(request.POST.get('loyer_hc')),
            charges=float(request.POST.get('charges')),
            taxes=float(request.POST.get('taxes')),
            indice_reference=float(request.POST.get('indice_reference')),
            trimestre_reference=request.POST.get('trimestre_reference'),
            reason=request.POST.get('reason'),
            notes=f"Révision IRL/ILC. Ancien: {data['ancien_loyer']:.2f}€, Nouvel indice: {data['nouvel_indice']}"
        )

        logger.info(f"Nouvelle tarification {nouvelle_tarif.pk} créée pour bail {bail.pk}")

        # 3. Générer le courrier PDF
        generator = PDFGenerator(bail)
        pdf_content = generator.generer_revision_loyer(
            float(request.POST.get('indice_reference')),
            request.POST.get('trimestre_reference'),
            datetime.strptime(request.POST.get('date_debut'), '%Y-%m-%d').date(),
            data['ancien_indice']
        )

        filename = f"Revision_Loyer_{bail.local.numero_porte}.pdf"

        response = HttpResponse(pdf_content, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'

        # Nettoyer la session
        if 'nouvelle_tarification' in request.session:
            del request.session['nouvelle_tarification']

        return response

    except Exception as e:
        logger.exception(f"Erreur création tarification bail {pk}")
        return HttpResponse(f"Erreur: {str(e)}", status=500)


# ============================================================================
# DASHBOARD PATRIMOINE
# ============================================================================

@staff_member_required
def dashboard_patrimoine(request):
    """
    Dashboard de synthèse du patrimoine immobilier.
    Affiche graphiques et indicateurs globaux.
    Accessible uniquement aux utilisateurs staff.
    """
    import json
    from dateutil.relativedelta import relativedelta

    # Récupérer tous les immeubles
    immeubles = Immeuble.objects.all().prefetch_related('credits', 'locaux__baux', 'estimations')

    # Calculer données pour chaque immeuble
    immeubles_data = []
    total_valeur = 0
    total_crd = 0
    total_cashflow = 0
    total_locaux = 0

    for immeuble in immeubles:
        valeur = PatrimoineCalculator.get_valeur_actuelle(immeuble)
        crd = PatrimoineCalculator.get_capital_restant_du(immeuble)
        cashflow = RentabiliteCalculator.get_cashflow_mensuel(immeuble)
        rendement = RentabiliteCalculator.get_rendement_brut(immeuble)
        nb_locaux = immeuble.locaux.count()

        total_valeur += valeur
        total_crd += crd
        total_cashflow += cashflow
        total_locaux += nb_locaux

        immeubles_data.append({
            'id': immeuble.id,
            'nom': immeuble.nom,
            'regime_fiscal_display': immeuble.get_regime_fiscal_display(),
            'valeur_actuelle': valeur,
            'capital_restant_du': crd,
            'valeur_nette': valeur - crd,
            'rendement_brut': rendement,
            'cashflow': cashflow,
        })

    # Totaux
    totaux = {
        'valeur_totale': total_valeur,
        'crd_total': total_crd,
        'valeur_nette': total_valeur - total_crd,
        'cashflow_total': total_cashflow,
        'nb_immeubles': immeubles.count(),
        'nb_locaux': total_locaux,
    }

    # Données JSON pour les graphiques
    immeubles_json = json.dumps(immeubles_data)

    # Projection sur 10 ans
    today = date.today()
    projection_labels = []
    projection_valeurs = []
    projection_crd = []
    projection_nette = []

    for i in range(0, 11):
        annee = today.year + i
        projection_labels.append(str(annee))

        # Valeur (on garde la même pour simplifier, ou on ajoute une appréciation)
        valeur_projetee = total_valeur * (1.02 ** i)  # +2% par an
        projection_valeurs.append(round(valeur_projetee, 0))

        # CRD (décroissant)
        target_date = date(annee, 12, 31)
        crd_projete = sum(
            credit.get_capital_restant_du_at(target_date)
            for immeuble in immeubles
            for credit in immeuble.credits.all()
        )
        projection_crd.append(round(crd_projete, 0))

        # Valeur nette
        projection_nette.append(round(valeur_projetee - crd_projete, 0))

    projection_json = json.dumps({
        'labels': projection_labels,
        'valeurs': projection_valeurs,
        'crd': projection_crd,
        'nette': projection_nette,
    })

    context = {
        'immeubles': immeubles_data,
        'totaux': totaux,
        'immeubles_json': immeubles_json,
        'projection_json': projection_json,
    }

    return render(request, 'admin/core/dashboard_patrimoine.html', context)


@staff_member_required
def dashboard_immeuble_detail(request, immeuble_id):
    """
    Dashboard détaillé pour un immeuble spécifique.
    Affiche tous les indicateurs de gestion immobilière.
    """
    import json
    from decimal import Decimal
    from .models import CreditImmobilier, VacanceLocative
    from .patrimoine_calculators import FiscaliteCalculator, RatiosCalculator

    immeuble = get_object_or_404(
        Immeuble.objects.prefetch_related(
            'credits', 'locaux__baux__tarifications', 'locaux__baux__occupants',
            'estimations', 'charges_fiscales', 'locaux__vacances'
        ),
        pk=immeuble_id
    )

    annee_courante = date.today().year

    # === INDICATEURS PATRIMONIAUX ===
    valeur_actuelle = PatrimoineCalculator.get_valeur_actuelle(immeuble)
    capital_restant_du = PatrimoineCalculator.get_capital_restant_du(immeuble)
    valeur_nette = PatrimoineCalculator.get_valeur_nette(immeuble)
    plus_value_latente = PatrimoineCalculator.get_plus_value_latente(immeuble)
    cout_acquisition = float(immeuble.prix_achat or 0) + float(immeuble.frais_notaire or 0) + float(immeuble.frais_agence or 0)

    # === INDICATEURS DE SURFACE ET PRIX AU M² ===
    surface_totale = sum(float(local.surface_m2 or 0) for local in immeuble.locaux.all())
    prix_m2_achat = cout_acquisition / surface_totale if surface_totale > 0 else 0
    prix_m2_actuel = valeur_actuelle / surface_totale if surface_totale > 0 else 0

    # === INDICATEURS DE LOYERS ===
    loyers_mensuels = 0
    loyers_annuels = 0
    charges_mensuelles = 0
    nb_locaux_loues = 0
    nb_locaux_vacants = 0

    locaux_details = []
    for local in immeuble.locaux.all():
        bail_actif = local.baux.filter(actif=True).first()
        local_data = {
            'local': local,
            'surface_m2': float(local.surface_m2 or 0),
            'type_local': local.get_type_local_display() if hasattr(local, 'get_type_local_display') else local.type_local,
            'etage': local.etage,
            'bail_actif': bail_actif,
            'loyer_hc': 0,
            'charges': 0,
            'loyer_ttc': 0,
            'loyer_m2': 0,
            'locataire': None,
            'date_debut_bail': None,
        }

        if bail_actif:
            nb_locaux_loues += 1
            tarif = bail_actif.tarification_actuelle
            if tarif:
                loyer_hc = float(tarif.loyer_hc or 0)
                charges = float(tarif.charges or 0)
                loyer_ttc = float(bail_actif.loyer_ttc)

                # Ajuster pour baux trimestriels
                if bail_actif.frequence_paiement == 'TRIMESTRIEL':
                    loyer_mensuel = loyer_ttc / 3
                else:
                    loyer_mensuel = loyer_ttc

                loyers_mensuels += loyer_mensuel
                charges_mensuelles += charges / 3 if bail_actif.frequence_paiement == 'TRIMESTRIEL' else charges

                local_data['loyer_hc'] = loyer_hc
                local_data['charges'] = charges
                local_data['loyer_ttc'] = loyer_ttc
                local_data['loyer_m2'] = loyer_hc / float(local.surface_m2) if local.surface_m2 else 0
                local_data['frequence'] = bail_actif.get_frequence_paiement_display()

            locataire = bail_actif.occupants.filter(role='LOCATAIRE').first()
            local_data['locataire'] = locataire.nom if locataire else "Non renseigné"
            local_data['date_debut_bail'] = bail_actif.date_debut
        else:
            nb_locaux_vacants += 1

        locaux_details.append(local_data)

    loyers_annuels = loyers_mensuels * 12
    loyer_m2_moyen = loyers_mensuels / surface_totale if surface_totale > 0 else 0

    # === INDICATEURS DE RENTABILITÉ ===
    rendement_brut = RentabiliteCalculator.get_rendement_brut(immeuble, annee_courante)
    rendement_net = RentabiliteCalculator.get_rendement_net(immeuble, annee_courante)
    cashflow_mensuel = RentabiliteCalculator.get_cashflow_mensuel(immeuble)
    cashflow_annuel = cashflow_mensuel * 12

    # === INDICATEURS DE CHARGES ===
    charges_annuelles = RentabiliteCalculator.get_charges_annuelles(immeuble, annee_courante)
    interets_annuels = RentabiliteCalculator.get_interets_annuels(immeuble, annee_courante)

    # Détail des charges de l'immeuble (charges fiscales)
    from .models import ChargeFiscale
    charges_immeuble = immeuble.charges_fiscales.filter(annee=annee_courante)
    charges_details = []
    total_charges_immeuble = 0
    for charge in charges_immeuble:
        montant = float(charge.montant or 0)
        total_charges_immeuble += montant
        charges_details.append({
            'type': charge.get_type_charge_display(),
            'montant': montant,
            'description': charge.description if hasattr(charge, 'description') else '',
        })

    # Charges locataires (provisions sur charges encaissées)
    charges_locataires_annuelles = charges_mensuelles * 12
    total_charges_immeuble_mensuel = total_charges_immeuble / 12 if total_charges_immeuble else 0

    # === INDICATEURS DE CRÉDITS ===
    credits = immeuble.credits.all()
    total_mensualites = sum(float(c.mensualite or 0) for c in credits)
    credits_details = []
    for credit in credits:
        credits_details.append({
            'credit': credit,
            'nom_banque': credit.nom_banque,
            'capital_emprunte': float(credit.capital_emprunte),
            'taux': float(credit.taux_interet),
            'mensualite': float(credit.mensualite),
            'capital_restant': float(credit.capital_restant_du),
            'date_fin': credit.date_fin,
            'progression': round((1 - float(credit.capital_restant_du) / float(credit.capital_emprunte)) * 100, 1) if credit.capital_emprunte else 0,
        })

    # === INDICATEURS D'OCCUPATION ===
    taux_occupation = RatiosCalculator.get_taux_occupation(immeuble, annee_courante)
    taux_vacance = RatiosCalculator.get_taux_vacance(immeuble, annee_courante)

    # === RATIOS CLÉS ===
    ratio_endettement = (total_mensualites / loyers_mensuels * 100) if loyers_mensuels > 0 else 0
    multiplicateur_loyer = valeur_actuelle / loyers_annuels if loyers_annuels > 0 else 0  # Années pour rembourser

    # === ÉVOLUTION DE LA VALEUR (pour graphique) ===
    estimations = list(immeuble.estimations.order_by('date_estimation').values('date_estimation', 'valeur_estimee'))
    evolution_valeur = {
        'labels': [e['date_estimation'].strftime('%Y-%m') for e in estimations],
        'valeurs': [float(e['valeur_estimee']) for e in estimations]
    }
    # Ajouter le prix d'achat au début si pas d'estimation
    if immeuble.prix_achat and (not estimations or estimations[0]['valeur_estimee'] != immeuble.prix_achat):
        evolution_valeur['labels'].insert(0, 'Achat')
        evolution_valeur['valeurs'].insert(0, float(immeuble.prix_achat))

    # === PROJECTION CRÉDIT (pour graphique) ===
    projection_crd = []
    today = date.today()
    for i in range(11):
        target_date = date(today.year + i, 12, 31)
        crd = sum(c.get_capital_restant_du_at(target_date) for c in credits)
        projection_crd.append({
            'annee': today.year + i,
            'crd': round(crd, 0),
            'valeur_nette': round(valeur_actuelle * (1.02 ** i) - crd, 0)
        })

    # === CONTEXTE ===
    context = {
        'immeuble': immeuble,
        'annee': annee_courante,

        # Patrimoine
        'valeur_actuelle': valeur_actuelle,
        'capital_restant_du': capital_restant_du,
        'valeur_nette': valeur_nette,
        'plus_value_latente': plus_value_latente,
        'cout_acquisition': cout_acquisition,

        # Surface et prix au m²
        'surface_totale': surface_totale,
        'prix_m2_achat': prix_m2_achat,
        'prix_m2_actuel': prix_m2_actuel,

        # Loyers
        'loyers_mensuels': loyers_mensuels,
        'loyers_annuels': loyers_annuels,
        'charges_mensuelles': charges_mensuelles,
        'loyer_m2_moyen': loyer_m2_moyen,

        # Rentabilité
        'rendement_brut': rendement_brut,
        'rendement_net': rendement_net,
        'cashflow_mensuel': cashflow_mensuel,
        'cashflow_annuel': cashflow_annuel,

        # Charges
        'charges_annuelles': charges_annuelles,
        'interets_annuels': interets_annuels,
        'charges_details': charges_details,
        'total_charges_immeuble': total_charges_immeuble,
        'total_charges_immeuble_mensuel': total_charges_immeuble_mensuel,
        'charges_locataires_annuelles': charges_locataires_annuelles,

        # Occupation
        'nb_locaux': immeuble.locaux.count(),
        'nb_locaux_loues': nb_locaux_loues,
        'nb_locaux_vacants': nb_locaux_vacants,
        'taux_occupation': taux_occupation,
        'taux_vacance': taux_vacance,

        # Ratios
        'ratio_endettement': ratio_endettement,
        'multiplicateur_loyer': multiplicateur_loyer,
        'total_mensualites': total_mensualites,

        # Détails
        'locaux_details': locaux_details,
        'credits_details': credits_details,

        # Données JSON pour graphiques
        'evolution_valeur_json': json.dumps(evolution_valeur),
        'projection_crd_json': json.dumps(projection_crd),
        'locaux_loyers_json': json.dumps([
            {'nom': item['local'].numero_porte, 'loyer': item['loyer_ttc']}
            for item in locaux_details
        ]),
    }

    return render(request, 'admin/core/dashboard_immeuble_detail.html', context)


# ============================================================================
# BILAN FISCAL
# ============================================================================


@staff_member_required
def bilan_fiscal_immeuble(request, immeuble_id):
    """
    Affiche le bilan fiscal d'un immeuble pour une année donnée.
    Calcule automatiquement les intérêts et assurances depuis les échéances de crédit.
    """
    from .patrimoine_calculators import FiscaliteCalculator, RentabiliteCalculator

    immeuble = get_object_or_404(Immeuble, pk=immeuble_id)

    # Année par défaut : année précédente (pour déclaration fiscale)
    annee = int(request.GET.get('annee', date.today().year - 1))

    # Générer le bilan fiscal
    bilan = FiscaliteCalculator.generer_bilan_fiscal(immeuble, annee)

    # Calculer les intérêts et assurances par crédit pour le détail
    credits_details = []
    date_debut = date(annee, 1, 1)
    date_fin = date(annee, 12, 31)

    for credit in immeuble.credits.all():
        echeances_annee = credit.echeances.filter(
            date_echeance__gte=date_debut,
            date_echeance__lte=date_fin
        )
        interets = sum(float(e.interets) for e in echeances_annee)
        assurance = sum(float(e.assurance) for e in echeances_annee)
        capital = sum(float(e.capital_rembourse) for e in echeances_annee)

        credits_details.append({
            'credit': credit,
            'banque': credit.nom_banque,
            'interets': interets,
            'assurance': assurance,
            'capital_rembourse': capital,
            'total': interets + assurance,
            'nb_echeances': echeances_annee.count(),
        })

    # Total intérêts et assurances depuis les crédits
    total_interets_credits = sum(c['interets'] for c in credits_details)
    total_assurance_credits = sum(c['assurance'] for c in credits_details)

    # Charges manuelles saisies
    charges_manuelles = immeuble.charges_fiscales.filter(annee=annee)
    charges_par_type = {}
    for charge in charges_manuelles:
        type_display = charge.get_type_charge_display()
        if type_display not in charges_par_type:
            charges_par_type[type_display] = []
        charges_par_type[type_display].append({
            'libelle': charge.libelle or type_display,
            'montant': float(charge.montant),
        })

    # Années disponibles (pour le sélecteur)
    annees_credits = set()
    for credit in immeuble.credits.all():
        for echeance in credit.echeances.all():
            annees_credits.add(echeance.date_echeance.year)
    annees_disponibles = sorted(annees_credits, reverse=True)
    if not annees_disponibles:
        annees_disponibles = [date.today().year - 1, date.today().year]

    context = {
        'immeuble': immeuble,
        'annee': annee,
        'bilan': bilan,
        'credits_details': credits_details,
        'total_interets_credits': total_interets_credits,
        'total_assurance_credits': total_assurance_credits,
        'charges_par_type': charges_par_type,
        'annees_disponibles': annees_disponibles,
    }

    return render(request, 'admin/core/bilan_fiscal.html', context)


# ============================================================================
# ASSISTANT CRÉDIT IMMOBILIER
# ============================================================================


@staff_member_required
def assistant_credit(request, immeuble_id=None):
    """
    Assistant intelligent pour créer un crédit immobilier.
    Permet de calculer automatiquement les valeurs manquantes.
    """
    from .models import CreditImmobilier
    from decimal import Decimal

    # Récupérer tous les immeubles pour le formulaire
    immeubles = Immeuble.objects.all()

    if request.method == 'POST':
        try:
            # Récupérer les données du formulaire
            immeuble_id = request.POST.get('immeuble')
            nom_banque = request.POST.get('nom_banque')
            numero_pret = request.POST.get('numero_pret', '')
            date_debut = request.POST.get('date_debut')
            type_credit = request.POST.get('type_credit')
            assurance_mensuelle = Decimal(request.POST.get('assurance_mensuelle', 0))

            # Récupérer les valeurs calculées (depuis les champs hidden ou les champs normaux)
            capital_emprunte = Decimal(request.POST.get('capital_emprunte_final') or request.POST.get('capital_emprunte'))
            taux_interet = Decimal(request.POST.get('taux_interet_final') or request.POST.get('taux_interet'))
            duree_mois = int(request.POST.get('duree_mois_final') or request.POST.get('duree_mois'))

            # Créer le crédit
            immeuble = Immeuble.objects.get(pk=immeuble_id)
            credit = CreditImmobilier.objects.create(
                immeuble=immeuble,
                nom_banque=nom_banque,
                numero_pret=numero_pret,
                capital_emprunte=capital_emprunte,
                taux_interet=taux_interet,
                duree_mois=duree_mois,
                date_debut=datetime.strptime(date_debut, '%Y-%m-%d').date(),
                type_credit=type_credit,
                assurance_mensuelle=assurance_mensuelle
            )

            logger.info(f"Crédit créé via assistant: {credit}")

            # Générer automatiquement les échéances
            from .patrimoine_calculators import CreditGenerator
            generator = CreditGenerator(credit)
            nb_echeances = generator.creer_echeances_en_base()
            logger.info(f"Échéancier généré: {nb_echeances} échéances")

            # Rediriger vers l'admin du crédit
            from django.urls import reverse
            url = reverse('admin:core_creditimmobilier_change', args=[credit.pk])
            return redirect(url)

        except Exception as e:
            logger.exception("Erreur lors de la création du crédit")
            return HttpResponse(f"Erreur: {str(e)}", status=500)

    # GET : Afficher le formulaire
    context = {
        'immeubles': immeubles,
    }

    # Si un immeuble_id est fourni, le presélectionner
    if immeuble_id:
        context['selected_immeuble_id'] = immeuble_id

    return render(request, 'credit_forms/assistant_credit.html', context)
