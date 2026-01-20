"""
Calculateurs pour les opérations complexes de gestion locative.
"""
import calendar
from datetime import date, timedelta
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)


class BailCalculator:
    """Classe utilitaire pour les calculs liés aux baux."""

    @staticmethod
    def calculer_provisions_mensuelles(bail, date_debut, date_fin):
        """
        Calcule les provisions de charges mois par mois avec tarifs historiques.

        Args:
            bail: Instance de Bail
            date_debut: Date de début de la période
            date_fin: Date de fin de la période

        Returns:
            tuple: (total_provisions, details_list)
                - total_provisions (float): Montant total des provisions
                - details_list (list): Liste des calculs détaillés par mois
        """
        from .exceptions import TarificationNotFoundError

        total_provisions = 0.0
        details = []

        logger.info(f"Calcul provisions pour {bail} du {date_debut} au {date_fin}")

        # Intersection avec les dates du bail
        start_date = max(date_debut, bail.date_debut)
        end_date = date_fin if not bail.date_fin else min(date_fin, bail.date_fin)

        if start_date > end_date:
            logger.warning(f"Période invalide pour {bail}: start > end")
            return 0.0, ["Aucune période de présence"]

        # Parcourir mois par mois
        curr = date(start_date.year, start_date.month, 1)

        while curr <= end_date:
            # Fin du mois
            last_day = calendar.monthrange(curr.year, curr.month)[1]
            month_end = date(curr.year, curr.month, last_day)

            # Intersection avec occupation
            p_start = max(curr, start_date)
            p_end = min(month_end, end_date)

            if p_start <= p_end:
                # RÉCUPÉRER TARIF DU 1ER DU MOIS
                tarif_mois = bail.get_tarification_at(curr)

                if not tarif_mois:
                    raise TarificationNotFoundError(curr, bail)

                nb_jours_presence = (p_end - p_start).days + 1
                nb_jours_mois = last_day

                if nb_jours_presence == nb_jours_mois:
                    montant_mois = float(tarif_mois.charges)
                    detail = f"{curr.strftime('%m/%Y')} : Mois complet ({tarif_mois.charges}€) -> {montant_mois:.2f}€"
                else:
                    montant_mois = float(tarif_mois.charges) * (nb_jours_presence / nb_jours_mois)
                    detail = f"{curr.strftime('%m/%Y')} : Partiel {nb_jours_presence}/{nb_jours_mois}j ({tarif_mois.charges}€) -> {montant_mois:.2f}€"

                details.append(detail)
                total_provisions += montant_mois

                logger.debug(f"  {detail}")

            # Mois suivant
            next_month = curr.month + 1
            next_year = curr.year
            if next_month > 12:
                next_month = 1
                next_year += 1
            curr = date(next_year, next_month, 1)

        logger.info(f"Total provisions calculées: {total_provisions:.2f}€")
        return total_provisions, details

    @staticmethod
    def calculer_revision_irl(bail, nouvel_indice, ancien_indice=None):
        """
        Calcule le nouveau loyer après révision IRL/ILC.

        Args:
            bail: Instance de Bail
            nouvel_indice (Decimal): Nouvel indice IRL/ILC
            ancien_indice (Decimal, optional): Ancien indice. Si None, utilise tarification actuelle.

        Returns:
            dict: {
                'ancien_loyer': Decimal,
                'nouveau_loyer': Decimal,
                'variation_pct': float,
                'ancien_indice': Decimal,
                'nouvel_indice': Decimal
            }
        """
        tarif_actuel = bail.tarification_actuelle

        if not tarif_actuel:
            raise ValueError(f"Aucune tarification actuelle pour {bail}")

        ancien_loyer = tarif_actuel.loyer_hc

        if ancien_indice is None:
            ancien_indice = tarif_actuel.indice_reference

        if not ancien_indice:
            raise ValueError(f"Aucun indice de référence pour {bail}")

        # Calcul
        nouveau_loyer = Decimal(ancien_loyer) * (Decimal(nouvel_indice) / Decimal(ancien_indice))
        nouveau_loyer = nouveau_loyer.quantize(Decimal('0.01'))  # Arrondi à 2 décimales

        variation_pct = float((nouveau_loyer - ancien_loyer) / ancien_loyer * 100)

        logger.info(f"Révision IRL {bail}: {ancien_loyer}€ -> {nouveau_loyer}€ ({variation_pct:+.2f}%)")

        return {
            'ancien_loyer': ancien_loyer,
            'nouveau_loyer': nouveau_loyer,
            'variation_pct': variation_pct,
            'ancien_indice': ancien_indice,
            'nouvel_indice': nouvel_indice
        }

    @staticmethod
    def calculer_prorata_loyer(bail, date_debut, date_fin, tarif=None):
        """
        Calcule le loyer au prorata temporis pour une période donnée.

        Args:
            bail: Instance de Bail
            date_debut: Date de début
            date_fin: Date de fin
            tarif: Tarification à utiliser (si None, utilise tarif à date_debut)

        Returns:
            dict: {
                'montant_periode': Decimal,
                'nb_jours_periode': int,
                'nb_jours_presence': int,
                'loyer_prorata': Decimal
            }
        """
        from .exceptions import TarificationNotFoundError

        if tarif is None:
            tarif = bail.get_tarification_at(date_debut)

        if not tarif:
            raise TarificationNotFoundError(date_debut, bail)

        # Déterminer la période de facturation (mois ou trimestre)
        if bail.frequence_paiement == 'TRIMESTRIEL':
            # Début du trimestre
            mois_debut_trim = ((date_debut.month - 1) // 3) * 3 + 1
            debut_periode = date(date_debut.year, mois_debut_trim, 1)

            # Fin du trimestre
            m_fin = mois_debut_trim + 2
            y_fin = date_debut.year
            if m_fin > 12:
                m_fin -= 12
                y_fin += 1
            last_day = calendar.monthrange(y_fin, m_fin)[1]
            fin_periode = date(y_fin, m_fin, last_day)
        else:
            # Mensuel
            debut_periode = date(date_debut.year, date_debut.month, 1)
            last_day = calendar.monthrange(date_debut.year, date_debut.month)[1]
            fin_periode = date(date_debut.year, date_debut.month, last_day)

        nb_jours_periode = (fin_periode - debut_periode).days + 1
        nb_jours_presence = (date_fin - date_debut).days + 1

        montant_periode = tarif.loyer_hc
        loyer_prorata = Decimal(montant_periode) * Decimal(nb_jours_presence) / Decimal(nb_jours_periode)
        loyer_prorata = loyer_prorata.quantize(Decimal('0.01'))

        logger.debug(f"Prorata loyer {bail}: {nb_jours_presence}/{nb_jours_periode}j = {loyer_prorata}€")

        return {
            'montant_periode': montant_periode,
            'nb_jours_periode': nb_jours_periode,
            'nb_jours_presence': nb_jours_presence,
            'loyer_prorata': loyer_prorata
        }

    @staticmethod
    def verifier_continuite_tarifications(bail):
        """
        Vérifie qu'il n'y a pas de trous dans les tarifications d'un bail.

        Args:
            bail: Instance de Bail

        Returns:
            tuple: (is_continuous, gaps_list)
                - is_continuous (bool): True si continu
                - gaps_list (list): Liste des trous détectés
        """
        tarifs = bail.tarifications.order_by('date_debut')

        if not tarifs.exists():
            return False, ["Aucune tarification définie"]

        gaps = []

        for i in range(len(tarifs) - 1):
            tarif_current = tarifs[i]
            tarif_next = tarifs[i + 1]

            if tarif_current.date_fin:
                expected_next = tarif_current.date_fin + timedelta(days=1)
                if tarif_next.date_debut != expected_next:
                    gaps.append({
                        'end': tarif_current.date_fin,
                        'start': tarif_next.date_debut,
                        'days': (tarif_next.date_debut - tarif_current.date_fin).days - 1
                    })

        is_continuous = len(gaps) == 0

        if not is_continuous:
            logger.warning(f"Trous détectés dans tarifications de {bail}: {gaps}")

        return is_continuous, gaps
