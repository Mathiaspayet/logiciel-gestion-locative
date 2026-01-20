import os
import subprocess
import sys

# Configuration du projet
PROJECT_NAME = "gestion_locative"
APP_NAME = "core"

def run_command(command):
    """Exécute une commande shell."""
    try:
        subprocess.check_call(command, shell=True)
    except subprocess.CalledProcessError as e:
        print(f"Erreur lors de l'exécution de : {command}")
        sys.exit(1)

def write_file(path, content):
    """Écrit le contenu dans un fichier."""
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content.strip())
    print(f"Fichier créé : {path}")

# --- CONTENU DES FICHIERS ---

MODELS_CODE = '''
from django.db import models
from django.utils import timezone

class Proprietaire(models.Model):
    TYPE_CHOICES = [
        ('PARTICULIER', 'Particulier'),
        ('SOCIETE', 'Société'),
    ]
    nom = models.CharField(max_length=200, verbose_name="Nom ou Raison Sociale")
    adresse = models.TextField()
    ville = models.CharField(max_length=100)
    code_postal = models.CharField(max_length=20)
    type_proprietaire = models.CharField(max_length=20, choices=TYPE_CHOICES, default='PARTICULIER')

    def __str__(self):
        return self.nom

    class Meta:
        verbose_name = "Propriétaire"
        verbose_name_plural = "Propriétaires"

class Immeuble(models.Model):
    proprietaire = models.ForeignKey(Proprietaire, on_delete=models.SET_NULL, null=True, blank=True, related_name='immeubles', verbose_name="Propriétaire / Bailleur")
    nom = models.CharField(max_length=200)
    adresse = models.TextField()
    ville = models.CharField(max_length=100)
    code_postal = models.CharField(max_length=20)
    date_creation = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.nom} - {self.ville}"

    class Meta:
        verbose_name = "Immeuble"
        verbose_name_plural = "Immeubles"

class Local(models.Model):
    TYPE_CHOICES = [
        ('APPART', 'Appartement'),
        ('COMMERCE', 'Local Commercial'),
        ('PARKING', 'Parking'),
        ('BUREAU', 'Bureau'),
    ]
    immeuble = models.ForeignKey(Immeuble, on_delete=models.CASCADE, related_name='locaux')
    numero_porte = models.CharField(max_length=10)
    etage = models.IntegerField(default=0)
    surface_m2 = models.DecimalField(max_digits=6, decimal_places=2)
    type_local = models.CharField(max_length=20, choices=TYPE_CHOICES, default='APPART', verbose_name="Type de local")

    def __str__(self):
        return f"{self.immeuble.nom} - Porte {self.numero_porte}"

    class Meta:
        verbose_name = "Local"
        verbose_name_plural = "Locaux"

class Bail(models.Model):
    TYPE_CHARGES_CHOICES = [
        ('PROVISION', 'Provision sur charges (Régularisation annuelle)'),
        ('FORFAIT', 'Forfait de charges (Pas de régularisation)'),
    ]
    FREQUENCE_CHOICES = [
        ('MENSUEL', 'Mensuel'),
        ('TRIMESTRIEL', 'Trimestriel'),
    ]
    local = models.ForeignKey(Local, on_delete=models.CASCADE, related_name='baux')
    type_charges = models.CharField(max_length=20, choices=TYPE_CHARGES_CHOICES, default='PROVISION')
    frequence_paiement = models.CharField(max_length=20, choices=FREQUENCE_CHOICES, default='MENSUEL', verbose_name="Fréquence de paiement")
    date_debut = models.DateField(default=timezone.now, verbose_name="Date d'entrée")
    date_fin = models.DateField(null=True, blank=True, verbose_name="Date de sortie")
    loyer_hc = models.DecimalField(max_digits=8, decimal_places=2, verbose_name="Loyer HC")
    charges = models.DecimalField(max_digits=8, decimal_places=2, default=0.00, verbose_name="Provisions charges")
    taxes = models.DecimalField(max_digits=8, decimal_places=2, default=0.00, verbose_name="Taxes (non soumises TVA)", help_text="Ex: Taxe foncière, TOM...")
    depot_garantie = models.DecimalField(max_digits=8, decimal_places=2, default=0.00, verbose_name="Dépôt de garantie")
    actif = models.BooleanField(default=True)
    
    # Gestion de la TVA
    soumis_tva = models.BooleanField(default=False, verbose_name="Soumis à la TVA")
    taux_tva = models.DecimalField(max_digits=5, decimal_places=2, default=20.00, help_text="En % (ex: 20.00)")
    
    # Indexation des loyers (IRL)
    indice_reference = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True, verbose_name="Indice IRL initial")
    trimestre_reference = models.CharField(max_length=20, blank=True, help_text="Ex: T1 2024")

    @property
    def montant_tva(self):
        if not self.soumis_tva:
            return 0
        return ((self.loyer_hc + self.charges) * self.taux_tva) / 100

    @property
    def loyer_ttc(self):
        return float(self.loyer_hc) + float(self.charges) + float(self.taxes) + float(self.montant_tva)

    def __str__(self):
        return f"Bail {self.local} ({self.date_debut})"

    class Meta:
        verbose_name = "Bail"
        verbose_name_plural = "Baux"

class CleRepartition(models.Model):
    """Définit comment une catégorie de charges est répartie (ex: Charges Générales, Ascenseur, Eau)."""
    MODE_CHOICES = [
        ('TANTIEMES', 'Par Tantièmes (Surface/Millièmes)'),
        ('CONSOMMATION', 'Par Consommation (Compteurs)'),
    ]
    immeuble = models.ForeignKey(Immeuble, on_delete=models.CASCADE, related_name='cles_repartition')
    nom = models.CharField(max_length=100, help_text="Ex: Charges Générales, Eau Froide, Taxe Ordures Ménagères")
    mode_repartition = models.CharField(max_length=20, choices=MODE_CHOICES, default='TANTIEMES', verbose_name="Mode de calcul")
    prix_unitaire = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True, verbose_name="Prix Unitaire (si consommation)", help_text="Ex: Prix du m3 d'eau")
    
    def __str__(self):
        return f"{self.nom} ({self.immeuble.nom})"

    class Meta:
        verbose_name = "Clé de répartition"
        verbose_name_plural = "Clés de répartition"

class QuotePart(models.Model):
    """Définit la part (tantièmes) d'un local pour une clé donnée."""
    cle = models.ForeignKey(CleRepartition, on_delete=models.CASCADE, related_name='quote_parts')
    local = models.ForeignKey(Local, on_delete=models.CASCADE, related_name='quote_parts')
    valeur = models.DecimalField(max_digits=10, decimal_places=2, help_text="Nombre de tantièmes ou m² pour ce local")

    class Meta:
        unique_together = ('cle', 'local') # Un local ne peut apparaître qu'une fois par clé

    def __str__(self):
        return f"{self.local.numero_porte} : {self.valeur}"

    class Meta:
        verbose_name = "Quote-part"
        verbose_name_plural = "Quote-parts"

class Depense(models.Model):
    """Une facture payée par le propriétaire, à répartir."""
    immeuble = models.ForeignKey(Immeuble, on_delete=models.CASCADE, related_name='depenses')
    cle_repartition = models.ForeignKey(CleRepartition, on_delete=models.SET_NULL, null=True, related_name='depenses')
    date = models.DateField()
    libelle = models.CharField(max_length=200, help_text="Ex: Facture EDF Parties Communes")
    montant = models.DecimalField(max_digits=10, decimal_places=2)
    date_debut = models.DateField(null=True, blank=True, verbose_name="Début période", help_text="Optionnel : Si la dépense couvre une période")
    date_fin = models.DateField(null=True, blank=True, verbose_name="Fin période")
    
    # Optionnel : pour stocker le PDF de la facture fournisseur
    # fichier = models.FileField(upload_to='factures/', null=True, blank=True)

    def __str__(self):
        return f"{self.date} - {self.libelle} ({self.montant}€)"

    class Meta:
        verbose_name = "Dépense"
        verbose_name_plural = "Dépenses"

class Consommation(models.Model):
    """Relevé de compteur pour un local spécifique."""
    local = models.ForeignKey(Local, on_delete=models.CASCADE, related_name='consommations')
    cle_repartition = models.ForeignKey(CleRepartition, on_delete=models.CASCADE, related_name='consommations', verbose_name="Type de fluide")
    date_debut = models.DateField(null=True, blank=True, verbose_name="Début période conso", help_text="Date du précédent relevé")
    date_releve = models.DateField(default=timezone.now, verbose_name="Date du relevé")
    index_debut = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Ancien Index")
    index_fin = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Nouvel Index")
    
    @property
    def quantite(self):
        return self.index_fin - self.index_debut

    def __str__(self):
        return f"{self.local} - {self.cle_repartition.nom} : {self.quantite}"

    class Meta:
        verbose_name = "Relevé Compteur"
        verbose_name_plural = "Relevés Compteurs"

class Ajustement(models.Model):
    """Ligne manuelle ajoutée à la régularisation (positive ou négative)."""
    bail = models.ForeignKey(Bail, on_delete=models.CASCADE, related_name='ajustements')
    date = models.DateField(default=timezone.now, help_text="La date détermine l'année de régularisation")
    libelle = models.CharField(max_length=200, verbose_name="Libellé de la ligne")
    montant = models.DecimalField(max_digits=8, decimal_places=2, help_text="Mettre un montant négatif pour une déduction")

    class Meta:
        verbose_name = "Ajustement manuel"
        verbose_name_plural = "Ajustements manuels"

class Occupant(models.Model):
    ROLE_CHOICES = [
        ('LOCATAIRE', 'Locataire (Habitant)'),
        ('GARANT', 'Garant (Caution)'),
    ]
    bail = models.ForeignKey(Bail, on_delete=models.CASCADE, related_name='occupants')
    nom = models.CharField(max_length=100)
    prenom = models.CharField(max_length=100)
    email = models.EmailField(blank=True)
    telephone = models.CharField(max_length=20, blank=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='LOCATAIRE')

    def __str__(self):
        return f"{self.nom} {self.prenom} ({self.get_role_display()})"

    class Meta:
        verbose_name = "Occupant"
        verbose_name_plural = "Occupants"

class Regularisation(models.Model):
    """Historique des régularisations effectuées."""
    bail = models.ForeignKey(Bail, on_delete=models.CASCADE, related_name='regularisations')
    date_creation = models.DateTimeField(auto_now_add=True, verbose_name="Fait le")
    date_debut = models.DateField(verbose_name="Début période")
    date_fin = models.DateField(verbose_name="Fin période")
    montant_reel = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Total Réel")
    montant_provisions = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Total Provisions")
    solde = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Solde (A payer/Rendre)")

    def __str__(self):
        return f"Régul du {self.date_debut} au {self.date_fin} ({self.solde}€)"
'''

ADMIN_CODE = '''
from django.contrib import admin
from django.shortcuts import redirect
from .models import Immeuble, Local, Bail, Occupant, Proprietaire, CleRepartition, QuotePart, Depense, Consommation, Ajustement, Regularisation

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
    can_delete = False # On garde l'historique

@admin.register(Local)
class LocalAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'type_local', 'surface_m2')
    list_filter = ('immeuble',)
    inlines = [BailInline]

@admin.register(Bail)
class BailAdmin(admin.ModelAdmin):
    list_display = ('local', 'date_debut', 'loyer_hc', 'charges', 'taxes', 'type_charges', 'frequence_paiement', 'actif')
    list_filter = ('actif', 'frequence_paiement')
    inlines = [OccupantInline, AjustementInline, RegularisationInline]
    actions = ['imprimer_quittance', 'imprimer_avis_echeance', 'imprimer_regularisation']

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
'''

SERIALIZERS_CODE = '''
from rest_framework import serializers
from .models import Immeuble, Local, Bail, Occupant

class OccupantSerializer(serializers.ModelSerializer):
    class Meta:
        model = Occupant
        fields = '__all__'

class BailSerializer(serializers.ModelSerializer):
    occupants = OccupantSerializer(many=True, read_only=True)
    class Meta:
        model = Bail
        fields = '__all__'

class LocalSerializer(serializers.ModelSerializer):
    bail_actif = serializers.SerializerMethodField()
    class Meta:
        model = Local
        fields = ['id', 'numero_porte', 'etage', 'surface_m2', 'type_local', 'bail_actif']

    def get_bail_actif(self, obj):
        bail = obj.baux.filter(actif=True).first()
        if bail:
            return BailSerializer(bail).data
        return None

class ImmeubleSerializer(serializers.ModelSerializer):
    locaux = LocalSerializer(many=True, read_only=True)
    class Meta:
        model = Immeuble
        fields = ['id', 'nom', 'adresse', 'ville', 'locaux']
'''

VIEWS_CODE = '''
from rest_framework import viewsets
from django.http import HttpResponse
from django.db.models import Sum, Q
from django.middleware.csrf import get_token
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib import colors
from datetime import datetime, date, timedelta
import calendar
from .models import Immeuble, Bail, Depense, Consommation, Ajustement, Regularisation
from .serializers import ImmeubleSerializer, BailSerializer

def format_euro(montant):
    """Formate un montant en euros : 1 234,56 €"""
    try:
        return f"{montant:,.2f}".replace(",", " ").replace(".", ",") + " €"
    except (ValueError, TypeError):
        return "0,00 €"

class ImmeubleViewSet(viewsets.ModelViewSet):
    queryset = Immeuble.objects.all()
    serializer_class = ImmeubleSerializer

class BailViewSet(viewsets.ModelViewSet):
    queryset = Bail.objects.all()
    serializer_class = BailSerializer

def generer_quittance_pdf(request, pk):
    """Génère une ou plusieurs quittances de loyer au format PDF pour un bail donné."""
    bail = Bail.objects.get(pk=pk)
    
    # 1. Détection de la fréquence
    is_trimestriel = (bail.frequence_paiement == 'TRIMESTRIEL')
    multiplicateur = 1 # Les montants en base sont déjà ceux de la période (mensuel ou trimestriel)

    # --- 1. Affichage du formulaire de sélection (si pas de POST) ---
    if request.method != 'POST':
        csrf_token = get_token(request)
        
        # Génération des 10 dernières périodes (pour les cases à cocher)
        options_html = ""
        date_cursor = date.today().replace(day=1)
        
        if is_trimestriel:
            # Caler sur le début du trimestre en cours
            mois_debut_trim = ((date_cursor.month - 1) // 3) * 3 + 1
            date_cursor = date_cursor.replace(month=mois_debut_trim)
            
        for i in range(10):
            # Calcul fin pour affichage
            if is_trimestriel:
                mois_fin_p = date_cursor.month + 2
                annee_fin_p = date_cursor.year
                if mois_fin_p > 12:
                    mois_fin_p -= 12
                    annee_fin_p += 1
                last_day = calendar.monthrange(annee_fin_p, mois_fin_p)[1]
                date_fin_display = date(annee_fin_p, mois_fin_p, last_day)
                label = f"Trimestre du {date_cursor.strftime('%d/%m/%Y')} au {date_fin_display.strftime('%d/%m/%Y')}"
                
                # Reculer de 3 mois pour la prochaine itération (on remonte le temps)
                prev_month = date_cursor.month - 3
                prev_year = date_cursor.year
                if prev_month < 1:
                    prev_month += 12
                    prev_year -= 1
                next_cursor = date(prev_year, prev_month, 1)
            else:
                last_day = calendar.monthrange(date_cursor.year, date_cursor.month)[1]
                date_fin_display = date_cursor.replace(day=last_day)
                label = f"Mois de {date_cursor.strftime('%m/%Y')}"
                
                # Reculer d'1 mois
                prev_month = date_cursor.month - 1
                prev_year = date_cursor.year
                if prev_month < 1:
                    prev_month += 12
                    prev_year -= 1
                next_cursor = date(prev_year, prev_month, 1)
                
            valeur = date_cursor.strftime('%Y-%m-%d')
            options_html += f'''
            <div style="margin-bottom: 8px;">
                <input type="checkbox" id="d_{valeur}" name="dates" value="{valeur}">
                <label for="d_{valeur}" style="display:inline; font-weight:normal;">{label}</label>
            </div>
            '''
            date_cursor = next_cursor

        html = f'''
        <html>
        <head>
            <title>Générer Quittances</title>
            <style>
                body {{ font-family: sans-serif; padding: 40px; background-color: #f4f6f9; }}
                .container {{ max-width: 500px; margin: 0 auto; background: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
                h2 {{ color: #333; margin-top: 0; }}
                label {{ display: block; margin-top: 15px; font-weight: bold; color: #555; }}
                input[type="month"] {{ width: 100%; padding: 10px; margin-top: 5px; border: 1px solid #ddd; border-radius: 4px; box-sizing: border-box; }}
                button {{ margin-top: 25px; width: 100%; padding: 12px; background-color: #417690; color: white; border: none; border-radius: 4px; font-size: 16px; cursor: pointer; }}
                button:hover {{ background-color: #2a5366; }}
                .info {{ margin-bottom: 20px; padding: 10px; background-color: #e8f4f8; border-left: 4px solid #417690; color: #2c3e50; }}
                .section-title {{ font-weight:bold; color:#555; margin-top: 20px; margin-bottom: 10px; border-bottom: 1px solid #eee; padding-bottom: 5px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h2>Générer Quittances</h2>
                <div class="info">
                    <strong>Bail :</strong> {bail.local.numero_porte}<br>
                    <strong>Locataire :</strong> {bail.occupants.first() or 'Inconnu'}
                </div>
                <form method="POST">
                    <input type="hidden" name="csrfmiddlewaretoken" value="{csrf_token}">
                    
                    <div class="section-title">Sélection rapide (10 dernières)</div>
                    {options_html}
                    
                    <div class="section-title">Ou par période personnalisée</div>
                    <label>Mois de début :</label>
                    <input type="month" name="custom_debut">
                    
                    <label>Mois de fin (inclus) :</label>
                    <input type="month" name="custom_fin">
                    
                    <button type="submit">Générer le PDF</button>
                </form>
            </div>
        </body>
        </html>
        '''
        return HttpResponse(html)

    # --- 2. Traitement et Génération du PDF ---
    final_dates = set()
    
    # A. Dates cochées
    selected_dates_str = request.POST.getlist('dates')
    for d_str in selected_dates_str:
        final_dates.add(datetime.strptime(d_str, '%Y-%m-%d').date())
        
    # B. Période personnalisée
    custom_debut = request.POST.get('custom_debut')
    custom_fin = request.POST.get('custom_fin')
    
    if custom_debut and custom_fin:
        y1, m1 = map(int, custom_debut.split('-'))
        y2, m2 = map(int, custom_fin.split('-'))
        d_start = date(y1, m1, 1)
        d_end = date(y2, m2, 1)
        
        # Si trimestriel, on cale le début
        if is_trimestriel:
             m_snap = ((d_start.month - 1) // 3) * 3 + 1
             d_start = d_start.replace(month=m_snap)

        curr = d_start
        while curr <= d_end:
            final_dates.add(curr)
            # Incrément
            if is_trimestriel:
                nm = curr.month + 3
                ny = curr.year + (nm - 1) // 12
                nm = (nm - 1) % 12 + 1
                curr = date(ny, nm, 1)
            else:
                nm = curr.month + 1
                ny = curr.year + (nm - 1) // 12
                nm = (nm - 1) % 12 + 1
                curr = date(ny, nm, 1)

    sorted_dates = sorted(list(final_dates))
    
    if not sorted_dates:
        return HttpResponse("Veuillez sélectionner au moins une date ou une période.", status=400)

    # Préparation du nom de fichier (Nom + Période)
    occupant_f = bail.occupants.filter(role='LOCATAIRE').first()
    nom_locataire = occupant_f.nom.upper().replace(" ", "_") if occupant_f else "Inconnu"
    date_debut_str = sorted_dates[0].strftime('%Y-%m')
    date_fin_str = sorted_dates[-1].strftime('%Y-%m')
    periode_str = date_debut_str if date_debut_str == date_fin_str else f"{date_debut_str}_au_{date_fin_str}"

    # Configuration de la réponse HTTP (téléchargement de fichier)
    response = HttpResponse(content_type='application/pdf')
    filename = f"Quittance_{nom_locataire}_{periode_str}.pdf"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    # Création du document PDF
    p = canvas.Canvas(response, pagesize=A4)
    
    # BOUCLE SUR LES MOIS
    for current_date in sorted_dates:
        # Calcul de la période pour cette quittance
        if is_trimestriel:
            # Fin = fin du 3ème mois
            mois_fin_p = current_date.month + 2
            annee_fin_p = current_date.year
            if mois_fin_p > 12:
                mois_fin_p -= 12
                annee_fin_p += 1
            last_day = calendar.monthrange(annee_fin_p, mois_fin_p)[1]
            periode_fin = date(annee_fin_p, mois_fin_p, last_day)
        else:
            # Fin = fin du mois en cours
            last_day = calendar.monthrange(current_date.year, current_date.month)[1]
            periode_fin = current_date.replace(day=last_day)

        # --- DESSIN DE LA QUITTANCE (DESIGN PRO) ---
        
        # 1. En-tête avec fond gris
        p.setFillColor(colors.HexColor("#E0E0E0"))
        p.rect(1*cm, 26*cm, 19*cm, 2.5*cm, fill=1, stroke=0)
        p.setFillColor(colors.black)
        
        p.setFont("Helvetica-Bold", 16)
        p.drawCentredString(10.5*cm, 27.2*cm, "QUITTANCE DE LOYER")
        p.setFont("Helvetica", 11)
        p.drawCentredString(10.5*cm, 26.4*cm, f"Période du {current_date.strftime('%d/%m/%Y')} au {periode_fin.strftime('%d/%m/%Y')}")

        # 2. Cadres Bailleur / Locataire
        # --- Bailleur (Gauche) ---
        p.setStrokeColor(colors.grey)
        p.rect(1*cm, 21.5*cm, 9*cm, 3.5*cm) # Cadre
        p.setFillColor(colors.HexColor("#F5F5F5"))
        p.rect(1*cm, 24.2*cm, 9*cm, 0.8*cm, fill=1, stroke=1) # Titre cadre
        p.setFillColor(colors.black)
        p.setFont("Helvetica-Bold", 11)
        p.drawCentredString(5.5*cm, 24.4*cm, "BAILLEUR")
        
        p.setFont("Helvetica", 10)
        y_text = 23.5*cm
        proprietaire = bail.local.immeuble.proprietaire
        if proprietaire:
            p.drawString(1.5*cm, y_text, proprietaire.nom)
            p.drawString(1.5*cm, y_text-0.5*cm, proprietaire.adresse)
            p.drawString(1.5*cm, y_text-1.0*cm, f"{proprietaire.code_postal} {proprietaire.ville}")
        else:
            p.drawString(1.5*cm, y_text, bail.local.immeuble.nom)
            p.drawString(1.5*cm, y_text-0.5*cm, bail.local.immeuble.adresse)
            p.drawString(1.5*cm, y_text-1.0*cm, f"{bail.local.immeuble.code_postal} {bail.local.immeuble.ville}")

        # --- Locataire (Droite) ---
        p.rect(11*cm, 21.5*cm, 9*cm, 3.5*cm)
        p.setFillColor(colors.HexColor("#F5F5F5"))
        p.rect(11*cm, 24.2*cm, 9*cm, 0.8*cm, fill=1, stroke=1)
        p.setFillColor(colors.black)
        p.setFont("Helvetica-Bold", 11)
        p.drawCentredString(15.5*cm, 24.4*cm, "LOCATAIRE")
        
        p.setFont("Helvetica", 10)
        occupant = bail.occupants.filter(role='LOCATAIRE').first()
        if occupant:
            p.drawString(11.5*cm, y_text, f"{occupant.prenom} {occupant.nom.upper()}")
        else:
            p.drawString(11.5*cm, y_text, "Locataire inconnu")
            
        immeuble = bail.local.immeuble
        p.drawString(11.5*cm, y_text-0.5*cm, immeuble.adresse)
        p.drawString(11.5*cm, y_text-1.0*cm, f"{immeuble.code_postal} {immeuble.ville}")
        p.drawString(11.5*cm, y_text-1.5*cm, f"Porte : {bail.local.numero_porte}")

        # 3. Détail des sommes
        y = 18*cm
        p.setFont("Helvetica-Bold", 12)
        p.drawString(1*cm, y, "Détail du règlement")
        p.setStrokeColor(colors.black)
        p.line(1*cm, y-0.2*cm, 20*cm, y-0.2*cm)
        
        y -= 1.5*cm
        p.setFont("Helvetica", 11)
        
        # Ligne Loyer
        p.drawString(1.5*cm, y, "Loyer Hors Charges")
        p.drawRightString(19.5*cm, y, format_euro(bail.loyer_hc * multiplicateur))
        p.setStrokeColor(colors.lightgrey)
        p.line(1*cm, y-0.3*cm, 20*cm, y-0.3*cm)
        y -= 1*cm
        
        # Ligne Charges
        p.drawString(1.5*cm, y, "Provisions sur charges")
        p.drawRightString(19.5*cm, y, format_euro(bail.charges * multiplicateur))
        p.line(1*cm, y-0.3*cm, 20*cm, y-0.3*cm)
        y -= 1*cm
        
        # Ligne Taxes
        if bail.taxes > 0:
            p.drawString(1.5*cm, y, "Taxes (non soumises TVA)")
            p.drawRightString(19.5*cm, y, format_euro(bail.taxes * multiplicateur))
            p.line(1*cm, y-0.3*cm, 20*cm, y-0.3*cm)
            y -= 1*cm
        
        if bail.soumis_tva:
            p.drawString(1.5*cm, y, f"TVA ({bail.taux_tva} %)")
            p.drawRightString(19.5*cm, y, format_euro(bail.montant_tva * multiplicateur))
            p.line(1*cm, y-0.3*cm, 20*cm, y-0.3*cm)
            y -= 1*cm
        
        # 4. Total
        y -= 0.5*cm
        p.setFillColor(colors.HexColor("#E0E0E0"))
        p.rect(10*cm, y-0.5*cm, 10*cm, 1.2*cm, fill=1, stroke=0)
        p.setFillColor(colors.black)
        p.setFont("Helvetica-Bold", 14)
        p.drawString(10.5*cm, y, "TOTAL PAYÉ")
        p.drawRightString(19.5*cm, y, format_euro(bail.loyer_ttc * multiplicateur))
        
        # Footer
        p.setFont("Helvetica-Oblique", 10)
        p.drawCentredString(10.5*cm, 4*cm, "Pour valoir ce que de droit.")

        # Fin de la page (Quittance suivante sur une nouvelle page)
        p.showPage()

    p.save()
    return response

def generer_avis_echeance_pdf(request, pk):
    """Génère un ou plusieurs avis d'échéance (appel de loyer) au format PDF."""
    bail = Bail.objects.get(pk=pk)
    
    # 1. Détection de la fréquence
    is_trimestriel = (bail.frequence_paiement == 'TRIMESTRIEL')
    multiplicateur = 1 # Les montants en base sont déjà ceux de la période (mensuel ou trimestriel)

    # --- FORMULAIRE DE SELECTION ---
    if request.method != 'POST':
        csrf_token = get_token(request)
        
        # On génère une liste de prochaines échéances (ex: mois en cours + 5 suivants)
        options_html = ""
        date_cursor = date.today().replace(day=1)
        
        # Si trimestriel, on aligne sur le début du trimestre
        if is_trimestriel:
            mois_debut_trim = ((date_cursor.month - 1) // 3) * 3 + 1
            date_cursor = date_cursor.replace(month=mois_debut_trim)

        for i in range(6): # Proposer 6 échéances
            # Calcul date fin pour l'affichage
            if is_trimestriel:
                mois_fin_p = date_cursor.month + 2
                annee_fin_p = date_cursor.year
                if mois_fin_p > 12:
                    mois_fin_p -= 12
                    annee_fin_p += 1
                last_day = calendar.monthrange(annee_fin_p, mois_fin_p)[1]
                date_fin_display = date(annee_fin_p, mois_fin_p, last_day)
                label = f"Trimestre du {date_cursor.strftime('%d/%m/%Y')} au {date_fin_display.strftime('%d/%m/%Y')}"
                
                # Préparer prochaine itération
                next_month = date_cursor.month + 3
            else:
                last_day = calendar.monthrange(date_cursor.year, date_cursor.month)[1]
                date_fin_display = date_cursor.replace(day=last_day)
                label = f"Mois de {date_cursor.strftime('%m/%Y')} ({date_cursor.strftime('%d/%m')} au {date_fin_display.strftime('%d/%m')})"
                
                # Préparer prochaine itération
                next_month = date_cursor.month + 1
            
            valeur = date_cursor.strftime('%Y-%m-%d')
            checked = "checked" if i == 0 else "" # Cocher la première par défaut
            
            options_html += f'''
            <div style="margin-bottom: 8px;">
                <input type="checkbox" id="d{i}" name="dates" value="{valeur}" {checked}>
                <label for="d{i}" style="display:inline; font-weight:normal;">{label}</label>
            </div>
            '''
            
            # Incrémenter date_cursor
            next_year = date_cursor.year + (next_month - 1) // 12
            next_month = (next_month - 1) % 12 + 1
            date_cursor = date(next_year, next_month, 1)

        html = f'''
        <html>
        <head>
            <title>Générer Avis d'Échéance</title>
            <style>
                body {{ font-family: sans-serif; padding: 40px; background-color: #f4f6f9; }}
                .container {{ max-width: 500px; margin: 0 auto; background: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
                h2 {{ color: #333; margin-top: 0; }}
                button {{ margin-top: 25px; width: 100%; padding: 12px; background-color: #417690; color: white; border: none; border-radius: 4px; font-size: 16px; cursor: pointer; }}
                button:hover {{ background-color: #2a5366; }}
                .info {{ margin-bottom: 20px; padding: 10px; background-color: #e8f4f8; border-left: 4px solid #417690; color: #2c3e50; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h2>Avis d'échéance</h2>
                <div class="info">
                    <strong>Bail :</strong> {bail.local.numero_porte}<br>
                    <strong>Locataire :</strong> {bail.occupants.first() or 'Inconnu'}
                </div>
                <form method="POST">
                    <input type="hidden" name="csrfmiddlewaretoken" value="{csrf_token}">
                    <p style="font-weight:bold; color:#555;">Sélectionnez les échéances :</p>
                    {options_html}
                    <button type="submit">Générer le PDF</button>
                </form>
            </div>
        </body>
        </html>
        '''
        return HttpResponse(html)

    # --- GENERATION PDF ---
    selected_dates = request.POST.getlist('dates')
    selected_dates.sort() # Ordre chronologique
    
    # Préparation du nom de fichier (AE + Nom + Période)
    occupant_f = bail.occupants.filter(role='LOCATAIRE').first()
    nom_locataire = occupant_f.nom.upper().replace(" ", "_") if occupant_f else "Inconnu"
    
    if selected_dates:
        d_debut = datetime.strptime(selected_dates[0], '%Y-%m-%d')
        d_fin = datetime.strptime(selected_dates[-1], '%Y-%m-%d')
        periode_str = d_debut.strftime('%Y-%m') if d_debut == d_fin else f"{d_debut.strftime('%Y-%m')}_au_{d_fin.strftime('%Y-%m')}"
    else:
        periode_str = datetime.now().strftime('%Y-%m')

    response = HttpResponse(content_type='application/pdf')
    filename = f"AE_{nom_locataire}_{periode_str}.pdf"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    p = canvas.Canvas(response, pagesize=A4)
    
    for date_str in selected_dates:
        date_debut = datetime.strptime(date_str, '%Y-%m-%d').date()
        
        if is_trimestriel:
            mois_fin = date_debut.month + 2
            annee_fin = date_debut.year
            if mois_fin > 12:
                mois_fin -= 12
                annee_fin += 1
            last_day = calendar.monthrange(annee_fin, mois_fin)[1]
            date_fin = date(annee_fin, mois_fin, last_day)
        else:
            last_day = calendar.monthrange(date_debut.year, date_debut.month)[1]
            date_fin = date_debut.replace(day=last_day)

        # --- DESSIN DE L'AVIS D'ECHEANCE (DESIGN PRO) ---
        
        # 1. En-tête avec fond gris
        p.setFillColor(colors.HexColor("#E0E0E0"))
        p.rect(1*cm, 26*cm, 19*cm, 2.5*cm, fill=1, stroke=0)
        p.setFillColor(colors.black)
        
        p.setFont("Helvetica-Bold", 16)
        p.drawCentredString(10.5*cm, 27.2*cm, "AVIS D'ÉCHÉANCE")
        p.setFont("Helvetica", 11)
        p.drawCentredString(10.5*cm, 26.4*cm, f"Période du {date_debut.strftime('%d/%m/%Y')} au {date_fin.strftime('%d/%m/%Y')}")

        # 2. Cadres Bailleur / Locataire
        # --- Bailleur (Gauche) ---
        p.setStrokeColor(colors.grey)
        p.rect(1*cm, 21.5*cm, 9*cm, 3.5*cm)
        p.setFillColor(colors.HexColor("#F5F5F5"))
        p.rect(1*cm, 24.2*cm, 9*cm, 0.8*cm, fill=1, stroke=1)
        p.setFillColor(colors.black)
        p.setFont("Helvetica-Bold", 11)
        p.drawCentredString(5.5*cm, 24.4*cm, "BAILLEUR")
        
        p.setFont("Helvetica", 10)
        y_text = 23.5*cm
        proprietaire = bail.local.immeuble.proprietaire
        if proprietaire:
            p.drawString(1.5*cm, y_text, proprietaire.nom)
            p.drawString(1.5*cm, y_text-0.5*cm, proprietaire.adresse)
            p.drawString(1.5*cm, y_text-1.0*cm, f"{proprietaire.code_postal} {proprietaire.ville}")
        else:
            p.drawString(1.5*cm, y_text, bail.local.immeuble.nom)
            p.drawString(1.5*cm, y_text-0.5*cm, bail.local.immeuble.adresse)
            p.drawString(1.5*cm, y_text-1.0*cm, f"{bail.local.immeuble.code_postal} {bail.local.immeuble.ville}")

        # --- Locataire (Droite) ---
        p.rect(11*cm, 21.5*cm, 9*cm, 3.5*cm)
        p.setFillColor(colors.HexColor("#F5F5F5"))
        p.rect(11*cm, 24.2*cm, 9*cm, 0.8*cm, fill=1, stroke=1)
        p.setFillColor(colors.black)
        p.setFont("Helvetica-Bold", 11)
        p.drawCentredString(15.5*cm, 24.4*cm, "LOCATAIRE")
        
        p.setFont("Helvetica", 10)
        occupant = bail.occupants.filter(role='LOCATAIRE').first()
        if occupant:
            p.drawString(11.5*cm, y_text, f"{occupant.prenom} {occupant.nom.upper()}")
        else:
            p.drawString(11.5*cm, y_text, "Locataire inconnu")
            
        immeuble = bail.local.immeuble
        p.drawString(11.5*cm, y_text-0.5*cm, immeuble.adresse)
        p.drawString(11.5*cm, y_text-1.0*cm, f"{immeuble.code_postal} {immeuble.ville}")
        p.drawString(11.5*cm, y_text-1.5*cm, f"Porte : {bail.local.numero_porte}")

        # 3. Détail des sommes
        y = 18*cm
        p.setFont("Helvetica-Bold", 12)
        p.drawString(1*cm, y, "Détail du règlement")
        p.setStrokeColor(colors.black)
        p.line(1*cm, y-0.2*cm, 20*cm, y-0.2*cm)
        
        y -= 1.5*cm
        p.setFont("Helvetica", 11)
        
        # Ligne Loyer
        p.drawString(1.5*cm, y, "Loyer Hors Charges")
        p.drawRightString(19.5*cm, y, format_euro(bail.loyer_hc * multiplicateur))
        p.setStrokeColor(colors.lightgrey)
        p.line(1*cm, y-0.3*cm, 20*cm, y-0.3*cm)
        y -= 1*cm
        
        # Ligne Charges
        p.drawString(1.5*cm, y, "Provisions sur charges")
        p.drawRightString(19.5*cm, y, format_euro(bail.charges * multiplicateur))
        p.line(1*cm, y-0.3*cm, 20*cm, y-0.3*cm)
        y -= 1*cm
        
        # Ligne Taxes
        if bail.taxes > 0:
            p.drawString(1.5*cm, y, "Taxes (non soumises TVA)")
            p.drawRightString(19.5*cm, y, format_euro(bail.taxes * multiplicateur))
            p.line(1*cm, y-0.3*cm, 20*cm, y-0.3*cm)
            y -= 1*cm
        
        if bail.soumis_tva:
            p.drawString(1.5*cm, y, f"TVA ({bail.taux_tva} %)")
            p.drawRightString(19.5*cm, y, format_euro(bail.montant_tva * multiplicateur))
            p.line(1*cm, y-0.3*cm, 20*cm, y-0.3*cm)
            y -= 1*cm
        
        # 4. Total
        y -= 0.5*cm
        p.setFillColor(colors.HexColor("#E0E0E0"))
        p.rect(10*cm, y-0.5*cm, 10*cm, 1.2*cm, fill=1, stroke=0)
        p.setFillColor(colors.black)
        p.setFont("Helvetica-Bold", 14)
        p.drawString(10.5*cm, y, "TOTAL À PAYER")
        p.drawRightString(19.5*cm, y, format_euro(bail.loyer_ttc * multiplicateur))
        
        # Date limite
        p.setFont("Helvetica-Bold", 10)
        date_limite = date_debut.replace(day=5)
        p.drawCentredString(15*cm, y-1.5*cm, f"À régler avant le : {date_limite.strftime('%d/%m/%Y')}")

        p.showPage()

    p.save()
    return response

def generer_regularisation_pdf(request, pk):
    """Génère le décompte de régularisation de charges sur une période donnée."""
    bail = Bail.objects.get(pk=pk)
    
    # --- 1. Formulaire de sélection de la période ---
    if request.method != 'POST':
        csrf_token = get_token(request)
        # Par défaut : Année précédente
        annee_prec = datetime.now().year - 1
        default_start = f"{annee_prec}-01-01"
        default_end = f"{annee_prec}-12-31"
        
        html = f'''
        <html>
        <head>
            <title>Régularisation de Charges</title>
            <style>
                body {{ font-family: sans-serif; padding: 40px; background-color: #f4f6f9; }}
                .container {{ max-width: 500px; margin: 0 auto; background: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
                h2 {{ color: #333; margin-top: 0; }}
                label {{ display: block; margin-top: 15px; font-weight: bold; color: #555; }}
                input {{ width: 100%; padding: 10px; margin-top: 5px; border: 1px solid #ddd; border-radius: 4px; box-sizing: border-box; }}
                button {{ margin-top: 25px; width: 100%; padding: 12px; background-color: #417690; color: white; border: none; border-radius: 4px; font-size: 16px; cursor: pointer; }}
                button:hover {{ background-color: #2a5366; }}
                .info {{ margin-bottom: 20px; padding: 10px; background-color: #e8f4f8; border-left: 4px solid #417690; color: #2c3e50; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h2>Régularisation de Charges</h2>
                <div class="info">
                    <strong>Bail :</strong> {bail.local.numero_porte}<br>
                    <strong>Locataire :</strong> {bail.occupants.first() or 'Inconnu'}
                </div>
                <form method="POST">
                    <input type="hidden" name="csrfmiddlewaretoken" value="{csrf_token}">
                    
                    <label>Date de début :</label>
                    <input type="date" name="date_debut" required value="{default_start}">
                    
                    <label>Date de fin :</label>
                    <input type="date" name="date_fin" required value="{default_end}">
                    
                    <button type="submit">Générer la Régularisation</button>
                </form>
            </div>
        </body>
        </html>
        '''
        return HttpResponse(html)

    # --- 2. Traitement des dates et calculs ---
    date_debut_str = request.POST.get('date_debut')
    date_fin_str = request.POST.get('date_fin')
    
    date_debut = datetime.strptime(date_debut_str, '%Y-%m-%d').date()
    date_fin = datetime.strptime(date_fin_str, '%Y-%m-%d').date()
    
    # Calcul de la durée totale de la période de régularisation
    nb_jours_periode = (date_fin - date_debut).days + 1
    
    # Calcul de la présence du locataire sur cette période (Intersection)
    debut_occup = max(date_debut, bail.date_debut)
    fin_occup = date_fin
    if bail.date_fin:
        fin_occup = min(date_fin, bail.date_fin)
    
    nb_jours_presence = 0
    if debut_occup <= fin_occup:
        nb_jours_presence = (fin_occup - debut_occup).days + 1
    
    # Ratio de présence (Prorata Temporis)
    ratio_temps = 0
    if nb_jours_periode > 0:
        ratio_temps = nb_jours_presence / nb_jours_periode

    # --- GENERATION PDF ---
    response = HttpResponse(content_type='application/pdf')
    filename = f"Regularisation_{date_debut_str}_{date_fin_str}.pdf"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    p = canvas.Canvas(response, pagesize=A4)
    
    # 1. En-tête (Design Pro)
    p.setFillColor(colors.HexColor("#E0E0E0"))
    p.rect(1*cm, 26*cm, 19*cm, 2.5*cm, fill=1, stroke=0)
    p.setFillColor(colors.black)
    
    p.setFont("Helvetica-Bold", 16)
    p.drawCentredString(10.5*cm, 27.2*cm, "RÉGULARISATION DE CHARGES")
    p.setFont("Helvetica", 11)
    p.drawCentredString(10.5*cm, 26.4*cm, f"Période du {date_debut.strftime('%d/%m/%Y')} au {date_fin.strftime('%d/%m/%Y')}")
    
    # Infos contextuelles
    p.setFont("Helvetica", 10)
    p.drawString(2*cm, 25*cm, f"Locataire : {bail.occupants.first() or 'Inconnu'}")
    p.drawString(2*cm, 24.5*cm, f"Temps de présence : {nb_jours_presence} jours sur {nb_jours_periode} jours (Prorata : {ratio_temps*100:.2f}%)")

    # --- CALCULS ---
    # Liste pour stocker le détail des calculs pour l'annexe
    details_calculs = []
    details_calculs.append("--- PARAMÈTRES GÉNÉRAUX ---")
    details_calculs.append(f"Période Régul : {date_debut} au {date_fin} ({nb_jours_periode} jours)")
    details_calculs.append(f"Présence Locataire : {nb_jours_presence} jours (Ratio global : {ratio_temps:.6f})")
    details_calculs.append("")
    details_calculs.append("--- DÉTAIL DÉPENSES ---")

    # On cherche les dépenses qui sont dans la période (date facture) OU qui chevauchent la période (période de service)
    depenses = Depense.objects.filter(
        Q(immeuble=bail.local.immeuble) & 
        (
            Q(date__range=[date_debut, date_fin]) | 
            Q(date_debut__lte=date_fin, date_fin__gte=date_debut)
        )
    ).distinct()
    
    total_part_locataire = 0
    y = 23*cm
    
    p.setFont("Helvetica-Bold", 10)
    p.drawString(2*cm, y, "Détail des dépenses réelles :")
    y -= 1*cm
    p.setFont("Helvetica", 9)
    p.drawString(2*cm, y, "Nature")
    p.drawString(10*cm, y, "Montant Immeuble")
    p.drawString(14*cm, y, "Votre Quote-part")
    y -= 0.6*cm

    for depense in depenses:
        cle = depense.cle_repartition
        if cle:
            # Récupérer la part du local
            qp_local = cle.quote_parts.filter(local=bail.local).first()
            # Récupérer le total de la clé (somme des tantièmes)
            total_cle = cle.quote_parts.aggregate(Sum('valeur'))['valeur__sum'] or 0
            
            if qp_local and total_cle > 0:
                part_theorique = (depense.montant * qp_local.valeur) / total_cle
                
                # LOGIQUE DE PRORATA INTELLIGENTE
                if depense.date_debut and depense.date_fin:
                    # Cas 1 : Dépense avec période définie (ex: Taxe Foncière, Assurance)
                    # On calcule l'intersection exacte entre [Dépense] et [Présence Locataire dans la période de régul]
                    
                    # Durée totale de la dépense (ex: 365 jours)
                    duree_depense = (depense.date_fin - depense.date_debut).days + 1
                    if duree_depense <= 0: duree_depense = 1
                    
                    # Intersection [Dépense] AND [Régul] AND [Locataire]
                    # On restreint d'abord la dépense à la période de régul demandée
                    start_inter = max(depense.date_debut, date_debut)
                    end_inter = min(depense.date_fin, date_fin)
                    
                    # Puis on croise avec la présence du locataire
                    start_final = max(start_inter, debut_occup)
                    end_final = min(end_inter, fin_occup)
                    
                    nb_jours_facturables = 0
                    if start_final <= end_final:
                        nb_jours_facturables = (end_final - start_final).days + 1
                    
                    # Montant = (Montant Total / Durée Dépense) * Jours Facturables
                    part_reelle = float(part_theorique) * (nb_jours_facturables / duree_depense)
                    
                    details_calculs.append(f"[Dépense] {depense.libelle} ({format_euro(depense.montant)})")
                    details_calculs.append(f"  > Période facture : {depense.date_debut} au {depense.date_fin} ({duree_depense} jours)")
                    details_calculs.append(f"  > Intersection présence : {nb_jours_facturables} jours")
                    details_calculs.append(f"  > Calcul : {float(part_theorique):.2f}€ x ({nb_jours_facturables}/{duree_depense}) = {part_reelle:.2f}€")
                    
                else:
                    # Cas 2 : Dépense sans période (ex: Ampoule, Réparation ponctuelle)
                    # On garde l'ancien système : si la date est dans la période, on lisse selon la présence globale
                    if not (date_debut <= depense.date <= date_fin):
                        continue # Hors période
                    part_reelle = float(part_theorique) * ratio_temps
                    
                    details_calculs.append(f"[Dépense] {depense.libelle} ({format_euro(depense.montant)})")
                    details_calculs.append(f"  > Sans période (Date: {depense.date}) -> Lissage global")
                    details_calculs.append(f"  > Calcul : {float(part_theorique):.2f}€ x Ratio {ratio_temps:.4f} = {part_reelle:.2f}€")
                
                total_part_locataire += part_reelle
                
                libelle_aff = f"{depense.libelle} ({cle.nom})"
                if depense.date_debut and depense.date_fin:
                     libelle_aff += f" [{depense.date_debut.strftime('%d/%m')} au {depense.date_fin.strftime('%d/%m')}]"
                
                p.drawString(2*cm, y, libelle_aff[:60])
                p.drawString(10*cm, y, format_euro(depense.montant))
                p.drawString(14*cm, y, format_euro(part_reelle))
                y -= 0.5*cm
    
    # --- CONSOMMATIONS (Compteurs) ---
    # On cherche les relevés qui chevauchent la période de régularisation
    consommations = Consommation.objects.filter(
        Q(local=bail.local) &
        (
            Q(date_releve__range=[date_debut, date_fin]) | 
            Q(date_debut__lte=date_fin, date_releve__gte=date_debut)
        )
    ).distinct()

    details_calculs.append("")
    details_calculs.append("--- DÉTAIL CONSOMMATIONS ---")

    for conso in consommations:
        cle = conso.cle_repartition
        if cle.prix_unitaire:
            quantite_reelle = float(conso.quantite)
            
            # PRORATISATION DE LA CONSOMMATION
            if conso.date_debut:
                # Durée totale de ce relevé (ex: 6 mois)
                duree_conso = (conso.date_releve - conso.date_debut).days + 1
                if duree_conso <= 0: duree_conso = 1
                
                # Intersection avec la période de régul
                start_inter = max(conso.date_debut, date_debut)
                end_inter = min(conso.date_releve, date_fin)
                
                nb_jours_conso = 0
                if start_inter <= end_inter:
                    nb_jours_conso = (end_inter - start_inter).days + 1
                
                # On ne garde que la part qui concerne la période de régul
                quantite_reelle = quantite_reelle * (nb_jours_conso / duree_conso)
                
                details_calculs.append(f"[Conso] {cle.nom} (Relevé: {conso.quantite})")
                details_calculs.append(f"  > Période relevé : {conso.date_debut} au {conso.date_releve} ({duree_conso} jours)")
                details_calculs.append(f"  > Intersection régul : {nb_jours_conso} jours")
                details_calculs.append(f"  > Qté retenue : {float(conso.quantite):.2f} x ({nb_jours_conso}/{duree_conso}) = {quantite_reelle:.2f}")
            else:
                details_calculs.append(f"[Conso] {cle.nom} (Relevé: {conso.quantite}) - 100% retenu")
            
            montant_conso = quantite_reelle * float(cle.prix_unitaire)
            total_part_locataire += montant_conso
            
            libelle_conso = f"{cle.nom} (Relevé: {conso.quantite})"
            if conso.date_debut:
                libelle_conso += f" [Prorata: {quantite_reelle:.2f}]"
            
            p.drawString(2*cm, y, libelle_conso)
            p.drawString(10*cm, y, f"PU: {format_euro(cle.prix_unitaire)}")
            p.drawString(14*cm, y, format_euro(montant_conso))
            y -= 0.5*cm

    # --- AJUSTEMENTS MANUELS ---
    ajustements = Ajustement.objects.filter(bail=bail, date__range=[date_debut, date_fin])
    for ajustement in ajustements:
        total_part_locataire += float(ajustement.montant)
        p.drawString(2*cm, y, f"Ajustement : {ajustement.libelle}")
        p.drawString(10*cm, y, "-")
        p.drawString(14*cm, y, format_euro(ajustement.montant))
        y -= 0.5*cm

    # --- BILAN ---
    y -= 1*cm
    p.setFont("Helvetica-Bold", 11)
    p.drawString(10*cm, y, f"TOTAL DÉPENSES RÉELLES : {format_euro(total_part_locataire)}")
    
    # --- CALCUL DES PROVISIONS DUES ---
    # Nouvelle logique : Calcul mois par mois pour respecter le montant mensuel fixe
    total_provisions = 0.0
    details_calculs.append("")
    details_calculs.append("--- DÉTAIL PROVISIONS (Calcul Mensuel) ---")
    details_calculs.append(f"Provision mensuelle : {bail.charges}€")

    # Période d'occupation effective sur la période de régul
    start_date = max(date_debut, bail.date_debut)
    end_date = date_fin
    if bail.date_fin:
        end_date = min(date_fin, bail.date_fin)

    if start_date <= end_date:
        # On itère du premier jour du mois de départ jusqu'à la fin
        curr = date(start_date.year, start_date.month, 1)
        
        while curr <= end_date:
            # Fin du mois courant
            last_day_month = calendar.monthrange(curr.year, curr.month)[1]
            month_end_date = date(curr.year, curr.month, last_day_month)
            
            # Intersection avec l'occupation
            p_start = max(curr, start_date)
            p_end = min(month_end_date, end_date)
            
            if p_start <= p_end:
                nb_jours_presence_mois = (p_end - p_start).days + 1
                nb_jours_mois = last_day_month
                
                if nb_jours_presence_mois == nb_jours_mois:
                    montant_mois = float(bail.charges)
                    details_calculs.append(f"  > {curr.strftime('%m/%Y')} : Mois complet -> {montant_mois:.2f}€")
                else:
                    montant_mois = float(bail.charges) * (nb_jours_presence_mois / nb_jours_mois)
                    details_calculs.append(f"  > {curr.strftime('%m/%Y')} : Partiel ({nb_jours_presence_mois}/{nb_jours_mois}j) -> {montant_mois:.2f}€")
                
                total_provisions += montant_mois
            
            # Mois suivant
            next_month = curr.month + 1
            next_year = curr.year
            if next_month > 12:
                next_month = 1
                next_year += 1
            curr = date(next_year, next_month, 1)
    else:
        details_calculs.append("  > Aucune présence sur la période.")

    details_calculs.append(f"TOTAL PROVISIONS DUES : {total_provisions:.2f}€")
    
    y -= 1*cm
    p.drawString(10*cm, y, f"PROVISIONS VERSÉES : -{format_euro(total_provisions)}")
    
    solde = total_part_locataire - total_provisions
    y -= 1.5*cm
    p.setFont("Helvetica-Bold", 14)
    if solde > 0:
        p.drawString(2*cm, y, f"RESTE À PAYER : {format_euro(solde)}")
    else:
        p.drawString(2*cm, y, f"TROP PERÇU (À REMBOURSER) : {format_euro(abs(solde))}")

    # --- HISTORISATION ---
    # On enregistre cette régularisation dans la base pour garder une trace
    Regularisation.objects.create(
        bail=bail,
        date_debut=date_debut,
        date_fin=date_fin,
        montant_reel=total_part_locataire,
        montant_provisions=total_provisions,
        solde=solde
    )

    # --- PAGE ANNEXE (DÉTAILS CALCULS) ---
    p.showPage() # Nouvelle page
    p.setFont("Helvetica-Bold", 14)
    p.drawString(2*cm, 28*cm, "ANNEXE : DÉTAIL DES CALCULS (ADMINISTRATEUR)")
    p.setFont("Courier", 9) # Police à chasse fixe pour aligner
    y_annex = 27*cm
    
    for line in details_calculs:
        p.drawString(2*cm, y_annex, line)
        y_annex -= 0.5*cm
        if y_annex < 2*cm: # Saut de page si on arrive en bas
            p.showPage()
            p.setFont("Courier", 9)
            y_annex = 28*cm

    p.showPage()
    p.save()
    return response
'''

URLS_APP_CODE = '''
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ImmeubleViewSet, BailViewSet, generer_quittance_pdf, generer_regularisation_pdf, generer_avis_echeance_pdf

router = DefaultRouter()
router.register(r'immeubles', ImmeubleViewSet)
router.register(r'baux', BailViewSet)

urlpatterns = [
    path('quittance/<int:pk>/', generer_quittance_pdf, name='quittance_pdf'),
    path('avis_echeance/<int:pk>/', generer_avis_echeance_pdf, name='avis_echeance_pdf'),
    path('regularisation/<int:pk>/', generer_regularisation_pdf, name='regularisation_pdf'),
    path('', include(router.urls)),
]
'''

URLS_PROJECT_CODE = '''
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('core.urls')),
]
'''

# --- EXECUTION ---

def main():
    print(f"--- Création du projet {PROJECT_NAME} ---")
    
    # 1. Création du projet Django
    if not os.path.exists(PROJECT_NAME):
        run_command(f"django-admin startproject {PROJECT_NAME}")
    else:
        print(f"Le dossier {PROJECT_NAME} existe déjà.")
    
    os.chdir(PROJECT_NAME)
    
    # 2. Création de l'application 'core'
    if not os.path.exists(APP_NAME):
        run_command(f"python manage.py startapp {APP_NAME}")
    
    # 3. Écriture des fichiers de l'application
    base_path = os.path.join(APP_NAME)
    write_file(os.path.join(base_path, 'models.py'), MODELS_CODE)
    write_file(os.path.join(base_path, 'admin.py'), ADMIN_CODE)
    write_file(os.path.join(base_path, 'serializers.py'), SERIALIZERS_CODE)
    write_file(os.path.join(base_path, 'views.py'), VIEWS_CODE)
    write_file(os.path.join(base_path, 'urls.py'), URLS_APP_CODE)
    
    # 4. Mise à jour des URLs du projet principal
    proj_settings_path = os.path.join(PROJECT_NAME, 'urls.py')
    write_file(proj_settings_path, URLS_PROJECT_CODE)

    # 5. Modification de settings.py pour ajouter les apps
    settings_path = os.path.join(PROJECT_NAME, 'settings.py')
    with open(settings_path, 'r') as f:
        settings_content = f.read()
    
    if "'rest_framework'" not in settings_content:
        print("Ajout de jazzmin, rest_framework et core dans settings.py...")
        
        # Ajout de Jazzmin (Interface mobile) avant l'admin par défaut
        if "'jazzmin'" not in settings_content:
            settings_content = settings_content.replace(
                "'django.contrib.admin',",
                "'jazzmin',\n    'django.contrib.admin',"
            )

        new_apps = "    'rest_framework',\n    'core',"
        settings_content = settings_content.replace(
            "'django.contrib.staticfiles',", 
            f"'django.contrib.staticfiles',\n{new_apps}"
        )
        write_file(settings_path, settings_content)

    print("\n--- Installation terminée avec succès ! ---")
    print("Pour lancer votre logiciel :")
    print(f"1. cd {PROJECT_NAME}")
    print("2. python manage.py makemigrations")
    print("3. python manage.py migrate")
    print("4. python manage.py createsuperuser (pour créer votre compte admin)")
    print("5. python manage.py runserver")

if __name__ == "__main__":
    main()
