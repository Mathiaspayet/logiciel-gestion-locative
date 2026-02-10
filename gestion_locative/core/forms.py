from django import forms
from core.models import (
    Immeuble, Local, Bail, BailTarification, Occupant,
    Depense, CleRepartition, QuotePart, EstimationValeur,
    CreditImmobilier, Consommation, Regularisation, Ajustement,
)

# Classes CSS communes
INPUT_CLASS = 'w-full px-3 py-2.5 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none'
INPUT_CLASS_MOBILE = 'w-full px-3 py-3 border border-gray-300 rounded-lg text-base focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none'


def _apply_css(form_class):
    """Applique les classes CSS Tailwind a tous les widgets d'un formulaire."""
    original_init = form_class.__init__

    def new_init(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        for field in self.fields.values():
            existing = field.widget.attrs.get('class', '')
            if not existing:
                field.widget.attrs['class'] = INPUT_CLASS

    form_class.__init__ = new_init
    return form_class


# ─── Depense ──────────────────────────────────────────────────────────────────

class DepenseQuickForm(forms.ModelForm):
    """Formulaire rapide d'ajout de depense, optimise mobile."""

    class Meta:
        model = Depense
        fields = ['immeuble', 'libelle', 'montant', 'date', 'cle_repartition', 'date_debut', 'date_fin']
        widgets = {
            'immeuble': forms.Select(attrs={'class': INPUT_CLASS_MOBILE}),
            'libelle': forms.TextInput(attrs={'class': INPUT_CLASS_MOBILE, 'placeholder': 'Ex: Facture EDF'}),
            'montant': forms.NumberInput(attrs={'class': INPUT_CLASS_MOBILE, 'placeholder': '0,00', 'step': '0.01', 'inputmode': 'decimal'}),
            'date': forms.DateInput(attrs={'class': INPUT_CLASS_MOBILE, 'type': 'date'}),
            'cle_repartition': forms.Select(attrs={'class': INPUT_CLASS_MOBILE}),
            'date_debut': forms.DateInput(attrs={'class': INPUT_CLASS_MOBILE, 'type': 'date'}),
            'date_fin': forms.DateInput(attrs={'class': INPUT_CLASS_MOBILE, 'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['cle_repartition'].required = False
        self.fields['cle_repartition'].empty_label = "-- Aucune --"
        self.fields['date_debut'].required = False
        self.fields['date_fin'].required = False


# ─── Immeuble ─────────────────────────────────────────────────────────────────

@_apply_css
class ImmeubleForm(forms.ModelForm):
    class Meta:
        model = Immeuble
        fields = [
            'nom', 'proprietaire', 'adresse', 'ville', 'code_postal',
            'regime_fiscal', 'prix_achat', 'date_achat', 'frais_notaire', 'frais_agence',
        ]
        widgets = {
            'adresse': forms.Textarea(attrs={'rows': 2}),
            'date_achat': forms.DateInput(attrs={'type': 'date'}),
            'prix_achat': forms.NumberInput(attrs={'step': '0.01'}),
            'frais_notaire': forms.NumberInput(attrs={'step': '0.01'}),
            'frais_agence': forms.NumberInput(attrs={'step': '0.01'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['proprietaire'].required = False
        self.fields['prix_achat'].required = False
        self.fields['date_achat'].required = False
        self.fields['frais_notaire'].required = False
        self.fields['frais_agence'].required = False


# ─── Local ────────────────────────────────────────────────────────────────────

@_apply_css
class LocalForm(forms.ModelForm):
    class Meta:
        model = Local
        fields = ['immeuble', 'numero_porte', 'type_local', 'etage', 'surface_m2']
        widgets = {
            'surface_m2': forms.NumberInput(attrs={'step': '0.01'}),
        }


# ─── Bail ─────────────────────────────────────────────────────────────────────

@_apply_css
class BailForm(forms.ModelForm):
    class Meta:
        model = Bail
        fields = [
            'local', 'date_debut', 'date_fin', 'type_charges', 'frequence_paiement',
            'depot_garantie', 'actif', 'soumis_tva', 'taux_tva',
        ]
        widgets = {
            'date_debut': forms.DateInput(attrs={'type': 'date'}),
            'date_fin': forms.DateInput(attrs={'type': 'date'}),
            'depot_garantie': forms.NumberInput(attrs={'step': '0.01'}),
            'taux_tva': forms.NumberInput(attrs={'step': '0.01'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['date_fin'].required = False


# ─── BailTarification ────────────────────────────────────────────────────────

@_apply_css
class BailTarificationForm(forms.ModelForm):
    class Meta:
        model = BailTarification
        fields = [
            'bail', 'date_debut', 'date_fin', 'loyer_hc', 'charges', 'taxes',
            'indice_reference', 'trimestre_reference', 'reason', 'notes',
        ]
        widgets = {
            'date_debut': forms.DateInput(attrs={'type': 'date'}),
            'date_fin': forms.DateInput(attrs={'type': 'date'}),
            'loyer_hc': forms.NumberInput(attrs={'step': '0.01'}),
            'charges': forms.NumberInput(attrs={'step': '0.01'}),
            'taxes': forms.NumberInput(attrs={'step': '0.01'}),
            'indice_reference': forms.NumberInput(attrs={'step': '0.01'}),
            'notes': forms.Textarea(attrs={'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['date_fin'].required = False
        self.fields['indice_reference'].required = False
        self.fields['trimestre_reference'].required = False
        self.fields['reason'].required = False
        self.fields['notes'].required = False


# ─── Occupant ─────────────────────────────────────────────────────────────────

@_apply_css
class OccupantForm(forms.ModelForm):
    class Meta:
        model = Occupant
        fields = ['bail', 'nom', 'prenom', 'email', 'telephone', 'role']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['email'].required = False
        self.fields['telephone'].required = False


# ─── EstimationValeur ─────────────────────────────────────────────────────────

@_apply_css
class EstimationValeurForm(forms.ModelForm):
    class Meta:
        model = EstimationValeur
        fields = ['immeuble', 'date_estimation', 'valeur_estimee', 'source', 'notes']
        widgets = {
            'date_estimation': forms.DateInput(attrs={'type': 'date'}),
            'valeur_estimee': forms.NumberInput(attrs={'step': '0.01'}),
            'notes': forms.Textarea(attrs={'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['notes'].required = False


# ─── CreditImmobilier ───────────────────────────────────────────────────────

@_apply_css
class CreditImmobilierForm(forms.ModelForm):
    class Meta:
        model = CreditImmobilier
        fields = [
            'immeuble', 'nom_banque', 'numero_pret', 'capital_emprunte',
            'taux_interet', 'duree_mois', 'date_debut', 'type_credit',
            'assurance_mensuelle',
        ]
        widgets = {
            'capital_emprunte': forms.NumberInput(attrs={'step': '0.01'}),
            'taux_interet': forms.NumberInput(attrs={'step': '0.001'}),
            'date_debut': forms.DateInput(attrs={'type': 'date'}),
            'assurance_mensuelle': forms.NumberInput(attrs={'step': '0.01'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['numero_pret'].required = False
        self.fields['assurance_mensuelle'].required = False


# ─── Depense (CRUD complet) ─────────────────────────────────────────────────

@_apply_css
class DepenseForm(forms.ModelForm):
    class Meta:
        model = Depense
        fields = ['immeuble', 'libelle', 'montant', 'date', 'cle_repartition', 'date_debut', 'date_fin']
        widgets = {
            'montant': forms.NumberInput(attrs={'step': '0.01'}),
            'date': forms.DateInput(attrs={'type': 'date'}),
            'date_debut': forms.DateInput(attrs={'type': 'date'}),
            'date_fin': forms.DateInput(attrs={'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        immeuble = kwargs.pop('immeuble', None)
        super().__init__(*args, **kwargs)
        self.fields['cle_repartition'].required = False
        self.fields['cle_repartition'].empty_label = "-- Aucune --"
        self.fields['date_debut'].required = False
        self.fields['date_fin'].required = False
        if immeuble:
            self.fields['cle_repartition'].queryset = CleRepartition.objects.filter(immeuble=immeuble)


# ─── CleRepartition ─────────────────────────────────────────────────────────

@_apply_css
class CleRepartitionForm(forms.ModelForm):
    class Meta:
        model = CleRepartition
        fields = ['immeuble', 'nom', 'mode_repartition', 'prix_unitaire']
        widgets = {
            'prix_unitaire': forms.NumberInput(attrs={'step': '0.0001'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['prix_unitaire'].required = False


# ─── QuotePart ───────────────────────────────────────────────────────────────

@_apply_css
class QuotePartForm(forms.ModelForm):
    class Meta:
        model = QuotePart
        fields = ['cle', 'local', 'valeur']
        widgets = {
            'valeur': forms.NumberInput(attrs={'step': '0.01'}),
        }

    def __init__(self, *args, **kwargs):
        cle = kwargs.pop('cle', None)
        super().__init__(*args, **kwargs)
        if cle:
            self.fields['local'].queryset = Local.objects.filter(immeuble=cle.immeuble)


# ─── Consommation ────────────────────────────────────────────────────────────

@_apply_css
class ConsommationForm(forms.ModelForm):
    class Meta:
        model = Consommation
        fields = ['local', 'cle_repartition', 'date_debut', 'date_releve', 'index_debut', 'index_fin']
        widgets = {
            'date_debut': forms.DateInput(attrs={'type': 'date'}),
            'date_releve': forms.DateInput(attrs={'type': 'date'}),
            'index_debut': forms.NumberInput(attrs={'step': '0.01'}),
            'index_fin': forms.NumberInput(attrs={'step': '0.01'}),
        }

    def __init__(self, *args, **kwargs):
        immeuble = kwargs.pop('immeuble', None)
        super().__init__(*args, **kwargs)
        self.fields['date_debut'].required = False
        if immeuble:
            self.fields['local'].queryset = Local.objects.filter(immeuble=immeuble)
            self.fields['cle_repartition'].queryset = CleRepartition.objects.filter(
                immeuble=immeuble, mode_repartition='CONSOMMATION',
            )


# ─── Regularisation ──────────────────────────────────────────────────────────

@_apply_css
class RegularisationForm(forms.ModelForm):
    class Meta:
        model = Regularisation
        fields = [
            'bail', 'date_debut', 'date_fin', 'montant_reel',
            'montant_provisions', 'solde', 'payee', 'date_paiement', 'notes',
        ]
        widgets = {
            'date_debut': forms.DateInput(attrs={'type': 'date'}),
            'date_fin': forms.DateInput(attrs={'type': 'date'}),
            'montant_reel': forms.NumberInput(attrs={'step': '0.01'}),
            'montant_provisions': forms.NumberInput(attrs={'step': '0.01'}),
            'solde': forms.NumberInput(attrs={'step': '0.01'}),
            'date_paiement': forms.DateInput(attrs={'type': 'date'}),
            'notes': forms.Textarea(attrs={'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['date_paiement'].required = False
        self.fields['notes'].required = False


# ─── Ajustement ──────────────────────────────────────────────────────────────

@_apply_css
class AjustementForm(forms.ModelForm):
    class Meta:
        model = Ajustement
        fields = ['bail', 'date', 'libelle', 'montant']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),
            'montant': forms.NumberInput(attrs={'step': '0.01'}),
        }
