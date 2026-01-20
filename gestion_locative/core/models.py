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
    REGIME_FISCAL_CHOICES = [
        ('REVENUS_FONCIERS', 'Revenus Fonciers (Réel)'),
        ('MICRO_FONCIER', 'Micro-Foncier'),
        ('LMNP_REEL', 'LMNP Réel'),
        ('LMNP_MICRO', 'LMNP Micro-BIC'),
        ('LMP', 'LMP'),
    ]

    proprietaire = models.ForeignKey(Proprietaire, on_delete=models.SET_NULL, null=True, blank=True, related_name='immeubles', verbose_name="Propriétaire / Bailleur")
    nom = models.CharField(max_length=200)
    adresse = models.TextField()
    ville = models.CharField(max_length=100)
    code_postal = models.CharField(max_length=20)
    date_creation = models.DateTimeField(auto_now_add=True)

    # Champs Acquisition (Phase 1)
    prix_achat = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, verbose_name="Prix d'acquisition (frais inclus)")
    date_achat = models.DateField(null=True, blank=True, verbose_name="Date d'acquisition")
    frais_notaire = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="Frais de notaire")
    frais_agence = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="Frais d'agence")
    regime_fiscal = models.CharField(max_length=20, choices=REGIME_FISCAL_CHOICES, default='REVENUS_FONCIERS', verbose_name="Régime fiscal")

    def __str__(self):
        return f"{self.nom} - {self.ville}"

    @property
    def cout_total_acquisition(self):
        """Coût total d'acquisition incluant frais."""
        total = self.prix_achat or 0
        total += self.frais_notaire or 0
        total += self.frais_agence or 0
        return total

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
    surface_m2 = models.DecimalField(max_digits=6, decimal_places=2, verbose_name="Surface (m²)")
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
    depot_garantie = models.DecimalField(max_digits=8, decimal_places=2, default=0.00, verbose_name="Dépôt de garantie")
    actif = models.BooleanField(default=True)

    # Gestion de la TVA
    soumis_tva = models.BooleanField(default=False, verbose_name="Soumis à la TVA")
    taux_tva = models.DecimalField(max_digits=5, decimal_places=2, default=20.00, help_text="En % (ex: 20.00)")

    # NOTE: loyer_hc, charges, taxes, indice_reference, trimestre_reference
    # sont maintenant gérés via le modèle BailTarification (voir properties ci-dessous)

    @property
    def montant_tva(self):
        if not self.soumis_tva:
            return 0
        return ((self.loyer_hc + self.charges) * self.taux_tva) / 100

    @property
    def loyer_ttc(self):
        return float(self.loyer_hc) + float(self.charges) + float(self.taxes) + float(self.montant_tva)

    # === TARIFICATION HISTORY METHODS ===

    def get_tarification_at(self, target_date):
        """Récupère la tarification active à une date donnée."""
        from django.db.models import Q
        return self.tarifications.filter(
            date_debut__lte=target_date
        ).filter(
            Q(date_fin__gte=target_date) | Q(date_fin__isnull=True)
        ).first()

    def get_tarifications_for_period(self, start_date, end_date):
        """Récupère toutes les tarifications qui chevauchent une période."""
        from django.db.models import Q
        return self.tarifications.filter(
            Q(date_debut__lte=end_date) &
            (Q(date_fin__gte=start_date) | Q(date_fin__isnull=True))
        ).order_by('date_debut')

    @property
    def tarification_actuelle(self):
        """Tarification active aujourd'hui."""
        from django.utils import timezone
        return self.get_tarification_at(timezone.now().date())

    # === BACKWARD COMPATIBILITY PROPERTIES ===
    # Ces properties permettent d'accéder aux valeurs actuelles via bail.loyer_hc, bail.charges, etc.
    # même après la suppression des champs de la base de données

    @property
    def loyer_hc(self):
        """Loyer HC de la tarification actuelle."""
        tarif = self.tarification_actuelle
        return tarif.loyer_hc if tarif else 0

    @property
    def charges(self):
        """Charges de la tarification actuelle."""
        tarif = self.tarification_actuelle
        return tarif.charges if tarif else 0

    @property
    def taxes(self):
        """Taxes de la tarification actuelle."""
        tarif = self.tarification_actuelle
        return tarif.taxes if tarif else 0

    @property
    def indice_reference(self):
        """Indice de référence de la tarification actuelle."""
        tarif = self.tarification_actuelle
        return tarif.indice_reference if tarif else None

    @property
    def trimestre_reference(self):
        """Trimestre de référence de la tarification actuelle."""
        tarif = self.tarification_actuelle
        return tarif.trimestre_reference if tarif else ""

    def __str__(self):
        return f"Bail {self.local} ({self.date_debut})"

    class Meta:
        verbose_name = "Bail"
        verbose_name_plural = "Baux"

class BailTarification(models.Model):
    """Historique des tarifications d'un bail."""

    # Relations
    bail = models.ForeignKey(
        Bail,
        on_delete=models.CASCADE,
        related_name='tarifications',
        verbose_name="Bail"
    )

    # Période de validité
    date_debut = models.DateField(
        verbose_name="Date de début",
        help_text="Date d'entrée en vigueur de cette tarification"
    )
    date_fin = models.DateField(
        null=True,
        blank=True,
        verbose_name="Date de fin",
        help_text="None = encore active"
    )

    # Montants (identiques aux champs actuels du Bail)
    loyer_hc = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        verbose_name="Loyer HC"
    )
    charges = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=0.00,
        verbose_name="Provisions charges"
    )
    taxes = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=0.00,
        verbose_name="Taxes"
    )

    # Indexation (transféré depuis Bail)
    indice_reference = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Indice IRL/ILC"
    )
    trimestre_reference = models.CharField(
        max_length=20,
        blank=True,
        help_text="Ex: T1 2024"
    )

    # Audit
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Créée le"
    )
    reason = models.CharField(
        max_length=200,
        blank=True,
        verbose_name="Motif du changement",
        help_text="Ex: Révision IRL, Augmentation négociée, Tarification initiale"
    )
    notes = models.TextField(
        blank=True,
        verbose_name="Notes"
    )

    class Meta:
        verbose_name = "Tarification"
        verbose_name_plural = "Tarifications"
        ordering = ['-date_debut']

    def __str__(self):
        date_fin_str = self.date_fin.strftime('%d/%m/%Y') if self.date_fin else 'en cours'
        return f"{self.bail.local.numero_porte} - Du {self.date_debut.strftime('%d/%m/%Y')} au {date_fin_str}"

    def clean(self):
        """Validation pour éviter les chevauchements et incohérences."""
        from django.core.exceptions import ValidationError
        from datetime import date
        errors = {}

        # 1. date_fin > date_debut
        if self.date_fin and self.date_fin <= self.date_debut:
            errors['date_fin'] = "La date de fin doit être postérieure à la date de début."

        # 2. Vérifier les chevauchements
        if self.bail_id:
            overlapping = BailTarification.objects.filter(bail=self.bail).exclude(pk=self.pk)
            for other in overlapping:
                if other.date_fin is None:
                    if self.date_fin is None or self.date_debut <= other.date_debut:
                        errors['date_debut'] = f"Chevauchement avec tarification active du {other.date_debut.strftime('%d/%m/%Y')}."
                        break
                else:
                    self_fin = self.date_fin if self.date_fin else date(9999, 12, 31)
                    if not (self_fin < other.date_debut or self.date_debut > other.date_fin):
                        errors['date_debut'] = f"Chevauchement avec période {other.date_debut.strftime('%d/%m/%Y')} - {other.date_fin.strftime('%d/%m/%Y')}."
                        break

        # 3. Date début >= début du bail
        if self.bail_id and self.bail.date_debut:
            if self.date_debut < self.bail.date_debut:
                errors['date_debut'] = "La tarification ne peut pas commencer avant le début du bail."

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

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

    # Nouveaux champs de suivi des paiements
    payee = models.BooleanField(default=False, verbose_name="Payée")
    date_paiement = models.DateField(null=True, blank=True, verbose_name="Date de paiement")
    notes = models.TextField(blank=True, verbose_name="Notes / Commentaires")

    def __str__(self):
        return f"Régul du {self.date_debut} au {self.date_fin} ({self.solde}€)"

    def clean(self):
        """Validation des champs de paiement."""
        from django.core.exceptions import ValidationError

        # Date de paiement uniquement si payée
        if self.date_paiement and not self.payee:
            raise ValidationError({
                'date_paiement': 'Une date de paiement ne peut être définie que si la régularisation est marquée comme payée.'
            })

        # Date de paiement après date de création
        if self.date_paiement and self.date_creation:
            if self.date_paiement < self.date_creation.date():
                raise ValidationError({
                    'date_paiement': 'La date de paiement ne peut pas être antérieure à la date de création.'
                })

    class Meta:
        verbose_name = "Régularisation"
        verbose_name_plural = "Régularisations"
        ordering = ['-date_creation']


# =============================================================================
# GESTION DE PATRIMOINE - Nouveaux modèles
# =============================================================================

class EstimationValeur(models.Model):
    """Historique des estimations de valeur d'un immeuble."""
    SOURCE_CHOICES = [
        ('MANUELLE', 'Estimation manuelle'),
        ('AGENT', 'Agent immobilier'),
        ('NOTAIRE', 'Notaire'),
        ('DVF', 'Données DVF'),
    ]

    immeuble = models.ForeignKey(Immeuble, on_delete=models.CASCADE, related_name='estimations')
    date_estimation = models.DateField(verbose_name="Date de l'estimation")
    valeur_estimee = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Valeur estimée (€)")
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default='MANUELLE')
    notes = models.TextField(blank=True, verbose_name="Notes / Commentaires")

    def __str__(self):
        return f"{self.immeuble.nom} - {self.valeur_estimee}€ ({self.date_estimation})"

    class Meta:
        verbose_name = "Estimation de valeur"
        verbose_name_plural = "Estimations de valeur"
        ordering = ['-date_estimation']


class CreditImmobilier(models.Model):
    """Crédits immobiliers liés à un immeuble."""
    TYPE_CREDIT_CHOICES = [
        ('AMORTISSABLE', 'Amortissable'),
        ('IN_FINE', 'In Fine'),
    ]

    immeuble = models.ForeignKey(Immeuble, on_delete=models.CASCADE, related_name='credits')
    nom_banque = models.CharField(max_length=100, verbose_name="Nom de la banque")
    numero_pret = models.CharField(max_length=50, blank=True, verbose_name="Numéro de prêt")
    capital_emprunte = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Capital emprunté (€)")
    taux_interet = models.DecimalField(max_digits=5, decimal_places=3, verbose_name="Taux d'intérêt (%)", help_text="Ex: 2.5 pour 2,5%")
    duree_mois = models.PositiveIntegerField(verbose_name="Durée (mois)")
    date_debut = models.DateField(verbose_name="Date de début du prêt")
    type_credit = models.CharField(max_length=20, choices=TYPE_CREDIT_CHOICES, default='AMORTISSABLE')
    assurance_mensuelle = models.DecimalField(max_digits=8, decimal_places=2, default=0, verbose_name="Assurance mensuelle (€)")

    def __str__(self):
        return f"{self.nom_banque} - {self.capital_emprunte}€ ({self.immeuble.nom})"

    @property
    def mensualite_hors_assurance(self):
        """Calcule la mensualité hors assurance (formule prêt amortissable)."""
        if self.type_credit == 'IN_FINE':
            # In fine : on ne paie que les intérêts mensuellement
            return (float(self.capital_emprunte) * float(self.taux_interet) / 100) / 12
        else:
            # Amortissable : formule classique
            capital = float(self.capital_emprunte)
            taux_mensuel = float(self.taux_interet) / 100 / 12
            n = self.duree_mois
            if taux_mensuel == 0:
                return capital / n
            return capital * (taux_mensuel * (1 + taux_mensuel) ** n) / ((1 + taux_mensuel) ** n - 1)

    @property
    def mensualite(self):
        """Mensualité totale avec assurance."""
        return self.mensualite_hors_assurance + float(self.assurance_mensuelle)

    @property
    def date_fin(self):
        """Date de fin du prêt."""
        from dateutil.relativedelta import relativedelta
        return self.date_debut + relativedelta(months=self.duree_mois)

    @property
    def capital_restant_du(self):
        """Capital restant dû à la date du jour."""
        from django.utils import timezone
        return self.get_capital_restant_du_at(timezone.now().date())

    def get_capital_restant_du_at(self, target_date):
        """Calcule le capital restant dû à une date donnée."""
        if target_date < self.date_debut:
            return float(self.capital_emprunte)
        if target_date >= self.date_fin:
            return 0

        # Compter le nombre de mois écoulés
        from dateutil.relativedelta import relativedelta
        delta = relativedelta(target_date, self.date_debut)
        mois_ecoules = delta.years * 12 + delta.months

        if self.type_credit == 'IN_FINE':
            # In fine : capital remboursé en totalité à la fin
            return float(self.capital_emprunte)
        else:
            # Amortissable : calculer le CRD
            capital = float(self.capital_emprunte)
            taux_mensuel = float(self.taux_interet) / 100 / 12
            if taux_mensuel == 0:
                return capital - (capital / self.duree_mois * mois_ecoules)
            mensualite = self.mensualite_hors_assurance
            crd = capital * ((1 + taux_mensuel) ** mois_ecoules) - mensualite * (((1 + taux_mensuel) ** mois_ecoules - 1) / taux_mensuel)
            return max(0, crd)

    class Meta:
        verbose_name = "Crédit immobilier"
        verbose_name_plural = "Crédits immobiliers"


class EcheanceCredit(models.Model):
    """Échéancier détaillé d'un crédit immobilier."""
    credit = models.ForeignKey(CreditImmobilier, on_delete=models.CASCADE, related_name='echeances')
    date_echeance = models.DateField(verbose_name="Date d'échéance")
    numero_echeance = models.PositiveIntegerField(verbose_name="N° échéance")
    capital_rembourse = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Capital remboursé")
    interets = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Intérêts")
    assurance = models.DecimalField(max_digits=8, decimal_places=2, verbose_name="Assurance")
    capital_restant_du = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Capital restant dû")
    payee = models.BooleanField(default=False, verbose_name="Payée")
    date_paiement = models.DateField(null=True, blank=True, verbose_name="Date de paiement")

    @property
    def mensualite_totale(self):
        """Total de l'échéance."""
        return float(self.capital_rembourse) + float(self.interets) + float(self.assurance)

    def __str__(self):
        return f"Échéance {self.numero_echeance} - {self.date_echeance}"

    class Meta:
        verbose_name = "Échéance de crédit"
        verbose_name_plural = "Échéances de crédit"
        ordering = ['credit', 'numero_echeance']
        unique_together = ('credit', 'numero_echeance')


class ChargeFiscale(models.Model):
    """Charges déductibles pour la fiscalité."""
    TYPE_CHARGE_CHOICES = [
        ('INTERETS', 'Intérêts d\'emprunt'),
        ('ASSURANCE_EMPRUNT', 'Assurance emprunt'),
        ('ASSURANCE_PNO', 'Assurance PNO'),
        ('TRAVAUX', 'Travaux'),
        ('TAXE_FONCIERE', 'Taxe foncière'),
        ('FRAIS_GESTION', 'Frais de gestion'),
        ('FRAIS_COMPTABLE', 'Frais comptables'),
        ('FRAIS_COPROPRIETE', 'Charges copropriété non récupérables'),
        ('AUTRES', 'Autres charges'),
    ]

    immeuble = models.ForeignKey(Immeuble, on_delete=models.CASCADE, related_name='charges_fiscales')
    type_charge = models.CharField(max_length=30, choices=TYPE_CHARGE_CHOICES, verbose_name="Type de charge")
    annee = models.PositiveIntegerField(verbose_name="Année fiscale")
    montant = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Montant (€)")
    libelle = models.CharField(max_length=200, blank=True, verbose_name="Libellé détaillé")
    justificatif = models.FileField(upload_to='justificatifs_fiscaux/', null=True, blank=True, verbose_name="Justificatif")
    date_creation = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.get_type_charge_display()} {self.annee} - {self.montant}€"

    class Meta:
        verbose_name = "Charge fiscale"
        verbose_name_plural = "Charges fiscales"
        ordering = ['-annee', 'type_charge']


class Amortissement(models.Model):
    """Tableau d'amortissement pour LMNP (optionnel)."""
    TYPE_BIEN_CHOICES = [
        ('IMMEUBLE', 'Immeuble (bâti)'),
        ('MOBILIER', 'Mobilier'),
        ('TRAVAUX', 'Travaux'),
    ]

    immeuble = models.ForeignKey(Immeuble, on_delete=models.CASCADE, related_name='amortissements')
    type_bien = models.CharField(max_length=20, choices=TYPE_BIEN_CHOICES, verbose_name="Type de bien")
    libelle = models.CharField(max_length=200, verbose_name="Libellé")
    valeur_origine = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Valeur d'origine (€)")
    date_mise_service = models.DateField(verbose_name="Date de mise en service")
    duree_amortissement = models.PositiveIntegerField(verbose_name="Durée d'amortissement (années)")

    @property
    def dotation_annuelle(self):
        """Dotation annuelle aux amortissements."""
        return float(self.valeur_origine) / self.duree_amortissement

    @property
    def date_fin_amortissement(self):
        """Date de fin d'amortissement."""
        from dateutil.relativedelta import relativedelta
        return self.date_mise_service + relativedelta(years=self.duree_amortissement)

    def get_valeur_nette_comptable(self, target_date):
        """Valeur nette comptable à une date donnée."""
        if target_date < self.date_mise_service:
            return float(self.valeur_origine)
        if target_date >= self.date_fin_amortissement:
            return 0

        from dateutil.relativedelta import relativedelta
        delta = relativedelta(target_date, self.date_mise_service)
        annees_ecoulees = delta.years + (1 if delta.months >= 6 else 0)  # Prorata simplifié
        amortissement_cumule = self.dotation_annuelle * annees_ecoulees
        return max(0, float(self.valeur_origine) - amortissement_cumule)

    def __str__(self):
        return f"{self.libelle} - {self.valeur_origine}€ sur {self.duree_amortissement} ans"

    class Meta:
        verbose_name = "Amortissement"
        verbose_name_plural = "Amortissements"


class VacanceLocative(models.Model):
    """Périodes de vacance locative."""
    MOTIF_CHOICES = [
        ('TRAVAUX', 'Travaux'),
        ('RECHERCHE', 'Recherche de locataire'),
        ('DELIBERE', 'Vacance délibérée'),
        ('AUTRE', 'Autre'),
    ]

    local = models.ForeignKey(Local, on_delete=models.CASCADE, related_name='vacances')
    date_debut = models.DateField(verbose_name="Début de vacance")
    date_fin = models.DateField(null=True, blank=True, verbose_name="Fin de vacance")
    motif = models.CharField(max_length=20, choices=MOTIF_CHOICES, default='RECHERCHE')
    notes = models.TextField(blank=True)

    @property
    def duree_jours(self):
        """Durée de la vacance en jours."""
        from django.utils import timezone
        fin = self.date_fin or timezone.now().date()
        return (fin - self.date_debut).days

    def __str__(self):
        fin_str = self.date_fin.strftime('%d/%m/%Y') if self.date_fin else 'en cours'
        return f"{self.local} - Vacance du {self.date_debut.strftime('%d/%m/%Y')} au {fin_str}"

    class Meta:
        verbose_name = "Vacance locative"
        verbose_name_plural = "Vacances locatives"
        ordering = ['-date_debut']