"""
Calculateurs pour la gestion de patrimoine immobilier.

Ce module contient les classes de calcul pour:
- PatrimoineCalculator: Valeur brute/nette, capital restant dû
- RentabiliteCalculator: Rendements brut/net, cash-flow
- FiscaliteCalculator: Bilan fiscal annuel
- RatiosCalculator: Taux d'endettement, taux de vacance
- CreditGenerator: Génération d'échéanciers de crédit
"""

import calendar
from decimal import Decimal, ROUND_HALF_UP
from datetime import date
from dateutil.relativedelta import relativedelta
from django.db import transaction
from django.db.models import Sum, Q
from django.utils import timezone


class CreditGenerator:
    """Générateur d'échéancier pour les crédits immobiliers."""

    def __init__(self, credit):
        self.credit = credit

    def generer_echeancier(self):
        """
        Calcule l'échéancier complet du crédit.
        Utilise Decimal pour éviter les erreurs d'arrondi sur 20+ ans.
        Retourne une liste de dictionnaires représentant chaque échéance.
        """
        TWO_PLACES = Decimal('0.01')
        echeancier = []
        capital = Decimal(str(self.credit.capital_emprunte))
        taux_mensuel = Decimal(str(self.credit.taux_interet)) / 100 / 12
        assurance = Decimal(str(self.credit.assurance_mensuelle))

        if self.credit.type_credit == 'IN_FINE':
            # Crédit in fine : intérêts mensuels, capital à la fin
            interets_mensuels = (capital * taux_mensuel).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
            for i in range(1, self.credit.duree_mois + 1):
                date_echeance = self.credit.date_debut + relativedelta(months=i)
                capital_rembourse = capital if i == self.credit.duree_mois else Decimal('0')
                capital_restant = capital if i < self.credit.duree_mois else Decimal('0')

                echeancier.append({
                    'numero_echeance': i,
                    'date_echeance': date_echeance,
                    'capital_rembourse': capital_rembourse.quantize(TWO_PLACES),
                    'interets': interets_mensuels,
                    'assurance': assurance.quantize(TWO_PLACES),
                    'capital_restant_du': capital_restant.quantize(TWO_PLACES),
                })
        else:
            # Crédit amortissable classique
            n = self.credit.duree_mois
            if taux_mensuel == 0:
                mensualite = capital / n
            else:
                mensualite = capital * (taux_mensuel * (1 + taux_mensuel) ** n) / ((1 + taux_mensuel) ** n - 1)
            mensualite = mensualite.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
            capital_restant = capital

            for i in range(1, self.credit.duree_mois + 1):
                date_echeance = self.credit.date_debut + relativedelta(months=i)
                interets = (capital_restant * taux_mensuel).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
                capital_rembourse = mensualite - interets
                capital_restant = max(Decimal('0'), capital_restant - capital_rembourse)

                # Ajustement dernière échéance
                if i == self.credit.duree_mois:
                    capital_rembourse += capital_restant
                    capital_restant = Decimal('0')

                echeancier.append({
                    'numero_echeance': i,
                    'date_echeance': date_echeance,
                    'capital_rembourse': capital_rembourse.quantize(TWO_PLACES),
                    'interets': interets,
                    'assurance': assurance.quantize(TWO_PLACES),
                    'capital_restant_du': capital_restant.quantize(TWO_PLACES),
                })

        return echeancier

    @transaction.atomic
    def creer_echeances_en_base(self):
        """
        Génère et sauvegarde l'échéancier complet en base de données.
        Supprime l'ancien échéancier s'il existe.
        Opération atomique : si bulk_create échoue, la suppression est annulée.
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
            return derniere_estimation.valeur_estimee
        return immeuble.prix_achat or Decimal('0')

    @staticmethod
    def get_capital_restant_du(immeuble, target_date=None):
        """
        Calcule le capital restant dû total de tous les crédits de l'immeuble.
        """
        if target_date is None:
            target_date = timezone.now().date()

        total_crd = Decimal('0')
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
        cout = immeuble.cout_total_acquisition if immeuble.prix_achat else Decimal('0')
        return valeur - cout

    @staticmethod
    def get_synthese_patrimoine(proprietaire):
        """
        Retourne une synthèse du patrimoine d'un propriétaire.
        """
        from .models import Immeuble

        immeubles = Immeuble.objects.filter(proprietaire=proprietaire)
        total_valeur = Decimal('0')
        total_crd = Decimal('0')
        total_acquisition = Decimal('0')

        details = []
        for immeuble in immeubles:
            valeur = PatrimoineCalculator.get_valeur_actuelle(immeuble)
            crd = PatrimoineCalculator.get_capital_restant_du(immeuble)
            acquisition = immeuble.cout_total_acquisition if immeuble.prix_achat else Decimal('0')

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
    def _loyer_mensuel_equivalent(bail, tarif):
        """Loyer ramené au mois, quelle que soit la fréquence de paiement."""
        if bail.frequence_paiement == 'TRIMESTRIEL':
            return tarif.loyer_hc / 3
        return tarif.loyer_hc

    @staticmethod
    def get_loyers_annuels(immeuble, annee):
        """
        Calcule les loyers théoriques sur une année, au prorata des jours occupés.

        ATTENTION : il s'agit des loyers dus d'après les tarifications, pas des
        loyers encaissés. Les impayés ne sont pas déduits (l'application ne suit
        pas les encaissements).
        """
        import calendar

        total_loyers = Decimal('0')
        date_debut_annee = date(annee, 1, 1)
        date_fin_annee = date(annee, 12, 31)

        for local in immeuble.locaux.all():
            # Filtrage en Python : un .filter() ici annulerait le prefetch_related
            # des vues et relancerait une requete par local.
            baux_de_lannee = [
                bail for bail in local.baux.all()
                if bail.date_debut <= date_fin_annee
                and (bail.date_fin is None or bail.date_fin >= date_debut_annee)
            ]
            for bail in baux_de_lannee:
                debut_effectif = max(bail.date_debut, date_debut_annee)
                fin_effective = min(bail.date_fin, date_fin_annee) if bail.date_fin else date_fin_annee

                if debut_effectif > fin_effective:
                    continue

                for mois in range(1, 13):
                    nb_jours_mois = calendar.monthrange(annee, mois)[1]
                    debut_mois = date(annee, mois, 1)
                    fin_mois = date(annee, mois, nb_jours_mois)

                    p_start = max(debut_mois, debut_effectif)
                    p_end = min(fin_mois, fin_effective)
                    if p_start > p_end:
                        continue

                    for tarif in bail.get_tarifications_for_period(p_start, p_end):
                        seg_start = max(p_start, tarif.date_debut)
                        seg_end = min(p_end, tarif.date_fin) if tarif.date_fin else p_end
                        if seg_start > seg_end:
                            continue

                        nb_jours = (seg_end - seg_start).days + 1
                        loyer_mensuel = RentabiliteCalculator._loyer_mensuel_equivalent(bail, tarif)

                        if nb_jours == nb_jours_mois:
                            total_loyers += loyer_mensuel
                        else:
                            total_loyers += (
                                loyer_mensuel * Decimal(nb_jours) / Decimal(nb_jours_mois)
                            )

        return total_loyers.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    @staticmethod
    def get_rendement_brut(immeuble, annee=None):
        """
        Calcule le rendement brut : Loyers annuels / Coût d'acquisition × 100
        """
        if not immeuble.prix_achat:
            return None

        if annee is None:
            annee = timezone.now().year

        loyers = RentabiliteCalculator.get_loyers_annuels(immeuble, annee)
        prix = immeuble.cout_total_acquisition

        if prix == 0:
            return None

        return float(loyers / prix * 100)

    @staticmethod
    def get_charges_annuelles(immeuble, annee, exclure_types=None):
        """
        Total des charges fiscales saisies pour une année.

        exclure_types permet d'écarter les types déjà calculés depuis l'échéancier
        de crédit, pour ne pas les compter deux fois.
        """
        charges = immeuble.charges_fiscales.filter(annee=annee)
        if exclure_types:
            charges = charges.exclude(type_charge__in=exclure_types)
        return charges.aggregate(total=Sum('montant'))['total'] or Decimal('0')

    @staticmethod
    def get_interets_annuels(immeuble, annee):
        """
        Total des intérêts payés sur une année pour tous les crédits (échéanciers).
        """
        total_interets = Decimal('0')
        date_debut = date(annee, 1, 1)
        date_fin = date(annee, 12, 31)

        for credit in immeuble.credits.all():
            interets = credit.echeances.filter(
                date_echeance__gte=date_debut,
                date_echeance__lte=date_fin
            ).aggregate(total=Sum('interets'))['total'] or Decimal('0')
            total_interets += interets

        return total_interets

    @staticmethod
    def get_assurance_emprunt_annuelle(immeuble, annee):
        """Total des primes d'assurance emprunteur d'une année (échéanciers)."""
        total = Decimal('0')
        date_debut = date(annee, 1, 1)
        date_fin = date(annee, 12, 31)

        for credit in immeuble.credits.all():
            assurance = credit.echeances.filter(
                date_echeance__gte=date_debut,
                date_echeance__lte=date_fin
            ).aggregate(total=Sum('assurance'))['total'] or Decimal('0')
            total += assurance

        return total

    @staticmethod
    def get_rendement_net(immeuble, annee=None):
        """
        Calcule le rendement net :
        (Loyers - Charges - Intérêts) / Coût d'acquisition × 100
        """
        if not immeuble.prix_achat:
            return None

        if annee is None:
            annee = timezone.now().year

        bilan = FiscaliteCalculator.generer_bilan_fiscal(immeuble, annee)
        prix = immeuble.cout_total_acquisition

        if prix == 0:
            return None

        resultat = bilan['resultat']['resultat_foncier']
        return float(resultat / prix * 100)

    @staticmethod
    def get_cashflow_mensuel(immeuble):
        """
        Calcule le cash-flow mensuel : Loyers mensuels - Mensualités crédits
        """
        total_loyers = Decimal('0')
        for local in immeuble.locaux.all():
            bail_actif = next(
                (b for b in local.baux.all() if b.actif and b.date_fin is None), None
            )
            if bail_actif:
                tarif = bail_actif.tarification_actuelle
                if tarif:
                    total_loyers += RentabiliteCalculator._loyer_mensuel_equivalent(bail_actif, tarif)

        total_mensualites = sum(
            (credit.mensualite for credit in immeuble.credits.all()), Decimal('0')
        )

        return (total_loyers - total_mensualites).quantize(
            Decimal('0.01'), rounding=ROUND_HALF_UP
        )

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

    # Types de charges déjà couverts par l'échéancier de crédit : les compter en
    # plus des montants calculés reviendrait à les déduire deux fois.
    TYPES_COUVERTS_PAR_ECHEANCIER = ('INTERETS', 'ASSURANCE_EMPRUNT')

    @staticmethod
    def generer_bilan_fiscal(immeuble, annee):
        """
        Génère un bilan fiscal annuel pour un immeuble.
        Format adapté à la déclaration 2044 (revenus fonciers).

        Les intérêts et l'assurance emprunteur sont pris depuis l'échéancier des
        crédits quand il existe ; à défaut seulement, depuis les charges saisies
        à la main.
        """
        loyers_bruts = RentabiliteCalculator.get_loyers_annuels(immeuble, annee)

        interets_echeancier = RentabiliteCalculator.get_interets_annuels(immeuble, annee)
        assurance_echeancier = RentabiliteCalculator.get_assurance_emprunt_annuelle(immeuble, annee)

        charges_saisies = immeuble.charges_fiscales.filter(annee=annee)

        # Repli : sans échéancier, on retient ce qui a été saisi manuellement.
        interets_saisis = charges_saisies.filter(type_charge='INTERETS').aggregate(
            total=Sum('montant'))['total'] or Decimal('0')
        assurance_saisie = charges_saisies.filter(type_charge='ASSURANCE_EMPRUNT').aggregate(
            total=Sum('montant'))['total'] or Decimal('0')

        interets_emprunts = interets_echeancier or interets_saisis
        assurance_emprunt = assurance_echeancier or assurance_saisie
        source_interets = 'echeancier' if interets_echeancier else 'saisie_manuelle'

        # Les autres charges, ventilées par type
        charges_par_type = {}
        for charge in charges_saisies.exclude(
            type_charge__in=FiscaliteCalculator.TYPES_COUVERTS_PAR_ECHEANCIER
        ):
            libelle = charge.get_type_charge_display()
            charges_par_type[libelle] = charges_par_type.get(libelle, Decimal('0')) + charge.montant

        total_charges = sum(charges_par_type.values(), Decimal('0'))

        resultat_foncier = loyers_bruts - total_charges - interets_emprunts - assurance_emprunt

        return {
            'immeuble': immeuble,
            'annee': annee,
            'regime_fiscal': immeuble.get_regime_fiscal_display(),
            'revenus': {
                'loyers_bruts': loyers_bruts,
                'loyers_theoriques': True,
            },
            'charges': {
                'detail': charges_par_type,
                'total_charges_deductibles': total_charges,
                'interets_emprunts': interets_emprunts,
                'assurance_emprunt': assurance_emprunt,
                'source_interets': source_interets,
            },
            'resultat': {
                'total_charges': total_charges + interets_emprunts + assurance_emprunt,
                'resultat_foncier': resultat_foncier,
                'deficit_reportable': min(Decimal('0'), resultat_foncier),
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
        total_revenus = Decimal('0')
        total_charges = Decimal('0')
        total_resultat = Decimal('0')

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

        total_mensualites = Decimal('0')
        total_loyers = Decimal('0')

        for immeuble in Immeuble.objects.filter(proprietaire=proprietaire):
            for credit in immeuble.credits.all():
                total_mensualites += credit.mensualite

            for local in immeuble.locaux.all():
                bail_actif = next(
                    (b for b in local.baux.all() if b.actif and b.date_fin is None), None
                )
                if bail_actif:
                    tarif = bail_actif.tarification_actuelle
                    if tarif:
                        total_loyers += RentabiliteCalculator._loyer_mensuel_equivalent(
                            bail_actif, tarif
                        )

        if total_loyers == 0:
            return None

        return float(total_mensualites / total_loyers * 100)

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

        # Moyenne par local, sur la durée réelle de l'année (bissextile comprise)
        jours_annee = 366 if calendar.isleap(annee) else 365
        jours_vacants_moyen = total_jours_vacants / total_locaux
        return (jours_vacants_moyen / jours_annee) * 100

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
