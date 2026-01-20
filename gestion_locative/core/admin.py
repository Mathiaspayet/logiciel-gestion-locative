from django.contrib import admin
from django.shortcuts import redirect
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.db.models import Sum, Count, Q
from django.http import HttpResponse
from datetime import date
import zipfile
from io import BytesIO
import logging

from .models import Immeuble, Local, Bail, Occupant, Proprietaire, CleRepartition, QuotePart, Depense, Consommation, Ajustement, Regularisation, BailTarification

logger = logging.getLogger(__name__)

# Personnalisation de l'interface
admin.site.site_header = "Gestion Locative"
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

class RegularisationInline(admin.TabularInline):
    model = Regularisation
    extra = 0
    readonly_fields = ('date_creation', 'date_debut', 'date_fin', 'montant_reel', 'montant_provisions', 'solde')
    fields = ('date_creation', 'date_debut', 'date_fin', 'montant_reel', 'montant_provisions', 'solde', 'payee', 'date_paiement', 'notes')
    can_delete = False # On garde l'historique

class BailTarificationInline(admin.TabularInline):
    model = BailTarification
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
    list_display = ('__str__', 'type_local', 'surface_m2')
    list_filter = ('immeuble',)
    inlines = [BailInline]

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
    list_display = ('nom', 'ville', 'proprietaire')

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