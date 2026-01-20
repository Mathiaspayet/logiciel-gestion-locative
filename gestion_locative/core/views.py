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
from rest_framework import viewsets

from .models import Immeuble, Bail, Local
from .serializers import ImmeubleSerializer, BailSerializer
from .pdf_generator import PDFGenerator
from .calculators import BailCalculator
from .exceptions import TarificationNotFoundError
from .patrimoine_calculators import PatrimoineCalculator, RentabiliteCalculator

# Configuration logging
logger = logging.getLogger(__name__)


# ============================================================================
# API VIEWSETS (inchangés)
# ============================================================================

class ImmeubleViewSet(viewsets.ModelViewSet):
    queryset = Immeuble.objects.all()
    serializer_class = ImmeubleSerializer


class BailViewSet(viewsets.ModelViewSet):
    queryset = Bail.objects.all()
    serializer_class = BailSerializer


# ============================================================================
# HELPERS
# ============================================================================

def generer_periodes_disponibles(bail, nb_periodes=24):
    """
    Génère la liste des périodes disponibles pour un bail.

    Args:
        bail: Instance de Bail
        nb_periodes: Nombre de périodes à générer (défaut: 24 pour 2 ans)

    Returns:
        list: Liste de dict {label, value}
    """
    periodes = []
    today = date.today()

    # Démarrer au 1er du mois actuel
    current = date(today.year, today.month, 1)

    if bail.frequence_paiement == 'TRIMESTRIEL':
        # Trimestres
        for i in range(nb_periodes // 3):
            # Premier mois du trimestre
            label = current.strftime('%B %Y - Trimestre')
            periodes.append({
                'label': label.capitalize(),
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
        # Mensuels
        for i in range(nb_periodes):
            label = current.strftime('%B %Y')
            periodes.append({
                'label': label.capitalize(),
                'value': current.strftime('%Y-%m-%d')
            })

            # Mois précédent
            month = current.month - 1
            year = current.year
            if month < 1:
                month = 12
                year -= 1
            current = date(year, month, 1)

    return list(reversed(periodes))  # Plus récent en dernier


# ============================================================================
# VUES PDF (Refactorisées)
# ============================================================================

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
            'periodes_disponibles': generer_periodes_disponibles(bail)
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
            'periodes_disponibles': generer_periodes_disponibles(bail, nb_periodes=12)  # 12 périodes futures
        }

        return render(request, 'pdf_forms/quittance_form.html', context)  # Même template

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

from django.contrib.admin.views.decorators import staff_member_required


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
