"""
Calculateurs pour la gestion de patrimoine immobilier.

Ce module contient les classes de calcul pour:
- PatrimoineCalculator: Valeur brute/nette, capital restant dû
- RentabiliteCalculator: Rendements brut/net, cash-flow
- FiscaliteCalculator: Bilan fiscal annuel
- RatiosCalculator: Taux d'endettement, taux de vacance
- CreditGenerator: Génération d'échéanciers de crédit
"""

from decimal import Decimal
from datetime import date
from dateutil.relativedelta import relativedelta
from django.db.models import Sum, Q
from django.utils import timezone


class CreditGenerator:
    """Générateur d'échéancier pour les crédits immobiliers."""

    def __init__(self, credit):
        self.credit = credit

    def generer_echeancier(self):
        """
        Calcule l'échéancier complet du crédit.
        Retourne une liste de dictionnaires représentant chaque échéance.
        """
        echeancier = []
        capital = float(self.credit.capital_emprunte)
        taux_mensuel = float(self.credit.taux_interet) / 100 / 12
        assurance = float(self.credit.assurance_mensuelle)
        date_echeance = self.credit.date_debut

        if self.credit.type_credit == 'IN_FINE':
            # Crédit in fine : intérêts mensuels, capital à la fin
            interets_mensuels = capital * taux_mensuel
            for i in range(1, self.credit.duree_mois + 1):
                date_echeance = self.credit.date_debut + relativedelta(months=i)
                capital_rembourse = capital if i == self.credit.duree_mois else 0
                capital_restant = capital if i < self.credit.duree_mois else 0

                echeancier.append({
                    'numero_echeance': i,
                    'date_echeance': date_echeance,
                    'capital_rembourse': round(capital_rembourse, 2),
                    'interets': round(interets_mensuels, 2),
                    'assurance': round(assurance, 2),
                    'capital_restant_du': round(capital_restant, 2),
                })
        else:
            # Crédit amortissable classique
            mensualite_hors_assurance = self.credit.mensualite_hors_assurance
            capital_restant = capital

            for i in range(1, self.credit.duree_mois + 1):
                date_echeance = self.credit.date_debut + relativedelta(months=i)
                interets = capital_restant * taux_mensuel
                capital_rembourse = mensualite_hors_assurance - interets
                capital_restant = max(0, capital_restant - capital_rembourse)

                # Ajustement dernière échéance
                if i == self.credit.duree_mois:
                    capital_rembourse += capital_restant
                    capital_restant = 0

                echeancier.append({
                    'numero_echeance': i,
                    'date_echeance': date_echeance,
                    'capital_rembourse': round(capital_rembourse, 2),
                    'interets': round(interets, 2),
                    'assurance': round(assurance, 2),
                    'capital_restant_du': round(capital_restant, 2),
                })

        return echeancier

    def creer_echeances_en_base(self):
        """
        Génère et sauvegarde l'échéancier complet en base de données.
        Supprime l'ancien échéancier s'il existe.
        """
        from .models import EcheanceCredit

        # Supprimer les échéances existantes
        self.credit.echeances.all().delete()

        # Générer le nouvel échéancier
        echeancier = self.generer_echeancier()

        # Créer les objets en bulk
        echeances = [
            EcheanceCredit(
                credit=self.credit,
                numero_echeance=e['numero_echeance'],
                date_echeance=e['date_echeance'],
                capital_rembourse=e['capital_rembourse'],
                interets=e['interets'],
                assurance=e['assurance'],
                capital_restant_du=e['capital_restant_du'],
            )
            for e in echeancier
        ]

        EcheanceCredit.objects.bulk_create(echeances)
        return len(echeances)


class PatrimoineCalculator:
    """Calculs liés à la valeur du patrimoine immobilier."""

    @staticmethod
    def get_valeur_actuelle(immeuble):
        """
        Retourne la valeur actuelle de l'immeuble.
        Utilise la dernière estimation ou le prix d'achat par défaut.
        """
        derniere_estimation = immeuble.estimations.order_by('-date_estimation').first()
        if derniere_estimation:
            return float(derniere_estimation.valeur_estimee)
        return float(immeuble.prix_achat) if immeuble.prix_achat else 0

    @staticmethod
    def get_capital_restant_du(immeuble, target_date=None):
        """
        Calcule le capital restant dû total de tous les crédits de l'immeuble.
        """
        if target_date is None:
            target_date = timezone.now().date()

        total_crd = 0
        for credit in immeuble.credits.all():
            total_crd += credit.get_capital_restant_du_at(target_date)
        return total_crd

    @staticmethod
    def get_valeur_nette(immeuble, target_date=None):
        """
        Calcule la valeur nette (valeur actuelle - capital restant dû).
        """
        valeur = PatrimoineCalculator.get_valeur_actuelle(immeuble)
        crd = PatrimoineCalculator.get_capital_restant_du(immeuble, target_date)
        return valeur - crd

    @staticmethod
    def get_plus_value_latente(immeuble):
        """
        Calcule la plus-value latente (valeur actuelle - coût d'acquisition).
        """
        valeur = PatrimoineCalculator.get_valeur_actuelle(immeuble)
        cout = float(immeuble.cout_total_acquisition) if immeuble.prix_achat else 0
        return valeur - cout

    @staticmethod
    def get_synthese_patrimoine(proprietaire):
        """
        Retourne une synthèse du patrimoine d'un propriétaire.
        """
        from .models import Immeuble

        immeubles = Immeuble.objects.filter(proprietaire=proprietaire)
        total_valeur = 0
        total_crd = 0
        total_acquisition = 0

        details = []
        for immeuble in immeubles:
            valeur = PatrimoineCalculator.get_valeur_actuelle(immeuble)
            crd = PatrimoineCalculator.get_capital_restant_du(immeuble)
            acquisition = float(immeuble.cout_total_acquisition) if immeuble.prix_achat else 0

            total_valeur += valeur
            total_crd += crd
            total_acquisition += acquisition

            details.append({
                'immeuble': immeuble,
                'valeur_actuelle': valeur,
                'capital_restant_du': crd,
                'valeur_nette': valeur - crd,
                'cout_acquisition': acquisition,
                'plus_value_latente': valeur - acquisition,
            })

        return {
            'total_valeur': total_valeur,
            'total_crd': total_crd,
            'total_valeur_nette': total_valeur - total_crd,
            'total_acquisition': total_acquisition,
            'plus_value_latente': total_valeur - total_acquisition,
            'details': details,
        }


class RentabiliteCalculator:
    """Calculs de rentabilité immobilière."""

    @staticmethod
    def get_loyers_annuels(immeuble, annee):
        """
        Calcule les loyers bruts perçus sur une année.
        Basé sur les baux actifs de l'immeuble.
        """
        from .models import Bail

        total_loyers = 0
        date_debut_annee = date(annee, 1, 1)
        date_fin_annee = date(annee, 12, 31)

        # Récupérer tous les baux actifs pendant l'année
        for local in immeuble.locaux.all():
            for bail in local.baux.filter(
                Q(date_debut__lte=date_fin_annee) &
                (Q(date_fin__isnull=True) | Q(date_fin__gte=date_debut_annee))
            ):
                # Calculer le nombre de mois actifs
                debut_effectif = max(bail.date_debut, date_debut_annee)
                fin_effective = bail.date_fin if bail.date_fin and bail.date_fin <= date_fin_annee else date_fin_annee

                # Nombre de mois (approximatif)
                mois_actifs = (fin_effective.year - debut_effectif.year) * 12 + (fin_effective.month - debut_effectif.month) + 1
                mois_actifs = min(mois_actifs, 12)

                # Récupérer les tarifications pour chaque mois
                for mois in range(1, mois_actifs + 1):
                    date_mois = date(annee, min(mois + debut_effectif.month - 1, 12), 1)
                    if date_mois.month > 12:
                        continue
                    tarif = bail.get_tarification_at(date_mois)
                    if tarif:
                        total_loyers += float(tarif.loyer_hc)

        return total_loyers

    @staticmethod
    def get_rendement_brut(immeuble, annee=None):
        """
        Calcule le rendement brut : Loyers annuels / Prix d'achat × 100
        """
        if not immeuble.prix_achat:
            return None

        if annee is None:
            annee = timezone.now().year

        loyers = RentabiliteCalculator.get_loyers_annuels(immeuble, annee)
        prix = float(immeuble.cout_total_acquisition)

        if prix == 0:
            return None

        return (loyers / prix) * 100

    @staticmethod
    def get_charges_annuelles(immeuble, annee):
        """
        Total des charges fiscales pour une année.
        """
        return float(immeuble.charges_fiscales.filter(annee=annee).aggregate(
            total=Sum('montant'))['total'] or 0)

    @staticmethod
    def get_interets_annuels(immeuble, annee):
        """
        Total des intérêts payés sur une année pour tous les crédits.
        """
        total_interets = 0
        date_debut = date(annee, 1, 1)
        date_fin = date(annee, 12, 31)

        for credit in immeuble.credits.all():
            interets = credit.echeances.filter(
                date_echeance__gte=date_debut,
                date_echeance__lte=date_fin
            ).aggregate(total=Sum('interets'))['total'] or 0
            total_interets += float(interets)

        return total_interets

    @staticmethod
    def get_rendement_net(immeuble, annee=None):
        """
        Calcule le rendement net :
        (Loyers - Charges - Intérêts) / Prix d'achat × 100
        """
        if not immeuble.prix_achat:
            return None

        if annee is None:
            annee = timezone.now().year

        loyers = RentabiliteCalculator.get_loyers_annuels(immeuble, annee)
        charges = RentabiliteCalculator.get_charges_annuelles(immeuble, annee)
        interets = RentabiliteCalculator.get_interets_annuels(immeuble, annee)
        prix = float(immeuble.cout_total_acquisition)

        if prix == 0:
            return None

        return ((loyers - charges - interets) / prix) * 100

    @staticmethod
    def get_cashflow_mensuel(immeuble):
        """
        Calcule le cash-flow mensuel : Loyers mensuels - Mensualités crédits
        """
        # Loyers mensuels actuels
        total_loyers = 0
        for local in immeuble.locaux.all():
            bail_actif = local.baux.filter(actif=True, date_fin__isnull=True).first()
            if bail_actif:
                total_loyers += float(bail_actif.loyer_hc)

        # Mensualités des crédits
        total_mensualites = sum(credit.mensualite for credit in immeuble.credits.all())

        return total_loyers - total_mensualites

    @staticmethod
    def get_synthese_rentabilite(immeuble, annee=None):
        """
        Synthèse complète de la rentabilité d'un immeuble.
        """
        if annee is None:
            annee = timezone.now().year

        return {
            'annee': annee,
            'loyers_annuels': RentabiliteCalculator.get_loyers_annuels(immeuble, annee),
            'charges_annuelles': RentabiliteCalculator.get_charges_annuelles(immeuble, annee),
            'interets_annuels': RentabiliteCalculator.get_interets_annuels(immeuble, annee),
            'rendement_brut': RentabiliteCalculator.get_rendement_brut(immeuble, annee),
            'rendement_net': RentabiliteCalculator.get_rendement_net(immeuble, annee),
            'cashflow_mensuel': RentabiliteCalculator.get_cashflow_mensuel(immeuble),
        }


class FiscaliteCalculator:
    """Calculs pour la déclaration fiscale."""

    @staticmethod
    def generer_bilan_fiscal(immeuble, annee):
        """
        Génère un bilan fiscal annuel pour un immeuble.
        Format adapté à la déclaration 2044 (revenus fonciers).
        """
        # Revenus bruts
        loyers_bruts = RentabiliteCalculator.get_loyers_annuels(immeuble, annee)

        # Charges par type
        charges = immeuble.charges_fiscales.filter(annee=annee)
        charges_par_type = {}
        for charge in charges:
            type_charge = charge.get_type_charge_display()
            if type_charge not in charges_par_type:
                charges_par_type[type_charge] = 0
            charges_par_type[type_charge] += float(charge.montant)

        total_charges = sum(charges_par_type.values())

        # Intérêts d'emprunt (calculés depuis les échéanciers)
        interets_emprunts = RentabiliteCalculator.get_interets_annuels(immeuble, annee)

        # Assurance emprunt
        assurance_emprunt = 0
        date_debut = date(annee, 1, 1)
        date_fin = date(annee, 12, 31)
        for credit in immeuble.credits.all():
            assurance = credit.echeances.filter(
                date_echeance__gte=date_debut,
                date_echeance__lte=date_fin
            ).aggregate(total=Sum('assurance'))['total'] or 0
            assurance_emprunt += float(assurance)

        # Résultat foncier
        resultat_foncier = loyers_bruts - total_charges - interets_emprunts - assurance_emprunt

        return {
            'immeuble': immeuble,
            'annee': annee,
            'regime_fiscal': immeuble.get_regime_fiscal_display(),
            'revenus': {
                'loyers_bruts': loyers_bruts,
            },
            'charges': {
                'detail': charges_par_type,
                'total_charges_deductibles': total_charges,
                'interets_emprunts': interets_emprunts,
                'assurance_emprunt': assurance_emprunt,
            },
            'resultat': {
                'total_charges': total_charges + interets_emprunts + assurance_emprunt,
                'resultat_foncier': resultat_foncier,
                'deficit_reportable': min(0, resultat_foncier),
            },
        }

    @staticmethod
    def generer_bilan_global(proprietaire, annee):
        """
        Génère un bilan fiscal global pour tous les immeubles d'un propriétaire.
        """
        from .models import Immeuble

        immeubles = Immeuble.objects.filter(proprietaire=proprietaire)
        bilans = []
        total_revenus = 0
        total_charges = 0
        total_resultat = 0

        for immeuble in immeubles:
            bilan = FiscaliteCalculator.generer_bilan_fiscal(immeuble, annee)
            bilans.append(bilan)
            total_revenus += bilan['revenus']['loyers_bruts']
            total_charges += bilan['resultat']['total_charges']
            total_resultat += bilan['resultat']['resultat_foncier']

        return {
            'annee': annee,
            'proprietaire': proprietaire,
            'bilans_immeubles': bilans,
            'totaux': {
                'revenus_bruts': total_revenus,
                'charges_deductibles': total_charges,
                'resultat_foncier': total_resultat,
            },
        }


class RatiosCalculator:
    """Calculs de ratios et indicateurs."""

    @staticmethod
    def get_taux_endettement(proprietaire):
        """
        Calcule le taux d'endettement : Mensualités / Loyers × 100
        """
        from .models import Immeuble

        total_mensualites = 0
        total_loyers = 0

        for immeuble in Immeuble.objects.filter(proprietaire=proprietaire):
            for credit in immeuble.credits.all():
                total_mensualites += credit.mensualite

            for local in immeuble.locaux.all():
                bail_actif = local.baux.filter(actif=True, date_fin__isnull=True).first()
                if bail_actif:
                    total_loyers += float(bail_actif.loyer_hc)

        if total_loyers == 0:
            return None

        return (total_mensualites / total_loyers) * 100

    @staticmethod
    def get_taux_vacance(immeuble, annee):
        """
        Calcule le taux de vacance : Jours vacants / 365 × 100
        """
        from .models import VacanceLocative

        date_debut_annee = date(annee, 1, 1)
        date_fin_annee = date(annee, 12, 31)
        total_jours_vacants = 0
        total_locaux = immeuble.locaux.count()

        if total_locaux == 0:
            return 0

        for local in immeuble.locaux.all():
            vacances = VacanceLocative.objects.filter(
                local=local,
                date_debut__lte=date_fin_annee
            ).filter(
                Q(date_fin__isnull=True) | Q(date_fin__gte=date_debut_annee)
            )

            for vacance in vacances:
                debut = max(vacance.date_debut, date_debut_annee)
                fin = min(vacance.date_fin or date_fin_annee, date_fin_annee)
                jours = (fin - debut).days + 1
                total_jours_vacants += jours

        # Moyenne par local
        jours_vacants_moyen = total_jours_vacants / total_locaux
        return (jours_vacants_moyen / 365) * 100

    @staticmethod
    def get_taux_occupation(immeuble, annee):
        """
        Calcule le taux d'occupation (100 - taux de vacance).
        """
        return 100 - RatiosCalculator.get_taux_vacance(immeuble, annee)

    @staticmethod
    def get_synthese_ratios(proprietaire, annee=None):
        """
        Synthèse des ratios pour un propriétaire.
        """
        from .models import Immeuble

        if annee is None:
            annee = timezone.now().year

        immeubles = Immeuble.objects.filter(proprietaire=proprietaire)
        ratios_par_immeuble = []

        for immeuble in immeubles:
            ratios_par_immeuble.append({
                'immeuble': immeuble,
                'taux_vacance': RatiosCalculator.get_taux_vacance(immeuble, annee),
                'taux_occupation': RatiosCalculator.get_taux_occupation(immeuble, annee),
                'cashflow': RentabiliteCalculator.get_cashflow_mensuel(immeuble),
            })

        return {
            'annee': annee,
            'taux_endettement': RatiosCalculator.get_taux_endettement(proprietaire),
            'details': ratios_par_immeuble,
        }
