import logging
from datetime import date, datetime
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404

from django import forms as django_forms
from django.http import HttpResponse

from core.models import (
    Immeuble, Local, Bail, BailTarification, Occupant,
    Regularisation, EstimationValeur, CreditImmobilier,
    CleRepartition, QuotePart, Depense, Consommation, Ajustement,
)
from core.forms import (
    DepenseQuickForm, ImmeubleForm, LocalForm, BailForm,
    BailTarificationForm, OccupantForm, EstimationValeurForm,
    CreditImmobilierForm, DepenseForm, CleRepartitionForm,
    QuotePartForm, ConsommationForm, RegularisationForm, AjustementForm,
)
from core.patrimoine_calculators import (
    PatrimoineCalculator, RentabiliteCalculator, RatiosCalculator,
    FiscaliteCalculator, CreditGenerator,
)

logger = logging.getLogger(__name__)
from core.views import generer_periodes_disponibles


def login_view(request):
    """Page de connexion custom."""
    if request.user.is_authenticated:
        return redirect('app_dashboard')

    error = None
    if request.method == 'POST':
        username = request.POST.get('username', '')
        password = request.POST.get('password', '')
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            next_url = request.GET.get('next', 'app_dashboard')
            return redirect(next_url)
        else:
            error = "Identifiants incorrects."

    return render(request, 'app/auth/login.html', {'error': error})


def logout_view(request):
    """Déconnexion."""
    logout(request)
    return redirect('app_login')


@login_required
def dashboard_view(request):
    """Dashboard portfolio : KPIs globaux + cartes immeubles."""
    immeubles = Immeuble.objects.select_related('proprietaire').prefetch_related(
        'locaux__baux__tarifications',
        'locaux__baux__occupants',
        'locaux__vacances',
        'credits',
        'estimations',
    ).order_by('nom')

    immeubles_data = []
    total_valeur = 0
    total_crd = 0
    total_cashflow = 0
    annee = date.today().year

    for immeuble in immeubles:
        valeur = PatrimoineCalculator.get_valeur_actuelle(immeuble)
        crd = PatrimoineCalculator.get_capital_restant_du(immeuble)
        valeur_nette = PatrimoineCalculator.get_valeur_nette(immeuble)
        rendement_brut = RentabiliteCalculator.get_rendement_brut(immeuble)
        rendement_net = RentabiliteCalculator.get_rendement_net(immeuble)
        cashflow = RentabiliteCalculator.get_cashflow_mensuel(immeuble)
        taux_occupation = RatiosCalculator.get_taux_occupation(immeuble, annee)

        total_valeur += valeur or 0
        total_crd += crd or 0
        total_cashflow += cashflow or 0

        immeubles_data.append({
            'immeuble': immeuble,
            'valeur': valeur,
            'crd': crd,
            'valeur_nette': valeur_nette,
            'rendement_brut': rendement_brut,
            'rendement_net': rendement_net,
            'cashflow': cashflow,
            'taux_occupation': taux_occupation,
        })

    context = {
        'immeubles_data': immeubles_data,
        'total_valeur': total_valeur,
        'total_crd': total_crd,
        'total_valeur_nette': total_valeur - total_crd,
        'total_cashflow': total_cashflow,
    }

    return render(request, 'app/dashboard/index.html', context)


# ─── Dépenses ────────────────────────────────────────────────────────────────

@login_required
def depense_quick_add_view(request):
    """Formulaire rapide d'ajout de dépense (mobile-first)."""
    if request.method == 'POST':
        form = DepenseQuickForm(request.POST)
        if form.is_valid():
            depense = form.save()
            messages.success(request, f'Depense "{depense.libelle}" enregistree ({depense.montant} \u20ac).')
            return redirect('app_dashboard')
    else:
        form = DepenseQuickForm(initial={'date': date.today()})

    return render(request, 'app/depenses/quick_add.html', {'form': form})


# ─── Immeubles ───────────────────────────────────────────────────────────────

@login_required
def immeuble_detail_view(request, pk):
    """Vue détaillée d'un immeuble avec onglets."""
    immeuble = get_object_or_404(
        Immeuble.objects.select_related('proprietaire').prefetch_related(
            'locaux__baux__tarifications',
            'locaux__baux__occupants',
            'locaux__vacances',
            'credits',
            'estimations',
            'charges_fiscales',
        ),
        pk=pk,
    )

    annee = date.today().year
    valeur = PatrimoineCalculator.get_valeur_actuelle(immeuble)
    crd = PatrimoineCalculator.get_capital_restant_du(immeuble)

    context = {
        'immeuble': immeuble,
        'valeur': valeur,
        'crd': crd,
        'valeur_nette': PatrimoineCalculator.get_valeur_nette(immeuble),
        'plus_value': PatrimoineCalculator.get_plus_value_latente(immeuble),
        'rendement_brut': RentabiliteCalculator.get_rendement_brut(immeuble),
        'rendement_net': RentabiliteCalculator.get_rendement_net(immeuble),
        'cashflow': RentabiliteCalculator.get_cashflow_mensuel(immeuble),
        'taux_occupation': RatiosCalculator.get_taux_occupation(immeuble, annee),
        'active_tab': request.GET.get('tab', 'general'),
    }

    return render(request, 'app/immeubles/detail.html', context)


@login_required
def immeuble_tab_view(request, pk, tab):
    """Rendu partiel d'un onglet immeuble (HTMX)."""
    immeuble = get_object_or_404(
        Immeuble.objects.select_related('proprietaire').prefetch_related(
            'locaux__baux__tarifications',
            'locaux__baux__occupants',
            'locaux__vacances',
            'credits',
            'estimations',
            'charges_fiscales',
            'depenses__cle_repartition',
            'cles_repartition__quote_parts__local',
            'locaux__consommations__cle_repartition',
        ),
        pk=pk,
    )

    annee = date.today().year
    context = {
        'immeuble': immeuble,
        'valeur': PatrimoineCalculator.get_valeur_actuelle(immeuble),
        'crd': PatrimoineCalculator.get_capital_restant_du(immeuble),
        'valeur_nette': PatrimoineCalculator.get_valeur_nette(immeuble),
        'plus_value': PatrimoineCalculator.get_plus_value_latente(immeuble),
        'rendement_brut': RentabiliteCalculator.get_rendement_brut(immeuble),
        'rendement_net': RentabiliteCalculator.get_rendement_net(immeuble),
        'cashflow': RentabiliteCalculator.get_cashflow_mensuel(immeuble),
        'taux_occupation': RatiosCalculator.get_taux_occupation(immeuble, annee),
    }

    # Données spécifiques par onglet
    if tab == 'locaux':
        locaux_data = []
        for local in immeuble.locaux.all():
            bail_actif = local.baux.filter(actif=True).first()
            locataire = None
            if bail_actif:
                locataire = bail_actif.occupants.filter(role='LOCATAIRE').first()
            locaux_data.append({
                'local': local,
                'bail_actif': bail_actif,
                'locataire': locataire,
            })
        context['locaux_data'] = locaux_data
    elif tab == 'finances':
        context['credits'] = immeuble.credits.all()
        context['charges_annuelles'] = RentabiliteCalculator.get_charges_annuelles(immeuble, annee)
        context['interets_annuels'] = RentabiliteCalculator.get_interets_annuels(immeuble, annee)
        context['depenses'] = immeuble.depenses.order_by('-date')[:20]
        context['cles'] = immeuble.cles_repartition.prefetch_related('quote_parts')
    elif tab == 'consommations':
        context['consommations'] = Consommation.objects.filter(
            local__immeuble=immeuble,
        ).select_related('local', 'cle_repartition').order_by('-date_releve')[:30]

    template = f'app/immeubles/_tab_{tab}.html'
    return render(request, template, context)


# ─── Baux ────────────────────────────────────────────────────────────────────

@login_required
def bail_detail_view(request, pk):
    """Vue detaillee d'un bail avec onglets."""
    bail = get_object_or_404(
        Bail.objects.select_related('local__immeuble__proprietaire').prefetch_related(
            'tarifications',
            'occupants',
            'regularisations',
            'ajustements',
        ),
        pk=pk,
    )

    locataire = bail.occupants.filter(role='LOCATAIRE').first()
    tarif = bail.tarification_actuelle

    context = {
        'bail': bail,
        'locataire': locataire,
        'tarif': tarif,
        'active_tab': request.GET.get('tab', 'info'),
    }

    return render(request, 'app/baux/detail.html', context)


@login_required
def bail_tab_view(request, pk, tab):
    """Rendu partiel d'un onglet bail (HTMX)."""
    bail = get_object_or_404(
        Bail.objects.select_related('local__immeuble__proprietaire').prefetch_related(
            'tarifications',
            'occupants',
            'regularisations',
            'ajustements',
        ),
        pk=pk,
    )

    context = {'bail': bail}

    if tab == 'info':
        context['tarif'] = bail.tarification_actuelle
        context['tarifications'] = bail.tarifications.all()
        context['locataire'] = bail.occupants.filter(role='LOCATAIRE').first()
    elif tab == 'occupants':
        context['locataires'] = bail.occupants.filter(role='LOCATAIRE')
        context['garants'] = bail.occupants.filter(role='GARANT')
    elif tab == 'regularisations':
        context['regularisations'] = bail.regularisations.all()
        context['ajustements'] = bail.ajustements.all()
    elif tab == 'documents':
        context['periodes_disponibles'] = generer_periodes_disponibles(bail)

    template = f'app/baux/_tab_{tab}.html'
    return render(request, template, context)


# ═══════════════════════════════════════════════════════════════════════════════
# CRUD - Vues modals HTMX
# ═══════════════════════════════════════════════════════════════════════════════

def _modal_form_response(request, form, title, action_url, submit_label='Enregistrer'):
    """Helper : rendu d'un formulaire dans la modal."""
    return render(request, 'app/_modal_form.html', {
        'form': form,
        'modal_title': title,
        'form_action': action_url,
        'submit_label': submit_label,
    })


def _modal_success(redirect_url=None):
    """Helper : reponse HTMX apres succes (ferme la modal + reload page)."""
    resp = HttpResponse(status=204)
    resp['HX-Trigger'] = 'closeModal'
    if redirect_url:
        resp['HX-Redirect'] = redirect_url
    else:
        resp['HX-Refresh'] = 'true'
    return resp


# ─── CRUD Immeuble ───────────────────────────────────────────────────────────

@login_required
def immeuble_create_view(request):
    """Creer un immeuble (modal HTMX)."""
    if request.method == 'POST':
        form = ImmeubleForm(request.POST)
        if form.is_valid():
            immeuble = form.save()
            return _modal_success(redirect_url=f'/app/immeubles/{immeuble.pk}/')
    else:
        form = ImmeubleForm()
    return _modal_form_response(request, form, 'Nouvel immeuble', '/app/immeubles/creer/')


@login_required
def immeuble_edit_view(request, pk):
    """Modifier un immeuble (modal HTMX)."""
    immeuble = get_object_or_404(Immeuble, pk=pk)
    if request.method == 'POST':
        form = ImmeubleForm(request.POST, instance=immeuble)
        if form.is_valid():
            form.save()
            return _modal_success()
    else:
        form = ImmeubleForm(instance=immeuble)
    return _modal_form_response(request, form, f'Modifier {immeuble.nom}', f'/app/immeubles/{pk}/modifier/')


@login_required
def immeuble_delete_view(request, pk):
    """Supprimer un immeuble (modal HTMX)."""
    immeuble = get_object_or_404(Immeuble, pk=pk)
    if request.method == 'POST':
        immeuble.delete()
        return _modal_success(redirect_url='/app/')
    return render(request, 'app/_modal_confirm_delete.html', {
        'object': immeuble,
        'delete_action': f'/app/immeubles/{pk}/supprimer/',
    })


# ─── CRUD Local ──────────────────────────────────────────────────────────────

@login_required
def local_create_view(request, immeuble_pk):
    """Creer un local pour un immeuble (modal HTMX)."""
    immeuble = get_object_or_404(Immeuble, pk=immeuble_pk)
    action_url = f'/app/immeubles/{immeuble_pk}/locaux/creer/'
    if request.method == 'POST':
        form = LocalForm(request.POST)
        if form.is_valid():
            form.save()
            return _modal_success()
    else:
        form = LocalForm(initial={'immeuble': immeuble})
    form.fields['immeuble'].widget = django_forms.HiddenInput()
    return _modal_form_response(request, form, f'Nouveau local - {immeuble.nom}', action_url)


@login_required
def local_edit_view(request, pk):
    """Modifier un local (modal HTMX)."""
    local = get_object_or_404(Local, pk=pk)
    action_url = f'/app/locaux/{pk}/modifier/'
    if request.method == 'POST':
        form = LocalForm(request.POST, instance=local)
        if form.is_valid():
            form.save()
            return _modal_success()
    else:
        form = LocalForm(instance=local)
    form.fields['immeuble'].widget = django_forms.HiddenInput()
    return _modal_form_response(request, form, f'Modifier local {local.numero_porte}', action_url)


@login_required
def local_delete_view(request, pk):
    """Supprimer un local (modal HTMX)."""
    local = get_object_or_404(Local, pk=pk)
    if request.method == 'POST':
        local.delete()
        return _modal_success()
    return render(request, 'app/_modal_confirm_delete.html', {
        'object': local,
        'delete_action': f'/app/locaux/{pk}/supprimer/',
    })


# ─── CRUD Bail ───────────────────────────────────────────────────────────────

@login_required
def bail_create_view(request, local_pk):
    """Creer un bail pour un local (modal HTMX)."""
    local = get_object_or_404(Local, pk=local_pk)
    action_url = f'/app/locaux/{local_pk}/baux/creer/'
    if request.method == 'POST':
        form = BailForm(request.POST)
        if form.is_valid():
            bail = form.save()
            return _modal_success(redirect_url=f'/app/baux/{bail.pk}/')
    else:
        form = BailForm(initial={'local': local, 'date_debut': date.today()})
    form.fields['local'].widget = django_forms.HiddenInput()
    return _modal_form_response(request, form, f'Nouveau bail - {local}', action_url)


@login_required
def bail_edit_view(request, pk):
    """Modifier un bail (modal HTMX)."""
    bail = get_object_or_404(Bail, pk=pk)
    action_url = f'/app/baux/{pk}/modifier/'
    if request.method == 'POST':
        form = BailForm(request.POST, instance=bail)
        if form.is_valid():
            form.save()
            return _modal_success()
    else:
        form = BailForm(instance=bail)
    form.fields['local'].widget = django_forms.HiddenInput()
    return _modal_form_response(request, form, f'Modifier bail {bail.local.numero_porte}', action_url)


# ─── CRUD BailTarification ──────────────────────────────────────────────────

@login_required
def tarification_create_view(request, bail_pk):
    """Creer une tarification pour un bail (modal HTMX)."""
    bail = get_object_or_404(Bail, pk=bail_pk)
    action_url = f'/app/baux/{bail_pk}/tarifications/creer/'
    if request.method == 'POST':
        form = BailTarificationForm(request.POST)
        if form.is_valid():
            form.save()
            return _modal_success()
    else:
        form = BailTarificationForm(initial={
            'bail': bail,
            'date_debut': date.today(),
        })
    form.fields['bail'].widget = django_forms.HiddenInput()
    return _modal_form_response(request, form, 'Nouvelle tarification', action_url)


# ─── CRUD Occupant ───────────────────────────────────────────────────────────

@login_required
def occupant_create_view(request, bail_pk):
    """Creer un occupant pour un bail (modal HTMX)."""
    bail = get_object_or_404(Bail, pk=bail_pk)
    action_url = f'/app/baux/{bail_pk}/occupants/creer/'
    if request.method == 'POST':
        form = OccupantForm(request.POST)
        if form.is_valid():
            form.save()
            return _modal_success()
    else:
        form = OccupantForm(initial={'bail': bail})
    form.fields['bail'].widget = django_forms.HiddenInput()
    return _modal_form_response(request, form, 'Nouvel occupant', action_url)


@login_required
def occupant_edit_view(request, pk):
    """Modifier un occupant (modal HTMX)."""
    occupant = get_object_or_404(Occupant, pk=pk)
    action_url = f'/app/occupants/{pk}/modifier/'
    if request.method == 'POST':
        form = OccupantForm(request.POST, instance=occupant)
        if form.is_valid():
            form.save()
            return _modal_success()
    else:
        form = OccupantForm(instance=occupant)
    form.fields['bail'].widget = django_forms.HiddenInput()
    return _modal_form_response(request, form, f'Modifier {occupant.nom} {occupant.prenom}', action_url)


@login_required
def occupant_delete_view(request, pk):
    """Supprimer un occupant (modal HTMX)."""
    occupant = get_object_or_404(Occupant, pk=pk)
    if request.method == 'POST':
        occupant.delete()
        return _modal_success()
    return render(request, 'app/_modal_confirm_delete.html', {
        'object': occupant,
        'delete_action': f'/app/occupants/{pk}/supprimer/',
    })


# ─── CRUD EstimationValeur ──────────────────────────────────────────────────

@login_required
def estimation_create_view(request, immeuble_pk):
    """Creer une estimation pour un immeuble (modal HTMX)."""
    immeuble = get_object_or_404(Immeuble, pk=immeuble_pk)
    action_url = f'/app/immeubles/{immeuble_pk}/estimations/creer/'
    if request.method == 'POST':
        form = EstimationValeurForm(request.POST)
        if form.is_valid():
            form.save()
            return _modal_success()
    else:
        form = EstimationValeurForm(initial={
            'immeuble': immeuble,
            'date_estimation': date.today(),
        })
    form.fields['immeuble'].widget = django_forms.HiddenInput()
    return _modal_form_response(request, form, f'Nouvelle estimation - {immeuble.nom}', action_url)


@login_required
def estimation_delete_view(request, pk):
    """Supprimer une estimation (modal HTMX)."""
    estimation = get_object_or_404(EstimationValeur, pk=pk)
    if request.method == 'POST':
        estimation.delete()
        return _modal_success()
    return render(request, 'app/_modal_confirm_delete.html', {
        'object': estimation,
        'delete_action': f'/app/estimations/{pk}/supprimer/',
    })


# ─── CRUD CreditImmobilier ──────────────────────────────────────────────────

@login_required
def credit_create_view(request, immeuble_pk):
    """Assistant interactif pour creer un credit immobilier."""
    immeuble = get_object_or_404(Immeuble, pk=immeuble_pk)

    if request.method == 'POST':
        try:
            nom_banque = request.POST.get('nom_banque', '').strip()
            numero_pret = request.POST.get('numero_pret', '').strip()
            date_debut_str = request.POST.get('date_debut')
            type_credit = request.POST.get('type_credit', 'AMORTISSABLE')
            assurance_mensuelle = Decimal(request.POST.get('assurance_mensuelle') or '0')

            capital = Decimal(request.POST.get('capital_emprunte_final') or request.POST.get('capital_emprunte'))
            taux = Decimal(request.POST.get('taux_interet_final') or request.POST.get('taux_interet'))
            duree = int(request.POST.get('duree_mois_final') or request.POST.get('duree_mois'))

            credit = CreditImmobilier.objects.create(
                immeuble=immeuble,
                nom_banque=nom_banque,
                numero_pret=numero_pret,
                capital_emprunte=capital,
                taux_interet=taux,
                duree_mois=duree,
                date_debut=datetime.strptime(date_debut_str, '%Y-%m-%d').date(),
                type_credit=type_credit,
                assurance_mensuelle=assurance_mensuelle,
            )

            generator = CreditGenerator(credit)
            generator.creer_echeances_en_base()

            messages.success(request, f'Credit {nom_banque} cree avec succes ({credit.echeances.count()} echeances generees).')
            return redirect('app_immeuble_detail', pk=immeuble.pk)

        except Exception as e:
            logger.exception("Erreur lors de la creation du credit via assistant")
            messages.error(request, f'Erreur lors de la creation du credit : {e}')

    return render(request, 'app/credits/assistant.html', {'immeuble': immeuble})


@login_required
def credit_edit_view(request, pk):
    """Modifier un credit (modal HTMX)."""
    credit = get_object_or_404(CreditImmobilier, pk=pk)
    action_url = f'/app/credits/{pk}/modifier/'
    if request.method == 'POST':
        form = CreditImmobilierForm(request.POST, instance=credit)
        if form.is_valid():
            form.save()
            return _modal_success()
    else:
        form = CreditImmobilierForm(instance=credit)
    form.fields['immeuble'].widget = django_forms.HiddenInput()
    return _modal_form_response(request, form, f'Modifier credit {credit.nom_banque}', action_url)


@login_required
def credit_delete_view(request, pk):
    """Supprimer un credit (modal HTMX)."""
    credit = get_object_or_404(CreditImmobilier, pk=pk)
    if request.method == 'POST':
        credit.delete()
        return _modal_success()
    return render(request, 'app/_modal_confirm_delete.html', {
        'object': credit,
        'delete_action': f'/app/credits/{pk}/supprimer/',
    })


# ─── CRUD Depense (complet) ────────────────────────────────────────────────

@login_required
def depense_create_view(request, immeuble_pk):
    """Creer une depense pour un immeuble (modal HTMX)."""
    immeuble = get_object_or_404(Immeuble, pk=immeuble_pk)
    action_url = f'/app/immeubles/{immeuble_pk}/depenses/creer/'
    if request.method == 'POST':
        form = DepenseForm(request.POST, immeuble=immeuble)
        if form.is_valid():
            form.save()
            return _modal_success()
    else:
        form = DepenseForm(initial={'immeuble': immeuble, 'date': date.today()}, immeuble=immeuble)
    form.fields['immeuble'].widget = django_forms.HiddenInput()
    return _modal_form_response(request, form, f'Nouvelle depense - {immeuble.nom}', action_url)


@login_required
def depense_edit_view(request, pk):
    """Modifier une depense (modal HTMX)."""
    depense = get_object_or_404(Depense, pk=pk)
    action_url = f'/app/depenses/{pk}/modifier/'
    if request.method == 'POST':
        form = DepenseForm(request.POST, instance=depense, immeuble=depense.immeuble)
        if form.is_valid():
            form.save()
            return _modal_success()
    else:
        form = DepenseForm(instance=depense, immeuble=depense.immeuble)
    form.fields['immeuble'].widget = django_forms.HiddenInput()
    return _modal_form_response(request, form, f'Modifier depense', action_url)


@login_required
def depense_delete_view(request, pk):
    """Supprimer une depense (modal HTMX)."""
    depense = get_object_or_404(Depense, pk=pk)
    if request.method == 'POST':
        depense.delete()
        return _modal_success()
    return render(request, 'app/_modal_confirm_delete.html', {
        'object': depense,
        'delete_action': f'/app/depenses/{pk}/supprimer/',
    })


# ─── CRUD CleRepartition ──────────────────────────────────────────────────

@login_required
def cle_create_view(request, immeuble_pk):
    """Creer une cle de repartition pour un immeuble (modal HTMX)."""
    immeuble = get_object_or_404(Immeuble, pk=immeuble_pk)
    action_url = f'/app/immeubles/{immeuble_pk}/cles/creer/'
    if request.method == 'POST':
        form = CleRepartitionForm(request.POST)
        if form.is_valid():
            form.save()
            return _modal_success()
    else:
        form = CleRepartitionForm(initial={'immeuble': immeuble})
    form.fields['immeuble'].widget = django_forms.HiddenInput()
    return _modal_form_response(request, form, f'Nouvelle cle - {immeuble.nom}', action_url)


@login_required
def cle_edit_view(request, pk):
    """Modifier une cle de repartition (modal HTMX)."""
    cle = get_object_or_404(CleRepartition, pk=pk)
    action_url = f'/app/cles/{pk}/modifier/'
    if request.method == 'POST':
        form = CleRepartitionForm(request.POST, instance=cle)
        if form.is_valid():
            form.save()
            return _modal_success()
    else:
        form = CleRepartitionForm(instance=cle)
    form.fields['immeuble'].widget = django_forms.HiddenInput()
    return _modal_form_response(request, form, f'Modifier {cle.nom}', action_url)


@login_required
def cle_delete_view(request, pk):
    """Supprimer une cle de repartition (modal HTMX)."""
    cle = get_object_or_404(CleRepartition, pk=pk)
    if request.method == 'POST':
        cle.delete()
        return _modal_success()
    return render(request, 'app/_modal_confirm_delete.html', {
        'object': cle,
        'delete_action': f'/app/cles/{pk}/supprimer/',
    })


# ─── CRUD QuotePart ────────────────────────────────────────────────────────

@login_required
def quotepart_create_view(request, cle_pk):
    """Creer une quote-part pour une cle (modal HTMX)."""
    cle = get_object_or_404(CleRepartition, pk=cle_pk)
    action_url = f'/app/cles/{cle_pk}/quotesparts/creer/'
    if request.method == 'POST':
        form = QuotePartForm(request.POST, cle=cle)
        if form.is_valid():
            form.save()
            return _modal_success()
    else:
        form = QuotePartForm(initial={'cle': cle}, cle=cle)
    form.fields['cle'].widget = django_forms.HiddenInput()
    return _modal_form_response(request, form, f'Nouvelle quote-part - {cle.nom}', action_url)


@login_required
def quotepart_edit_view(request, pk):
    """Modifier une quote-part (modal HTMX)."""
    qp = get_object_or_404(QuotePart, pk=pk)
    action_url = f'/app/quotesparts/{pk}/modifier/'
    if request.method == 'POST':
        form = QuotePartForm(request.POST, instance=qp, cle=qp.cle)
        if form.is_valid():
            form.save()
            return _modal_success()
    else:
        form = QuotePartForm(instance=qp, cle=qp.cle)
    form.fields['cle'].widget = django_forms.HiddenInput()
    return _modal_form_response(request, form, f'Modifier quote-part {qp.local}', action_url)


@login_required
def quotepart_delete_view(request, pk):
    """Supprimer une quote-part (modal HTMX)."""
    qp = get_object_or_404(QuotePart, pk=pk)
    if request.method == 'POST':
        qp.delete()
        return _modal_success()
    return render(request, 'app/_modal_confirm_delete.html', {
        'object': qp,
        'delete_action': f'/app/quotesparts/{pk}/supprimer/',
    })


# ─── CRUD Consommation ─────────────────────────────────────────────────────

@login_required
def consommation_create_view(request, immeuble_pk):
    """Creer un releve compteur (modal HTMX)."""
    immeuble = get_object_or_404(Immeuble, pk=immeuble_pk)
    action_url = f'/app/immeubles/{immeuble_pk}/consommations/creer/'
    if request.method == 'POST':
        form = ConsommationForm(request.POST, immeuble=immeuble)
        if form.is_valid():
            form.save()
            return _modal_success()
    else:
        form = ConsommationForm(immeuble=immeuble)
    return _modal_form_response(request, form, f'Nouveau releve - {immeuble.nom}', action_url)


@login_required
def consommation_edit_view(request, pk):
    """Modifier un releve compteur (modal HTMX)."""
    conso = get_object_or_404(Consommation, pk=pk)
    action_url = f'/app/consommations/{pk}/modifier/'
    if request.method == 'POST':
        form = ConsommationForm(request.POST, instance=conso, immeuble=conso.local.immeuble)
        if form.is_valid():
            form.save()
            return _modal_success()
    else:
        form = ConsommationForm(instance=conso, immeuble=conso.local.immeuble)
    return _modal_form_response(request, form, 'Modifier releve compteur', action_url)


@login_required
def consommation_delete_view(request, pk):
    """Supprimer un releve compteur (modal HTMX)."""
    conso = get_object_or_404(Consommation, pk=pk)
    if request.method == 'POST':
        conso.delete()
        return _modal_success()
    return render(request, 'app/_modal_confirm_delete.html', {
        'object': conso,
        'delete_action': f'/app/consommations/{pk}/supprimer/',
    })


# ─── CRUD Regularisation ──────────────────────────────────────────────────

@login_required
def regularisation_create_view(request, bail_pk):
    """Creer une regularisation pour un bail (modal HTMX)."""
    bail = get_object_or_404(Bail, pk=bail_pk)
    action_url = f'/app/baux/{bail_pk}/regularisations/creer/'
    if request.method == 'POST':
        form = RegularisationForm(request.POST)
        if form.is_valid():
            form.save()
            return _modal_success()
    else:
        form = RegularisationForm(initial={'bail': bail})
    form.fields['bail'].widget = django_forms.HiddenInput()
    return _modal_form_response(request, form, 'Nouvelle regularisation', action_url)


@login_required
def regularisation_edit_view(request, pk):
    """Modifier une regularisation (modal HTMX)."""
    regul = get_object_or_404(Regularisation, pk=pk)
    action_url = f'/app/regularisations/{pk}/modifier/'
    if request.method == 'POST':
        form = RegularisationForm(request.POST, instance=regul)
        if form.is_valid():
            form.save()
            return _modal_success()
    else:
        form = RegularisationForm(instance=regul)
    form.fields['bail'].widget = django_forms.HiddenInput()
    return _modal_form_response(request, form, 'Modifier regularisation', action_url)


@login_required
def regularisation_delete_view(request, pk):
    """Supprimer une regularisation (modal HTMX)."""
    regul = get_object_or_404(Regularisation, pk=pk)
    if request.method == 'POST':
        regul.delete()
        return _modal_success()
    return render(request, 'app/_modal_confirm_delete.html', {
        'object': regul,
        'delete_action': f'/app/regularisations/{pk}/supprimer/',
    })


# ─── CRUD Ajustement ──────────────────────────────────────────────────────

@login_required
def ajustement_create_view(request, bail_pk):
    """Creer un ajustement pour un bail (modal HTMX)."""
    bail = get_object_or_404(Bail, pk=bail_pk)
    action_url = f'/app/baux/{bail_pk}/ajustements/creer/'
    if request.method == 'POST':
        form = AjustementForm(request.POST)
        if form.is_valid():
            form.save()
            return _modal_success()
    else:
        form = AjustementForm(initial={'bail': bail, 'date': date.today()})
    form.fields['bail'].widget = django_forms.HiddenInput()
    return _modal_form_response(request, form, 'Nouvel ajustement', action_url)


@login_required
def ajustement_edit_view(request, pk):
    """Modifier un ajustement (modal HTMX)."""
    ajust = get_object_or_404(Ajustement, pk=pk)
    action_url = f'/app/ajustements/{pk}/modifier/'
    if request.method == 'POST':
        form = AjustementForm(request.POST, instance=ajust)
        if form.is_valid():
            form.save()
            return _modal_success()
    else:
        form = AjustementForm(instance=ajust)
    form.fields['bail'].widget = django_forms.HiddenInput()
    return _modal_form_response(request, form, f'Modifier ajustement', action_url)


@login_required
def ajustement_delete_view(request, pk):
    """Supprimer un ajustement (modal HTMX)."""
    ajust = get_object_or_404(Ajustement, pk=pk)
    if request.method == 'POST':
        ajust.delete()
        return _modal_success()
    return render(request, 'app/_modal_confirm_delete.html', {
        'object': ajust,
        'delete_action': f'/app/ajustements/{pk}/supprimer/',
    })


# ─── Vue detail Cle de repartition ─────────────────────────────────────────

@login_required
def cle_detail_view(request, pk):
    """Vue detaillee d'une cle de repartition avec ses quotes-parts."""
    cle = get_object_or_404(
        CleRepartition.objects.select_related('immeuble').prefetch_related(
            'quote_parts__local',
        ),
        pk=pk,
    )
    total_tantiemes = sum(float(qp.valeur) for qp in cle.quote_parts.all())
    quotes_data = []
    for qp in cle.quote_parts.all():
        pct = (float(qp.valeur) / total_tantiemes * 100) if total_tantiemes else 0
        quotes_data.append({
            'qp': qp,
            'pourcentage': round(pct, 1),
        })

    context = {
        'cle': cle,
        'immeuble': cle.immeuble,
        'quotes_data': quotes_data,
        'total_tantiemes': total_tantiemes,
    }
    return render(request, 'app/charges/cle_detail.html', context)


# ═══════════════════════════════════════════════════════════════════════════════
# Patrimoine
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
def patrimoine_dashboard_view(request):
    """Dashboard patrimoine global avec graphiques."""
    import json
    from dateutil.relativedelta import relativedelta

    immeubles = Immeuble.objects.all().prefetch_related(
        'credits', 'locaux__baux__tarifications', 'estimations',
    )

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
            'valeur_actuelle': valeur,
            'capital_restant_du': crd,
            'valeur_nette': valeur - crd,
            'rendement_brut': rendement,
            'cashflow': cashflow,
        })

    # Projection 10 ans
    today = date.today()
    projection_labels = []
    projection_valeurs = []
    projection_crd = []
    projection_nette = []

    for i in range(11):
        annee = today.year + i
        projection_labels.append(str(annee))
        valeur_projetee = total_valeur * (1.02 ** i)
        projection_valeurs.append(round(valeur_projetee, 0))
        target_date = date(annee, 12, 31)
        crd_projete = sum(
            credit.get_capital_restant_du_at(target_date)
            for immeuble in immeubles
            for credit in immeuble.credits.all()
        )
        projection_crd.append(round(crd_projete, 0))
        projection_nette.append(round(valeur_projetee - crd_projete, 0))

    context = {
        'immeubles_data': immeubles_data,
        'total_valeur': total_valeur,
        'total_crd': total_crd,
        'total_valeur_nette': total_valeur - total_crd,
        'total_cashflow': total_cashflow,
        'nb_immeubles': immeubles.count(),
        'nb_locaux': total_locaux,
        'immeubles_json': json.dumps(immeubles_data),
        'projection_json': json.dumps({
            'labels': projection_labels,
            'valeurs': projection_valeurs,
            'crd': projection_crd,
            'nette': projection_nette,
        }),
    }

    return render(request, 'app/patrimoine/dashboard.html', context)


@login_required
def bilan_fiscal_view(request, pk):
    """Bilan fiscal d'un immeuble pour une annee donnee."""
    immeuble = get_object_or_404(
        Immeuble.objects.prefetch_related('credits__echeances', 'charges_fiscales'),
        pk=pk,
    )

    annee = int(request.GET.get('annee', date.today().year - 1))
    bilan = FiscaliteCalculator.generer_bilan_fiscal(immeuble, annee)

    # Detail credits
    date_debut = date(annee, 1, 1)
    date_fin = date(annee, 12, 31)
    credits_details = []
    for credit in immeuble.credits.all():
        echeances_annee = credit.echeances.filter(
            date_echeance__gte=date_debut, date_echeance__lte=date_fin,
        )
        interets = sum(float(e.interets) for e in echeances_annee)
        assurance = sum(float(e.assurance) for e in echeances_annee)
        credits_details.append({
            'banque': credit.nom_banque,
            'nb_echeances': echeances_annee.count(),
            'interets': interets,
            'assurance': assurance,
            'total': interets + assurance,
        })

    total_interets = sum(c['interets'] for c in credits_details)
    total_assurance = sum(c['assurance'] for c in credits_details)

    # Charges manuelles
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

    # Annees disponibles
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
        'total_interets': total_interets,
        'total_assurance': total_assurance,
        'charges_par_type': charges_par_type,
        'annees_disponibles': annees_disponibles,
    }

    return render(request, 'app/patrimoine/bilan_fiscal.html', context)
