from django.contrib import admin
from django.shortcuts import redirect
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.db.models import Sum, Count, Q
from django.http import HttpResponse
from django.forms import BaseInlineFormSet, ValidationError
from datetime import date
import zipfile
from io import BytesIO
import logging

from .models import (
    Immeuble, Local, Bail, Occupant, Proprietaire, CleRepartition, QuotePart,
    Depense, Consommation, Ajustement, Regularisation, BailTarification,
    EstimationValeur, CreditImmobilier, EcheanceCredit, ChargeFiscale,
    Amortissement, VacanceLocative
)
from .patrimoine_calculators import (
    PatrimoineCalculator, RentabiliteCalculator, CreditGenerator
)

logger = logging.getLogger(__name__)

# Personnalisation de l'interface (complétée par Jazzmin dans settings.py)
admin.site.site_header = "Gestion Locative & Patrimoine"
admin.site.site_title = "Administration Immobilière"
admin.site.index_title = "Tableau de Bord"

class OccupantInline(admin.TabularInline):
    model = Occupant
    extra = 1

class BailInline(admin.StackedInline):
    model = Bail
    extra = 0

class AjustementInline(admin.TabularInline):
    model = Ajustement
    extra = 0

class QuotePartInline(admin.TabularInline):
    model = QuotePart
    extra = 0


# === INLINES PATRIMOINE ===

class EstimationValeurInline(admin.TabularInline):
    model = EstimationValeur
    extra = 0
    fields = ('date_estimation', 'valeur_estimee', 'source', 'notes')
    ordering = ['-date_estimation']


class CreditImmobilierInline(admin.TabularInline):
    model = CreditImmobilier
    extra = 0
    fields = ('nom_banque', 'capital_emprunte', 'taux_interet', 'duree_mois', 'date_debut', 'type_credit', 'get_mensualite', 'get_crd')
    readonly_fields = ('get_mensualite', 'get_crd')
    show_change_link = True

    def get_mensualite(self, obj):
        if obj.pk:
            return f"{obj.mensualite:.2f} €"
        return "-"
    get_mensualite.short_description = "Mensualité"

    def get_crd(self, obj):
        if obj.pk:
            return f"{obj.capital_restant_du:.2f} €"
        return "-"
    get_crd.short_description = "CRD actuel"


class ChargeFiscaleInline(admin.TabularInline):
    model = ChargeFiscale
    extra = 0
    fields = ('annee', 'type_charge', 'montant', 'libelle')
    ordering = ['-annee', 'type_charge']


class EcheanceInline(admin.TabularInline):
    model = EcheanceCredit
    extra = 0
    fields = ('numero_echeance', 'date_echeance', 'capital_rembourse', 'interets', 'assurance', 'capital_restant_du', 'payee')
    readonly_fields = ('numero_echeance', 'date_echeance', 'capital_rembourse', 'interets', 'assurance', 'capital_restant_du')
    ordering = ['numero_echeance']
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


class AmortissementInline(admin.TabularInline):
    model = Amortissement
    extra = 0
    fields = ('type_bien', 'libelle', 'valeur_origine', 'date_mise_service', 'duree_amortissement', 'get_dotation')
    readonly_fields = ('get_dotation',)

    def get_dotation(self, obj):
        if obj.pk:
            return f"{obj.dotation_annuelle:.2f} €/an"
        return "-"
    get_dotation.short_description = "Dotation annuelle"


class VacanceLocativeInline(admin.TabularInline):
    model = VacanceLocative
    extra = 0
    fields = ('date_debut', 'date_fin', 'motif', 'duree_jours')
    readonly_fields = ('duree_jours',)

    def duree_jours(self, obj):
        if obj.pk:
            return f"{obj.duree_jours} jours"
        return "-"
    duree_jours.short_description = "Durée"


class RegularisationInline(admin.TabularInline):
    model = Regularisation
    extra = 0
    readonly_fields = ('date_creation', 'date_debut', 'date_fin', 'montant_reel', 'montant_provisions', 'solde')
    fields = ('date_creation', 'date_debut', 'date_fin', 'montant_reel', 'montant_provisions', 'solde', 'payee', 'date_paiement', 'notes')
    can_delete = False # On garde l'historique


class BailTarificationFormSet(BaseInlineFormSet):
    """FormSet personnalisé pour valider les chevauchements de tarifications.

    Contrairement à la validation dans le modèle, ce formset voit TOUTES les
    tarifications en cours de modification (y compris celles pas encore sauvegardées).
    """

    def clean(self):
        super().clean()

        # Collecter toutes les tarifications valides (non supprimées)
        tarifications = []
        for form in self.forms:
            if form.cleaned_data and not form.cleaned_data.get('DELETE', False):
                tarifications.append({
                    'date_debut': form.cleaned_data.get('date_debut'),
                    'date_fin': form.cleaned_data.get('date_fin'),
                    'form': form,
                })

        # Vérifier les chevauchements entre tarifications
        for i, t1 in enumerate(tarifications):
            if not t1['date_debut']:
                continue
            for t2 in tarifications[i + 1:]:
                if not t2['date_debut']:
                    continue
                if self._periods_overlap(t1, t2):
                    raise ValidationError(
                        f"Chevauchement détecté entre la tarification du "
                        f"{t1['date_debut'].strftime('%d/%m/%Y')} et celle du "
                        f"{t2['date_debut'].strftime('%d/%m/%Y')}."
                    )

    def _periods_overlap(self, t1, t2):
        """Vérifie si deux périodes se chevauchent."""
        # Utiliser une date très lointaine pour les périodes sans fin
        far_future = date(9999, 12, 31)
        t1_fin = t1['date_fin'] if t1['date_fin'] else far_future
        t2_fin = t2['date_fin'] if t2['date_fin'] else far_future

        # Deux périodes se chevauchent si elles ne sont PAS disjointes
        # Disjointes si: t1 finit avant t2 commence OU t2 finit avant t1 commence
        return not (t1_fin < t2['date_debut'] or t2_fin < t1['date_debut'])


class BailTarificationInline(admin.TabularInline):
    model = BailTarification
    formset = BailTarificationFormSet
    extra = 0
    fields = ('get_statut', 'date_debut', 'date_fin', 'loyer_hc', 'charges', 'taxes', 'indice_reference', 'trimestre_reference', 'reason', 'created_at')
    readonly_fields = ('created_at', 'get_statut')
    ordering = ['-date_debut']

    def get_statut(self, obj):
        """Affiche le statut (ACTIVE/FERMÉE) avec badge coloré."""
        if obj.date_fin is None:
            return mark_safe(
                '<span style="background-color: #28a745; color: white; padding: 3px 8px; border-radius: 3px; font-weight: bold; font-size: 11px;">● ACTIVE</span>'
            )
        else:
            return mark_safe(
                '<span style="background-color: #6c757d; color: white; padding: 3px 8px; border-radius: 3px; font-size: 11px;">○ Fermée</span>'
            )
    get_statut.short_description = 'Statut'

@admin.register(Regularisation)
class RegularisationAdmin(admin.ModelAdmin):
    list_display = ('bail', 'date_debut', 'date_fin', 'solde', 'payee', 'date_paiement', 'date_creation')
    list_filter = ('payee', 'date_creation', 'bail__local__immeuble')
    readonly_fields = ('bail', 'date_creation', 'date_debut', 'date_fin', 'montant_reel', 'montant_provisions', 'solde')
    fields = (
        ('bail', 'date_creation'),
        ('date_debut', 'date_fin'),
        ('montant_reel', 'montant_provisions', 'solde'),
        ('payee', 'date_paiement'),
        'notes'
    )
    search_fields = ('bail__local__numero_porte', 'bail__local__immeuble__nom')

    @admin.action(description='Marquer comme payée (date = aujourd\'hui)')
    def marquer_payee(self, request, queryset):
        from django.utils import timezone
        updated = queryset.update(payee=True, date_paiement=timezone.now().date())
        self.message_user(request, f'{updated} régularisation(s) marquée(s) comme payée(s).')

    actions = ['marquer_payee']

@admin.register(Local)
class LocalAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'type_local', 'surface_m2', 'immeuble')
    list_filter = ('immeuble', 'type_local')
    search_fields = ('numero_porte', 'immeuble__nom')
    inlines = [BailInline, VacanceLocativeInline]

@admin.register(Bail)
class BailAdmin(admin.ModelAdmin):
    list_display = ('local', 'get_locataire', 'date_debut', 'get_loyer_hc', 'get_charges', 'get_taxes', 'type_charges', 'frequence_paiement', 'get_actif_badge')

    # Filtres avancés
    list_filter = (
        'actif',
        'frequence_paiement',
        'type_charges',
        'soumis_tva',
        ('date_debut', admin.DateFieldListFilter),
        'local__immeuble',
    )

    # Recherche améliorée
    search_fields = (
        'local__numero_porte',
        'local__immeuble__nom',
        'local__immeuble__ville',
        'occupants__nom',
        'occupants__prenom',
    )

    # Navigation chronologique
    date_hierarchy = 'date_debut'

    inlines = [BailTarificationInline, OccupantInline, AjustementInline, RegularisationInline]

    actions = [
        'imprimer_quittance',
        'imprimer_avis_echeance',
        'imprimer_regularisation',
        'imprimer_solde_tout_compte',
        'imprimer_revision_loyer',
        'generer_quittances_zip',
        'verifier_continuite_tarifications',
    ]

    def get_queryset(self, request):
        """Optimisation des requêtes avec select_related et prefetch_related."""
        qs = super().get_queryset(request)
        return qs.select_related(
            'local__immeuble__proprietaire'
        ).prefetch_related(
            'tarifications',
            'occupants'
        )

    def get_locataire(self, obj):
        """Affiche le nom du locataire principal."""
        locataire = obj.occupants.filter(role='LOCATAIRE').first()
        if locataire:
            return f"{locataire.nom} {locataire.prenom}"
        return "-"
    get_locataire.short_description = 'Locataire'

    def get_loyer_hc(self, obj):
        return f"{obj.loyer_hc} €"
    get_loyer_hc.short_description = 'Loyer HC'
    get_loyer_hc.admin_order_field = 'tarifications__loyer_hc'

    def get_charges(self, obj):
        return f"{obj.charges} €"
    get_charges.short_description = 'Charges'

    def get_taxes(self, obj):
        return f"{obj.taxes} €"
    get_taxes.short_description = 'Taxes'

    def get_actif_badge(self, obj):
        """Badge coloré pour le statut actif/inactif."""
        if obj.actif:
            return mark_safe(
                '<span style="background-color: #28a745; color: white; padding: 3px 10px; border-radius: 3px; font-weight: bold;">✓ Actif</span>'
            )
        else:
            return mark_safe(
                '<span style="background-color: #dc3545; color: white; padding: 3px 10px; border-radius: 3px;">✗ Inactif</span>'
            )
    get_actif_badge.short_description = 'Statut'
    get_actif_badge.admin_order_field = 'actif'

    def imprimer_quittance(self, request, queryset):
        if queryset.count() != 1:
            self.message_user(request, "Veuillez sélectionner un seul bail pour imprimer la quittance.", level='warning')
            return
        # Redirige vers la vue de génération PDF
        return redirect('quittance_pdf', pk=queryset.first().pk)
    imprimer_quittance.short_description = "Télécharger la quittance PDF"

    def imprimer_avis_echeance(self, request, queryset):
        if queryset.count() != 1:
            self.message_user(request, "Veuillez sélectionner un seul bail.", level='warning')
            return
        return redirect('avis_echeance_pdf', pk=queryset.first().pk)
    imprimer_avis_echeance.short_description = "Télécharger Avis d'échéance"

    def imprimer_regularisation(self, request, queryset):
        if queryset.count() != 1:
            self.message_user(request, "Veuillez sélectionner un seul bail.", level='warning')
            return
        return redirect('regularisation_pdf', pk=queryset.first().pk)
    imprimer_regularisation.short_description = "Générer Régularisation Charges (N-1)"

    def imprimer_solde_tout_compte(self, request, queryset):
        if queryset.count() != 1:
            self.message_user(request, "Veuillez sélectionner un seul bail.", level='warning')
            return
        return redirect('solde_tout_compte_pdf', pk=queryset.first().pk)
    imprimer_solde_tout_compte.short_description = "Générer Solde de Tout Compte (Fin de bail)"

    def imprimer_revision_loyer(self, request, queryset):
        if queryset.count() != 1:
            self.message_user(request, "Veuillez sélectionner un seul bail.", level='warning')
            return
        return redirect('revision_loyer_pdf', pk=queryset.first().pk)
    imprimer_revision_loyer.short_description = "Révision du Loyer (IRL/ILC)"

    @admin.action(description='📦 Générer Quittances Groupées (ZIP)')
    def generer_quittances_zip(self, request, queryset):
        """
        Génère un fichier ZIP contenant les quittances de tous les baux sélectionnés.
        Utilise la dernière période disponible pour chaque bail.
        """
        if queryset.count() == 0:
            self.message_user(request, "Aucun bail sélectionné.", level='warning')
            return

        logger.info(f"Génération ZIP quittances pour {queryset.count()} baux")

        try:
            # Créer ZIP en mémoire
            zip_buffer = BytesIO()

            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                for bail in queryset:
                    try:
                        # Période actuelle (mois en cours)
                        today = date.today()
                        periode = date(today.year, today.month, 1)

                        # Générer quittance avec PDFGenerator
                        from .pdf_generator import PDFGenerator
                        generator = PDFGenerator(bail)
                        pdf_content = generator.generer_quittance([periode])

                        # Nom du fichier dans le ZIP
                        occupant = bail.occupants.filter(role='LOCATAIRE').first()
                        nom_locataire = occupant.nom.upper().replace(" ", "_") if occupant else "Inconnu"
                        filename = f"Quittance_{nom_locataire}_{bail.local.numero_porte}_{periode.strftime('%Y-%m')}.pdf"

                        # Ajouter au ZIP
                        zip_file.writestr(filename, pdf_content)

                        logger.debug(f"Quittance ajoutée au ZIP: {filename}")

                    except Exception as e:
                        logger.error(f"Erreur génération quittance pour bail {bail.pk}: {str(e)}")
                        # Continue avec les autres baux
                        continue

            # Préparer la réponse
            zip_buffer.seek(0)
            response = HttpResponse(zip_buffer.getvalue(), content_type='application/zip')
            response['Content-Disposition'] = f'attachment; filename="Quittances_{date.today().strftime("%Y%m%d")}.zip"'

            self.message_user(request, f'✓ ZIP généré avec {queryset.count()} quittance(s).', level='success')

            logger.info(f"ZIP généré avec succès: {len(zip_buffer.getvalue())} bytes")
            return response

        except Exception as e:
            logger.exception("Erreur génération ZIP quittances")
            self.message_user(request, f'Erreur: {str(e)}', level='error')
            return

    @admin.action(description='🔍 Vérifier Continuité Tarifications')
    def verifier_continuite_tarifications(self, request, queryset):
        """
        Vérifie qu'il n'y a pas de trous dans les tarifications des baux sélectionnés.
        """
        problemes = []

        for bail in queryset:
            tarifs = bail.tarifications.order_by('date_debut')

            if not tarifs.exists():
                problemes.append(f"❌ {bail}: Aucune tarification définie")
                continue

            # Vérifier continuité
            for i in range(len(tarifs) - 1):
                tarif_current = tarifs[i]
                tarif_next = tarifs[i + 1]

                if tarif_current.date_fin:
                    from datetime import timedelta
                    expected_next = tarif_current.date_fin + timedelta(days=1)

                    if tarif_next.date_debut != expected_next:
                        gap_days = (tarif_next.date_debut - tarif_current.date_fin).days - 1
                        problemes.append(
                            f"⚠️ {bail}: Trou de {gap_days} jour(s) entre "
                            f"{tarif_current.date_fin.strftime('%d/%m/%Y')} et "
                            f"{tarif_next.date_debut.strftime('%d/%m/%Y')}"
                        )

            # Vérifier qu'il y a une tarification active
            tarif_actif = bail.tarification_actuelle
            if not tarif_actif:
                problemes.append(f"❌ {bail}: Aucune tarification active aujourd'hui")

        # Afficher résultats
        if problemes:
            message = "Problèmes détectés:\n" + "\n".join(problemes)
            self.message_user(request, message, level='warning')
            logger.warning(f"Vérification tarifications: {len(problemes)} problème(s) détecté(s)")
        else:
            self.message_user(request, f'✓ Toutes les tarifications sont continues ({queryset.count()} bail(s) vérifiés).', level='success')
            logger.info(f"Vérification tarifications: OK pour {queryset.count()} baux")

@admin.register(Proprietaire)
class ProprietaireAdmin(admin.ModelAdmin):
    list_display = ('nom', 'ville', 'type_proprietaire')

@admin.register(Immeuble)
class ImmeubleAdmin(admin.ModelAdmin):
    list_display = (
        'nom', 'ville', 'proprietaire', 'regime_fiscal',
        'get_valeur_actuelle', 'get_capital_restant_du', 'get_valeur_nette',
        'get_rendement_brut', 'get_cashflow'
    )
    list_filter = ('proprietaire', 'regime_fiscal', 'ville')
    search_fields = ('nom', 'adresse', 'ville')

    fieldsets = (
        ('Informations générales', {
            'fields': ('proprietaire', 'nom', 'adresse', ('ville', 'code_postal'))
        }),
        ('Acquisition', {
            'fields': (
                ('prix_achat', 'date_achat'),
                ('frais_notaire', 'frais_agence'),
            ),
            'classes': ('collapse',),
        }),
        ('Fiscalité', {
            'fields': ('regime_fiscal',),
        }),
    )

    inlines = [EstimationValeurInline, CreditImmobilierInline, ChargeFiscaleInline, AmortissementInline]

    def get_valeur_actuelle(self, obj):
        valeur = PatrimoineCalculator.get_valeur_actuelle(obj)
        if valeur:
            return f"{valeur:,.0f} €".replace(',', ' ')
        return "-"
    get_valeur_actuelle.short_description = "Valeur actuelle"

    def get_capital_restant_du(self, obj):
        crd = PatrimoineCalculator.get_capital_restant_du(obj)
        if crd > 0:
            return f"{crd:,.0f} €".replace(',', ' ')
        return "0 €"
    get_capital_restant_du.short_description = "CRD"

    def get_valeur_nette(self, obj):
        valeur_nette = PatrimoineCalculator.get_valeur_nette(obj)
        color = "#28a745" if valeur_nette >= 0 else "#dc3545"
        return mark_safe(f'<span style="color: {color}; font-weight: bold;">{valeur_nette:,.0f} €</span>'.replace(',', ' '))
    get_valeur_nette.short_description = "Valeur nette"

    def get_rendement_brut(self, obj):
        rendement = RentabiliteCalculator.get_rendement_brut(obj)
        if rendement is not None:
            color = "#28a745" if rendement >= 5 else "#ffc107" if rendement >= 3 else "#dc3545"
            return mark_safe(f'<span style="color: {color}; font-weight: bold;">{rendement:.1f}%</span>')
        return "-"
    get_rendement_brut.short_description = "Rdt brut"

    def get_cashflow(self, obj):
        cashflow = RentabiliteCalculator.get_cashflow_mensuel(obj)
        color = "#28a745" if cashflow >= 0 else "#dc3545"
        return mark_safe(f'<span style="color: {color}; font-weight: bold;">{cashflow:,.0f} €/mois</span>'.replace(',', ' '))
    get_cashflow.short_description = "Cash-flow"

    actions = ['voir_bilan_fiscal']

    @admin.action(description='📊 Voir Bilan Fiscal')
    def voir_bilan_fiscal(self, request, queryset):
        """Redirige vers le bilan fiscal de l'immeuble sélectionné."""
        if queryset.count() != 1:
            self.message_user(request, "Veuillez sélectionner un seul immeuble.", level='warning')
            return
        immeuble = queryset.first()
        from django.shortcuts import redirect
        return redirect('bilan_fiscal_immeuble', immeuble_id=immeuble.pk)

@admin.register(Occupant)
class OccupantAdmin(admin.ModelAdmin):
    list_display = ('nom', 'prenom', 'role', 'bail')
    list_filter = ('role',)

@admin.register(CleRepartition)
class CleRepartitionAdmin(admin.ModelAdmin):
    list_display = ('nom', 'immeuble', 'mode_repartition', 'prix_unitaire')
    list_filter = ('immeuble', 'mode_repartition')
    inlines = [QuotePartInline] # Permet de définir les tantièmes de chaque local directement ici

@admin.register(Depense)
class DepenseAdmin(admin.ModelAdmin):
    list_display = ('date', 'libelle', 'montant', 'immeuble', 'cle_repartition', 'date_debut', 'date_fin')
    list_filter = ('immeuble', 'cle_repartition', 'date')

@admin.register(Consommation)
class ConsommationAdmin(admin.ModelAdmin):
    list_display = ('local', 'cle_repartition', 'date_debut', 'date_releve', 'index_debut', 'index_fin', 'quantite')
    list_filter = ('local__immeuble', 'cle_repartition', 'date_releve')

@admin.register(Ajustement)
class AjustementAdmin(admin.ModelAdmin):
    """Admin standalone pour gérer tous les ajustements."""
    list_display = ('bail', 'date', 'libelle', 'montant', 'get_immeuble')
    list_filter = ('bail__local__immeuble', 'date')
    search_fields = ('libelle', 'bail__local__numero_porte')
    date_hierarchy = 'date'
    ordering = ['-date']

    def get_immeuble(self, obj):
        return obj.bail.local.immeuble.nom
    get_immeuble.short_description = "Immeuble"
    get_immeuble.admin_order_field = 'bail__local__immeuble__nom'

@admin.register(QuotePart)
class QuotePartAdmin(admin.ModelAdmin):
    """Admin standalone pour gérer toutes les quote-parts."""
    list_display = ('local', 'cle', 'valeur', 'get_immeuble')
    list_filter = ('cle__immeuble', 'cle')
    search_fields = ('local__numero_porte', 'cle__nom')
    ordering = ['cle__immeuble', 'cle', 'local']

    def get_immeuble(self, obj):
        return obj.cle.immeuble.nom
    get_immeuble.short_description = "Immeuble"
    get_immeuble.admin_order_field = 'cle__immeuble__nom'

@admin.register(BailTarification)
class BailTarificationAdmin(admin.ModelAdmin):
    list_display = ('bail', 'date_debut', 'date_fin', 'loyer_hc', 'charges', 'taxes', 'reason', 'created_at')
    list_filter = ('bail__local__immeuble', 'created_at')
    readonly_fields = ('created_at',)
    fields = (
        'bail',
        ('date_debut', 'date_fin'),
        ('loyer_hc', 'charges', 'taxes'),
        ('indice_reference', 'trimestre_reference'),
        'reason',
        'notes',
        'created_at'
    )
    search_fields = ('bail__local__numero_porte', 'reason')

    def has_delete_permission(self, request, obj=None):
        # Empêcher suppression des tarifications initiales
        if obj and "migration automatique" in obj.reason.lower():
            return False
        return super().has_delete_permission(request, obj)


# =============================================================================
# ADMINISTRATION PATRIMOINE
# =============================================================================

@admin.register(EstimationValeur)
class EstimationValeurAdmin(admin.ModelAdmin):
    list_display = ('immeuble', 'date_estimation', 'valeur_estimee', 'source')
    list_filter = ('immeuble', 'source', 'date_estimation')
    search_fields = ('immeuble__nom', 'notes')
    date_hierarchy = 'date_estimation'


@admin.register(CreditImmobilier)
class CreditImmobilierAdmin(admin.ModelAdmin):
    list_display = (
        'nom_banque', 'immeuble', 'capital_emprunte', 'taux_interet',
        'duree_mois', 'date_debut', 'get_mensualite', 'get_crd', 'get_date_fin'
    )
    list_filter = ('immeuble', 'type_credit', 'nom_banque')
    search_fields = ('nom_banque', 'numero_pret', 'immeuble__nom')
    date_hierarchy = 'date_debut'

    fieldsets = (
        ('Informations du prêt', {
            'fields': ('immeuble', 'nom_banque', 'numero_pret')
        }),
        ('Conditions', {
            'fields': (
                ('capital_emprunte', 'taux_interet'),
                ('duree_mois', 'date_debut'),
                'type_credit',
                'assurance_mensuelle',
            )
        }),
    )

    inlines = [EcheanceInline]
    actions = ['generer_echeancier']

    def get_mensualite(self, obj):
        return f"{obj.mensualite:.2f} €"
    get_mensualite.short_description = "Mensualité"

    def get_crd(self, obj):
        crd = obj.capital_restant_du
        pourcentage = (crd / float(obj.capital_emprunte)) * 100 if obj.capital_emprunte else 0
        return f"{crd:,.0f} € ({pourcentage:.0f}%)".replace(',', ' ')
    get_crd.short_description = "Capital restant dû"

    def get_date_fin(self, obj):
        return obj.date_fin.strftime('%d/%m/%Y')
    get_date_fin.short_description = "Date fin"

    @admin.action(description='📅 Générer/Régénérer échéancier')
    def generer_echeancier(self, request, queryset):
        total = 0
        for credit in queryset:
            generator = CreditGenerator(credit)
            nb_echeances = generator.creer_echeances_en_base()
            total += nb_echeances
            logger.info(f"Échéancier généré pour {credit}: {nb_echeances} échéances")

        self.message_user(
            request,
            f'✓ {total} échéances générées pour {queryset.count()} crédit(s).',
            level='success'
        )


@admin.register(EcheanceCredit)
class EcheanceCreditAdmin(admin.ModelAdmin):
    list_display = (
        'credit', 'numero_echeance', 'date_echeance',
        'capital_rembourse', 'interets', 'assurance',
        'capital_restant_du', 'payee'
    )
    list_filter = ('credit__immeuble', 'credit', 'payee', 'date_echeance')
    readonly_fields = (
        'credit', 'numero_echeance', 'date_echeance',
        'capital_rembourse', 'interets', 'assurance', 'capital_restant_du'
    )
    date_hierarchy = 'date_echeance'

    actions = ['marquer_payee']

    @admin.action(description='✓ Marquer comme payée')
    def marquer_payee(self, request, queryset):
        from django.utils import timezone
        updated = queryset.update(payee=True, date_paiement=timezone.now().date())
        self.message_user(request, f'{updated} échéance(s) marquée(s) comme payée(s).')


@admin.register(ChargeFiscale)
class ChargeFiscaleAdmin(admin.ModelAdmin):
    list_display = ('immeuble', 'annee', 'type_charge', 'montant', 'libelle')
    list_filter = ('immeuble', 'annee', 'type_charge')
    search_fields = ('libelle', 'immeuble__nom')
    ordering = ['-annee', 'immeuble', 'type_charge']

    fieldsets = (
        (None, {
            'fields': ('immeuble', 'annee', 'type_charge', 'montant', 'libelle')
        }),
        ('Justificatif', {
            'fields': ('justificatif',),
            'classes': ('collapse',),
        }),
    )


@admin.register(Amortissement)
class AmortissementAdmin(admin.ModelAdmin):
    list_display = (
        'immeuble', 'type_bien', 'libelle', 'valeur_origine',
        'date_mise_service', 'duree_amortissement', 'get_dotation', 'get_date_fin'
    )
    list_filter = ('immeuble', 'type_bien')
    search_fields = ('libelle', 'immeuble__nom')

    def get_dotation(self, obj):
        return f"{obj.dotation_annuelle:,.2f} €/an".replace(',', ' ')
    get_dotation.short_description = "Dotation annuelle"

    def get_date_fin(self, obj):
        return obj.date_fin_amortissement.strftime('%d/%m/%Y')
    get_date_fin.short_description = "Fin amortissement"


@admin.register(VacanceLocative)
class VacanceLocativeAdmin(admin.ModelAdmin):
    list_display = ('local', 'date_debut', 'date_fin', 'motif', 'get_duree', 'get_statut')
    list_filter = ('local__immeuble', 'motif', 'date_debut')
    search_fields = ('local__numero_porte', 'local__immeuble__nom')
    date_hierarchy = 'date_debut'

    def get_duree(self, obj):
        return f"{obj.duree_jours} jours"
    get_duree.short_description = "Durée"

    def get_statut(self, obj):
        if obj.date_fin is None:
            return mark_safe(
                '<span style="background-color: #dc3545; color: white; padding: 3px 8px; border-radius: 3px;">● En cours</span>'
            )
        return mark_safe(
            '<span style="background-color: #28a745; color: white; padding: 3px 8px; border-radius: 3px;">○ Terminée</span>'
        )
    get_statut.short_description = "Statut"