from rest_framework import serializers
from .models import Immeuble, Local, Bail, Occupant, Regularisation, BailTarification

class OccupantSerializer(serializers.ModelSerializer):
    class Meta:
        model = Occupant
        fields = '__all__'

class RegularisationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Regularisation
        fields = ['id', 'bail', 'date_creation', 'date_debut', 'date_fin',
                  'montant_reel', 'montant_provisions', 'solde',
                  'payee', 'date_paiement', 'notes']
        read_only_fields = ['date_creation', 'date_debut', 'date_fin',
                           'montant_reel', 'montant_provisions', 'solde']

class BailTarificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = BailTarification
        fields = ['id', 'bail', 'date_debut', 'date_fin', 'loyer_hc', 'charges',
                  'taxes', 'indice_reference', 'trimestre_reference', 'reason',
                  'notes', 'created_at']
        read_only_fields = ['created_at']

class BailSerializer(serializers.ModelSerializer):
    occupants = OccupantSerializer(many=True, read_only=True)
    regularisations = RegularisationSerializer(many=True, read_only=True)
    tarifications = BailTarificationSerializer(many=True, read_only=True)
    tarification_actuelle = serializers.SerializerMethodField()

    class Meta:
        model = Bail
        fields = '__all__'

    def get_tarification_actuelle(self, obj):
        tarif = obj.tarification_actuelle
        if tarif:
            return BailTarificationSerializer(tarif).data
        return None

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