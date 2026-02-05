"""
Générateur PDF unifié pour tous les documents de gestion locative.
"""
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib import colors
from datetime import date, datetime
import calendar
import logging

logger = logging.getLogger(__name__)


def format_euro(montant):
    """Formate un montant en euros : 1 234,56 €"""
    try:
        return f"{montant:,.2f}".replace(",", " ").replace(".", ",") + " €"
    except (ValueError, TypeError):
        return "0,00 €"


class PDFGenerator:
    """
    Classe unifiée pour la génération de tous les PDFs de gestion locative.

    Mutualise les en-têtes, cadres bailleur/locataire, et fonctions communes.
    """

    def __init__(self, bail):
        """
        Initialise le générateur PDF pour un bail donné.

        Args:
            bail: Instance de Bail
        """
        self.bail = bail
        self.p = None
        self.response = None

    def _draw_header_standard(self, titre, sous_titre=""):
        """
        Dessine l'en-tête standardisé gris avec titre centré.

        Args:
            titre (str): Titre principal (ex: "QUITTANCE DE LOYER")
            sous_titre (str): Sous-titre optionnel (ex: "Période du ...")
        """
        # Fond gris clair
        self.p.setFillColor(colors.HexColor("#E0E0E0"))
        self.p.rect(1*cm, 26*cm, 19*cm, 2.5*cm, fill=1, stroke=0)
        self.p.setFillColor(colors.black)

        # Titre principal
        self.p.setFont("Helvetica-Bold", 16)
        self.p.drawCentredString(10.5*cm, 27.2*cm, titre)

        # Sous-titre
        if sous_titre:
            self.p.setFont("Helvetica", 11)
            self.p.drawCentredString(10.5*cm, 26.4*cm, sous_titre)

    def _draw_bailleur_locataire_boxes(self):
        """
        Dessine les cadres BAILLEUR (gauche) et LOCATAIRE (droite) standardisés.

        Utilise les données du bail (propriétaire et premier occupant).
        """
        # --- Cadre BAILLEUR (Gauche) ---
        self.p.setStrokeColor(colors.grey)
        self.p.rect(1*cm, 21.5*cm, 9*cm, 3.5*cm)  # Cadre

        # Titre cadre bailleur
        self.p.setFillColor(colors.HexColor("#F5F5F5"))
        self.p.rect(1*cm, 24.2*cm, 9*cm, 0.8*cm, fill=1, stroke=1)
        self.p.setFillColor(colors.black)
        self.p.setFont("Helvetica-Bold", 11)
        self.p.drawCentredString(5.5*cm, 24.4*cm, "BAILLEUR")

        # Contenu bailleur
        self.p.setFont("Helvetica", 10)
        y_text = 23.5*cm
        proprietaire = self.bail.local.immeuble.proprietaire

        if proprietaire:
            self.p.drawString(1.5*cm, y_text, proprietaire.nom)
            self.p.drawString(1.5*cm, y_text - 0.5*cm, proprietaire.adresse)
            self.p.drawString(1.5*cm, y_text - 1.0*cm, f"{proprietaire.code_postal} {proprietaire.ville}")
        else:
            self.p.drawString(1.5*cm, y_text, self.bail.local.immeuble.nom)
            self.p.drawString(1.5*cm, y_text - 0.5*cm, self.bail.local.immeuble.adresse)
            self.p.drawString(1.5*cm, y_text - 1.0*cm, f"{self.bail.local.immeuble.code_postal} {self.bail.local.immeuble.ville}")

        # --- Cadre LOCATAIRE (Droite) ---
        self.p.rect(11*cm, 21.5*cm, 9*cm, 3.5*cm)

        # Titre cadre locataire
        self.p.setFillColor(colors.HexColor("#F5F5F5"))
        self.p.rect(11*cm, 24.2*cm, 9*cm, 0.8*cm, fill=1, stroke=1)
        self.p.setFillColor(colors.black)
        self.p.setFont("Helvetica-Bold", 11)
        self.p.drawCentredString(15.5*cm, 24.4*cm, "LOCATAIRE")

        # Contenu locataire
        self.p.setFont("Helvetica", 10)
        y_text = 23.5*cm
        occupant = self.bail.occupants.filter(role='LOCATAIRE').first()

        if occupant:
            self.p.drawString(11.5*cm, y_text, f"{occupant.nom} {occupant.prenom}")
            self.p.drawString(11.5*cm, y_text - 0.5*cm, self.bail.local.immeuble.adresse)
            self.p.drawString(11.5*cm, y_text - 1.0*cm, f"{self.bail.local.immeuble.code_postal} {self.bail.local.immeuble.ville}")
            self.p.drawString(11.5*cm, y_text - 1.5*cm, f"Local: {self.bail.local.numero_porte}")
        else:
            self.p.drawString(11.5*cm, y_text, "Locataire")
            self.p.drawString(11.5*cm, y_text - 0.5*cm, self.bail.local.numero_porte)

    def _get_tarif_or_error(self, target_date):
        """
        Récupère la tarification pour une date donnée avec gestion d'erreur.

        Args:
            target_date (date): Date cible

        Returns:
            BailTarification: Tarification trouvée

        Raises:
            TarificationNotFoundError: Si aucune tarification trouvée
        """
        from .exceptions import TarificationNotFoundError

        tarif = self.bail.get_tarification_at(target_date)

        if not tarif:
            logger.error(f"Tarification introuvable pour {target_date} sur {self.bail}")
            raise TarificationNotFoundError(target_date, self.bail)

        return tarif

    def _draw_table_header(self, y, columns):
        """
        Dessine un en-tête de tableau standardisé.

        Args:
            y (float): Position Y
            columns (list): Liste de tuples (x, width, label)

        Returns:
            float: Nouvelle position Y après l'en-tête
        """
        # Fond gris pour en-tête
        self.p.setFillColor(colors.HexColor("#E0E0E0"))
        self.p.rect(2*cm, y - 0.2*cm, 17*cm, 0.8*cm, fill=1, stroke=1)
        self.p.setFillColor(colors.black)

        # Texte en-tête
        self.p.setFont("Helvetica-Bold", 9)
        for x, width, label in columns:
            self.p.drawString(x, y, label)

        return y - 1*cm

    def _format_date(self, dt):
        """Formate une date en français (JJ/MM/AAAA)."""
        if isinstance(dt, str):
            dt = datetime.strptime(dt, '%Y-%m-%d').date()
        return dt.strftime('%d/%m/%Y')

    def generer_quittance(self, periodes):
        """
        Génère une quittance de loyer pour une ou plusieurs périodes.

        Args:
            periodes (list): Liste de dates (date ou str 'YYYY-MM-DD')

        Returns:
            bytes: Contenu du PDF généré
        """
        from io import BytesIO

        logger.info(f"Génération quittance pour {self.bail}, {len(periodes)} période(s)")

        # Convertir dates si nécessaire
        sorted_dates = []
        for p in periodes:
            if isinstance(p, str):
                sorted_dates.append(datetime.strptime(p, '%Y-%m-%d').date())
            else:
                sorted_dates.append(p)
        sorted_dates.sort()

        # Fréquence de paiement
        is_trimestriel = (self.bail.frequence_paiement == 'TRIMESTRIEL')

        # Créer PDF en mémoire
        buffer = BytesIO()
        self.p = canvas.Canvas(buffer, pagesize=A4)

        # Boucle sur les périodes
        for current_date in sorted_dates:
            # Récupérer tarification pour cette période
            tarif = self._get_tarif_or_error(current_date)

            # Calcul de la période
            if is_trimestriel:
                mois_fin_p = current_date.month + 2
                annee_fin_p = current_date.year
                if mois_fin_p > 12:
                    mois_fin_p -= 12
                    annee_fin_p += 1
                last_day = calendar.monthrange(annee_fin_p, mois_fin_p)[1]
                periode_fin = date(annee_fin_p, mois_fin_p, last_day)
            else:
                last_day = calendar.monthrange(current_date.year, current_date.month)[1]
                periode_fin = current_date.replace(day=last_day)

            # EN-TÊTE
            sous_titre = f"Période du {self._format_date(current_date)} au {self._format_date(periode_fin)}"
            self._draw_header_standard("QUITTANCE DE LOYER", sous_titre)

            # CADRES BAILLEUR / LOCATAIRE
            self._draw_bailleur_locataire_boxes()

            # TABLEAU DÉTAIL
            y = 19*cm
            self.p.setFont("Helvetica-Bold", 12)
            self.p.drawString(2*cm, y, "DÉTAIL DU PAIEMENT")
            y -= 1*cm

            # Lignes du tableau
            self.p.setFont("Helvetica", 10)

            def draw_line(label, montant, bold=False):
                nonlocal y
                if bold:
                    self.p.setFont("Helvetica-Bold", 10)
                else:
                    self.p.setFont("Helvetica", 10)

                self.p.drawString(3*cm, y, label)
                self.p.drawRightString(18*cm, y, format_euro(montant))
                y -= 0.6*cm

            # Loyer HC
            draw_line("Loyer hors charges", tarif.loyer_hc)

            # Charges
            if tarif.charges > 0:
                label_charges = "Provisions sur charges" if self.bail.type_charges == 'PROVISION' else "Forfait de charges"
                draw_line(label_charges, tarif.charges)

            # Taxes
            if tarif.taxes > 0:
                draw_line("Taxes et contributions", tarif.taxes)

            # TVA si applicable
            if self.bail.soumis_tva:
                montant_tva = (float(tarif.loyer_hc) + float(tarif.charges)) * float(self.bail.taux_tva) / 100
                draw_line(f"TVA ({self.bail.taux_tva}%)", montant_tva)
                total = float(tarif.loyer_hc) + float(tarif.charges) + float(tarif.taxes) + montant_tva
            else:
                total = float(tarif.loyer_hc) + float(tarif.charges) + float(tarif.taxes)

            # Ligne de séparation
            y -= 0.3*cm
            self.p.setStrokeColor(colors.black)
            self.p.line(3*cm, y, 18*cm, y)
            y -= 0.7*cm

            # TOTAL
            draw_line("TOTAL PAYÉ", total, bold=True)

            # Texte de certification
            y -= 1*cm
            self.p.setFont("Helvetica-Oblique", 9)
            texte = "Je soussigné(e) certifie avoir reçu la somme indiquée ci-dessus au titre du loyer et des charges."
            self.p.drawString(2*cm, y, texte)

            y -= 0.7*cm
            self.p.setFont("Helvetica", 9)
            self.p.drawString(2*cm, y, f"Fait à {self.bail.local.immeuble.ville}, le {date.today().strftime('%d/%m/%Y')}")

            # Nouvelle page pour période suivante
            self.p.showPage()

        # Finaliser PDF
        self.p.save()
        pdf_content = buffer.getvalue()
        buffer.close()

        logger.info(f"Quittance générée : {len(pdf_content)} bytes")
        return pdf_content

    def generer_avis_echeance(self, periodes):
        """
        Génère un avis d'échéance (identique à quittance mais titre différent).

        Args:
            periodes (list): Liste de dates

        Returns:
            bytes: Contenu du PDF généré
        """
        # Réutilise la même logique que quittance
        # On pourrait créer une méthode interne commune, mais pour l'instant on duplique
        # TODO: Refactoriser avec generer_quittance si nécessaire

        logger.info(f"Génération avis d'échéance pour {self.bail}")

        from io import BytesIO

        # Convertir dates
        sorted_dates = []
        for p in periodes:
            if isinstance(p, str):
                sorted_dates.append(datetime.strptime(p, '%Y-%m-%d').date())
            else:
                sorted_dates.append(p)
        sorted_dates.sort()

        is_trimestriel = (self.bail.frequence_paiement == 'TRIMESTRIEL')

        buffer = BytesIO()
        self.p = canvas.Canvas(buffer, pagesize=A4)

        for current_date in sorted_dates:
            tarif = self._get_tarif_or_error(current_date)

            # Calcul période
            if is_trimestriel:
                mois_fin_p = current_date.month + 2
                annee_fin_p = current_date.year
                if mois_fin_p > 12:
                    mois_fin_p -= 12
                    annee_fin_p += 1
                last_day = calendar.monthrange(annee_fin_p, mois_fin_p)[1]
                periode_fin = date(annee_fin_p, mois_fin_p, last_day)
            else:
                last_day = calendar.monthrange(current_date.year, current_date.month)[1]
                periode_fin = current_date.replace(day=last_day)

            # EN-TÊTE (titre différent)
            sous_titre = f"Échéance du {self._format_date(current_date)} au {self._format_date(periode_fin)}"
            self._draw_header_standard("AVIS D'ÉCHÉANCE", sous_titre)

            # CADRES
            self._draw_bailleur_locataire_boxes()

            # TABLEAU
            y = 19*cm
            self.p.setFont("Helvetica-Bold", 12)
            self.p.drawString(2*cm, y, "MONTANT À PAYER")
            y -= 1*cm

            self.p.setFont("Helvetica", 10)

            def draw_line(label, montant, bold=False):
                nonlocal y
                if bold:
                    self.p.setFont("Helvetica-Bold", 10)
                else:
                    self.p.setFont("Helvetica", 10)
                self.p.drawString(3*cm, y, label)
                self.p.drawRightString(18*cm, y, format_euro(montant))
                y -= 0.6*cm

            draw_line("Loyer hors charges", tarif.loyer_hc)

            if tarif.charges > 0:
                label_charges = "Provisions sur charges" if self.bail.type_charges == 'PROVISION' else "Forfait de charges"
                draw_line(label_charges, tarif.charges)

            if tarif.taxes > 0:
                draw_line("Taxes et contributions", tarif.taxes)

            if self.bail.soumis_tva:
                montant_tva = (float(tarif.loyer_hc) + float(tarif.charges)) * float(self.bail.taux_tva) / 100
                draw_line(f"TVA ({self.bail.taux_tva}%)", montant_tva)
                total = float(tarif.loyer_hc) + float(tarif.charges) + float(tarif.taxes) + montant_tva
            else:
                total = float(tarif.loyer_hc) + float(tarif.charges) + float(tarif.taxes)

            y -= 0.3*cm
            self.p.line(3*cm, y, 18*cm, y)
            y -= 0.7*cm

            draw_line("TOTAL À PAYER", total, bold=True)

            # Date limite de paiement : début de la période (échéance à terme à échoir)
            y -= 1*cm
            self.p.setFont("Helvetica-Bold", 10)
            date_limite = current_date  # Paiement dû au début de la période
            self.p.drawString(2*cm, y, f"À payer avant le : {self._format_date(date_limite)}")

            self.p.showPage()

        self.p.save()
        pdf_content = buffer.getvalue()
        buffer.close()

        logger.info(f"Avis d'échéance généré : {len(pdf_content)} bytes")
        return pdf_content

    def _check_and_new_page(self, y, min_height=2*cm):
        """
        Vérifie si on doit créer une nouvelle page et retourne la nouvelle position y.

        Args:
            y (float): Position Y actuelle
            min_height (float): Hauteur minimale requise (défaut: 2cm)

        Returns:
            float: Nouvelle position Y
        """
        if y < min_height:
            self.p.showPage()
            # Mini-header sur nouvelle page
            self.p.setFont("Helvetica-Bold", 10)
            self.p.drawString(2*cm, 28*cm, "RÉGULARISATION DE CHARGES (suite)")
            return 27*cm
        return y

    def generer_regularisation(self, date_debut, date_fin, enregistrer_historique=True):
        """
        Génère le décompte de régularisation de charges sur une période donnée.

        Args:
            date_debut (date): Date de début de la période
            date_fin (date): Date de fin de la période
            enregistrer_historique (bool): Si True, sauvegarde dans la table Regularisation

        Returns:
            bytes: Contenu du PDF généré
        """
        from io import BytesIO
        from django.db.models import Sum, Q
        from .models import Depense, Consommation, Ajustement, Regularisation
        from .calculators import BailCalculator

        logger.info(f"Génération régularisation pour {self.bail}, période {date_debut} au {date_fin}")

        # Convertir en date si string
        if isinstance(date_debut, str):
            date_debut = datetime.strptime(date_debut, '%Y-%m-%d').date()
        if isinstance(date_fin, str):
            date_fin = datetime.strptime(date_fin, '%Y-%m-%d').date()

        # Calculs via BailCalculator
        total_provisions, details_provisions = BailCalculator.calculer_provisions_mensuelles(
            self.bail, date_debut, date_fin
        )

        # Calcul de la durée et présence
        nb_jours_periode = (date_fin - date_debut).days + 1
        debut_occup = max(date_debut, self.bail.date_debut)
        fin_occup = date_fin if not self.bail.date_fin else min(date_fin, self.bail.date_fin)

        nb_jours_presence = 0
        if debut_occup <= fin_occup:
            nb_jours_presence = (fin_occup - debut_occup).days + 1

        ratio_temps = nb_jours_presence / nb_jours_periode if nb_jours_periode > 0 else 0

        # Liste des détails calculs pour annexe
        details_calculs = []
        details_calculs.append("--- PARAMÈTRES GÉNÉRAUX ---")
        details_calculs.append(f"Période Régul : {date_debut} au {date_fin} ({nb_jours_periode} jours)")
        details_calculs.append(f"Présence Locataire : {nb_jours_presence} jours (Ratio global : {ratio_temps:.6f})")
        details_calculs.append("")
        details_calculs.append("--- DÉTAIL DÉPENSES ---")

        # Récupérer les dépenses
        depenses = Depense.objects.filter(
            Q(immeuble=self.bail.local.immeuble) &
            (
                Q(date__range=[date_debut, date_fin]) |
                Q(date_debut__lte=date_fin, date_fin__gte=date_debut)
            )
        ).distinct()

        total_part_locataire = 0

        # Créer PDF en mémoire
        buffer = BytesIO()
        self.p = canvas.Canvas(buffer, pagesize=A4)

        # EN-TÊTE
        sous_titre = f"Période du {self._format_date(date_debut)} au {self._format_date(date_fin)}"
        self._draw_header_standard("RÉGULARISATION DE CHARGES", sous_titre)

        # CADRES BAILLEUR / LOCATAIRE
        self._draw_bailleur_locataire_boxes()

        # Temps de présence
        self.p.setFont("Helvetica-Oblique", 8)
        self.p.drawString(2*cm, 20.5*cm, f"Temps de présence du locataire : {nb_jours_presence} jours sur {nb_jours_periode} jours (Prorata : {ratio_temps*100:.2f}%)")

        # TABLEAU DES DÉPENSES
        y = 19*cm
        self.p.setFont("Helvetica-Bold", 10)
        self.p.drawString(2*cm, y, "Détail des dépenses réelles :")
        y -= 0.8*cm

        # En-tête tableau
        self.p.setFont("Helvetica-Bold", 9)
        self.p.drawString(2*cm, y, "Nature")
        self.p.drawString(12*cm, y, "Montant Immeuble")
        self.p.drawString(16*cm, y, "Votre Quote-part")
        self.p.setLineWidth(0.5)
        self.p.line(2*cm, y - 0.2*cm, 19*cm, y - 0.2*cm)
        y -= 0.5*cm

        # Lignes de dépenses
        self.p.setFont("Helvetica", 8)
        for depense in depenses:
            cle = depense.cle_repartition
            if cle:
                qp_local = cle.quote_parts.filter(local=self.bail.local).first()
                total_cle = cle.quote_parts.aggregate(Sum('valeur'))['valeur__sum'] or 0

                if qp_local and total_cle > 0:
                    part_theorique = (depense.montant * qp_local.valeur) / total_cle

                    # LOGIQUE PRORATA INTELLIGENTE
                    if depense.date_debut and depense.date_fin:
                        duree_depense = (depense.date_fin - depense.date_debut).days + 1
                        if duree_depense <= 0:
                            duree_depense = 1

                        start_inter = max(depense.date_debut, date_debut)
                        end_inter = min(depense.date_fin, date_fin)
                        start_final = max(start_inter, debut_occup)
                        end_final = min(end_inter, fin_occup)

                        nb_jours_facturables = 0
                        if start_final <= end_final:
                            nb_jours_facturables = (end_final - start_final).days + 1

                        part_reelle = float(part_theorique) * (nb_jours_facturables / duree_depense)

                        details_calculs.append(f"[Dépense] {depense.libelle} ({format_euro(depense.montant)})")
                        details_calculs.append(f"  > Période facture : {depense.date_debut} au {depense.date_fin} ({duree_depense} jours)")
                        details_calculs.append(f"  > Intersection présence : {nb_jours_facturables} jours")
                        details_calculs.append(f"  > Calcul : {float(part_theorique):.2f}€ x ({nb_jours_facturables}/{duree_depense}) = {part_reelle:.2f}€")
                    else:
                        if not (date_debut <= depense.date <= date_fin):
                            continue
                        part_reelle = float(part_theorique) * ratio_temps

                        details_calculs.append(f"[Dépense] {depense.libelle} ({format_euro(depense.montant)})")
                        details_calculs.append(f"  > Sans période (Date: {depense.date}) -> Lissage global")
                        details_calculs.append(f"  > Calcul : {float(part_theorique):.2f}€ x Ratio {ratio_temps:.4f} = {part_reelle:.2f}€")

                    total_part_locataire += part_reelle

                    # Vérifier saut de page
                    y = self._check_and_new_page(y)

                    libelle_aff = f"{depense.libelle} ({cle.nom})"
                    if depense.date_debut and depense.date_fin:
                        libelle_aff += f" [{depense.date_debut.strftime('%d/%m')} au {depense.date_fin.strftime('%d/%m')}]"

                    self.p.drawString(2*cm, y, libelle_aff[:75])
                    self.p.drawString(12*cm, y, format_euro(depense.montant))
                    self.p.drawString(16*cm, y, format_euro(part_reelle))
                    y -= 0.6*cm

        # CONSOMMATIONS
        consommations = Consommation.objects.filter(
            Q(local=self.bail.local) &
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

                if conso.date_debut:
                    duree_conso = (conso.date_releve - conso.date_debut).days + 1
                    if duree_conso <= 0:
                        duree_conso = 1

                    start_inter = max(conso.date_debut, date_debut)
                    end_inter = min(conso.date_releve, date_fin)

                    nb_jours_conso = 0
                    if start_inter <= end_inter:
                        nb_jours_conso = (end_inter - start_inter).days + 1

                    quantite_reelle = quantite_reelle * (nb_jours_conso / duree_conso)

                    details_calculs.append(f"[Conso] {cle.nom} (Relevé: {conso.quantite})")
                    details_calculs.append(f"  > Période relevé : {conso.date_debut} au {conso.date_releve} ({duree_conso} jours)")
                    details_calculs.append(f"  > Intersection régul : {nb_jours_conso} jours")
                    details_calculs.append(f"  > Qté retenue : {float(conso.quantite):.2f} x ({nb_jours_conso}/{duree_conso}) = {quantite_reelle:.2f}")
                else:
                    details_calculs.append(f"[Conso] {cle.nom} (Relevé: {conso.quantite}) - 100% retenu")

                montant_conso = quantite_reelle * float(cle.prix_unitaire)
                total_part_locataire += montant_conso

                y = self._check_and_new_page(y)

                libelle_conso = f"{cle.nom} (Relevé: {conso.quantite})"
                if conso.date_debut:
                    libelle_conso += f" [Prorata: {quantite_reelle:.2f}]"

                self.p.drawString(2*cm, y, libelle_conso[:75])
                self.p.drawString(12*cm, y, f"PU: {format_euro(cle.prix_unitaire)}")
                self.p.drawString(16*cm, y, format_euro(montant_conso))
                y -= 0.6*cm

        # AJUSTEMENTS
        ajustements = Ajustement.objects.filter(bail=self.bail, date__range=[date_debut, date_fin])
        for ajustement in ajustements:
            total_part_locataire += float(ajustement.montant)

            y = self._check_and_new_page(y)

            self.p.drawString(2*cm, y, f"Ajustement : {ajustement.libelle}"[:75])
            self.p.drawString(12*cm, y, "-")
            self.p.drawString(16*cm, y, format_euro(ajustement.montant))
            y -= 0.6*cm

        # BILAN
        y -= 0.8*cm
        y = self._check_and_new_page(y, min_height=4*cm)

        self.p.setFont("Helvetica-Bold", 11)
        self.p.drawString(10*cm, y, f"TOTAL DÉPENSES RÉELLES : {format_euro(total_part_locataire)}")

        # Provisions (calculées par BailCalculator)
        details_calculs.append("")
        details_calculs.extend(details_provisions)

        y -= 1*cm
        self.p.drawString(10*cm, y, f"PROVISIONS VERSÉES : -{format_euro(total_provisions)}")

        solde = total_part_locataire - total_provisions
        y -= 1.5*cm
        self.p.setFont("Helvetica-Bold", 14)
        if solde > 0:
            self.p.drawString(2*cm, y, f"RESTE À PAYER : {format_euro(solde)}")
        else:
            self.p.drawString(2*cm, y, f"TROP PERÇU (À REMBOURSER) : {format_euro(abs(solde))}")

        # HISTORISATION
        if enregistrer_historique:
            Regularisation.objects.create(
                bail=self.bail,
                date_debut=date_debut,
                date_fin=date_fin,
                montant_reel=total_part_locataire,
                montant_provisions=total_provisions,
                solde=solde
            )
            logger.info(f"Régularisation enregistrée en base : solde={solde}")

        # PAGE ANNEXE (DÉTAILS CALCULS)
        self.p.showPage()
        self.p.setFont("Helvetica-Bold", 14)
        self.p.drawString(2*cm, 28*cm, "ANNEXE : DÉTAIL DES CALCULS (ADMINISTRATEUR)")
        self.p.setFont("Courier", 9)
        y_annex = 27*cm

        for line in details_calculs:
            self.p.drawString(2*cm, y_annex, line)
            y_annex -= 0.5*cm
            if y_annex < 2*cm:
                self.p.showPage()
                self.p.setFont("Courier", 9)
                y_annex = 28*cm

        self.p.showPage()
        self.p.save()

        pdf_content = buffer.getvalue()
        buffer.close()

        logger.info(f"Régularisation générée : {len(pdf_content)} bytes, solde={solde}")
        return pdf_content

    def generer_solde_tout_compte(self, date_sortie, statut_loyer, montant_retenues=0, desc_retenues=""):
        """
        Génère l'arrêté de compte de fin de bail (Solde de tout compte).

        Args:
            date_sortie (date): Date de sortie du locataire
            statut_loyer (str): 'NON_PAYE' ou 'PAYE_TOTAL'
            montant_retenues (float): Montant des retenues sur dépôt de garantie
            desc_retenues (str): Description des retenues

        Returns:
            bytes: Contenu du PDF généré
        """
        from io import BytesIO

        logger.info(f"Génération solde tout compte pour {self.bail}, date sortie={date_sortie}")

        # Convertir en date si string
        if isinstance(date_sortie, str):
            date_sortie = datetime.strptime(date_sortie, '%Y-%m-%d').date()

        # RÉCUPÉRER LA TARIFICATION À LA DATE DE SORTIE
        tarif_sortie = self._get_tarif_or_error(date_sortie)

        # CALCULS
        # A. Prorata Loyer (Dernière période)
        if self.bail.frequence_paiement == 'TRIMESTRIEL':
            mois_debut_trim = ((date_sortie.month - 1) // 3) * 3 + 1
            debut_periode = date(date_sortie.year, mois_debut_trim, 1)
            m_fin = mois_debut_trim + 2
            y_fin = date_sortie.year
            if m_fin > 12:
                m_fin -= 12
                y_fin += 1
            last_day = calendar.monthrange(y_fin, m_fin)[1]
            fin_periode = date(y_fin, m_fin, last_day)
        else:
            debut_periode = date(date_sortie.year, date_sortie.month, 1)
            last_day = calendar.monthrange(date_sortie.year, date_sortie.month)[1]
            fin_periode = date(date_sortie.year, date_sortie.month, last_day)

        nb_jours_periode = (fin_periode - debut_periode).days + 1
        nb_jours_presence = (date_sortie - debut_periode).days + 1

        montant_periode = float(tarif_sortie.loyer_hc)
        loyer_prorata = montant_periode * (nb_jours_presence / nb_jours_periode)

        # Impact financier du loyer
        if statut_loyer == "NON_PAYE":
            impact_loyer = -loyer_prorata
            lbl_loyer = f"Loyer dû au prorata ({nb_jours_presence}/{nb_jours_periode}j)"
        else:
            trop_percu = montant_periode - loyer_prorata
            impact_loyer = trop_percu
            lbl_loyer = f"Remboursement trop-perçu loyer (Sortie le {date_sortie.strftime('%d/%m')})"

        # C. Calcul Final
        depot = float(self.bail.depot_garantie)
        solde_final = depot + impact_loyer - montant_retenues

        # GÉNÉRATION PDF
        buffer = BytesIO()
        self.p = canvas.Canvas(buffer, pagesize=A4)

        # EN-TÊTE
        sous_titre = f"Arrêté au {self._format_date(date_sortie)}"
        self._draw_header_standard("SOLDE DE TOUT COMPTE", sous_titre)

        # CADRES BAILLEUR / LOCATAIRE
        self._draw_bailleur_locataire_boxes()

        # TABLEAU DE CALCUL
        y = 19*cm
        self.p.setFont("Helvetica-Bold", 12)
        self.p.drawString(2*cm, y, "DÉTAIL DU COMPTE")
        y -= 1*cm

        def draw_line(label, amount, is_total=False):
            nonlocal y
            if is_total:
                self.p.setFont("Helvetica-Bold", 12)
                self.p.setStrokeColor(colors.black)
                self.p.line(2*cm, y+0.5*cm, 19*cm, y+0.5*cm)
            else:
                self.p.setFont("Helvetica", 11)

            self.p.drawString(2*cm, y, label)
            self.p.drawRightString(19*cm, y, format_euro(amount))
            y -= 1*cm

        draw_line("Crédit : Dépôt de garantie initial", depot)
        draw_line(lbl_loyer, impact_loyer)

        if montant_retenues > 0:
            draw_line("Débit : Retenues / Dégradations", -montant_retenues)
            # Description
            self.p.setFont("Helvetica-Oblique", 9)
            self.p.drawString(3*cm, y+0.6*cm, f"({desc_retenues})")

        y -= 1*cm
        draw_line("SOLDE À RESTITUER AU LOCATAIRE", solde_final, is_total=True)

        self.p.showPage()
        self.p.save()

        pdf_content = buffer.getvalue()
        buffer.close()

        logger.info(f"Solde tout compte généré : {len(pdf_content)} bytes, solde={solde_final}")
        return pdf_content

    def generer_revision_loyer(self, nouvel_indice, nouveau_trimestre, date_application, ancien_indice=None):
        """
        Génère le courrier de révision de loyer (IRL/ILC).

        Note: Cette méthode génère UNIQUEMENT le courrier PDF.
        La mise à jour du bail (création de tarification) doit être faite séparément via l'assistant.

        Args:
            nouvel_indice (float): Nouvel indice IRL/ILC
            nouveau_trimestre (str): Trimestre du nouvel indice (ex: "T1 2024")
            date_application (date): Date d'application de la révision
            ancien_indice (float): Ancien indice (si None, utilise celui du bail)

        Returns:
            bytes: Contenu du PDF généré
        """
        from io import BytesIO

        logger.info(f"Génération révision loyer pour {self.bail}, indice={nouvel_indice}")

        # Convertir en date si string
        if isinstance(date_application, str):
            date_application = datetime.strptime(date_application, '%Y-%m-%d').date()

        # Récupérer l'ancien indice
        if ancien_indice is None:
            tarif_actuel = self.bail.tarification_actuelle
            if tarif_actuel and tarif_actuel.indice_reference:
                ancien_indice = float(tarif_actuel.indice_reference)
            else:
                raise ValueError("Impossible de calculer la révision : aucun indice de référence dans le bail")

        # Calcul du nouveau loyer
        ancien_loyer = float(self.bail.loyer_hc)
        nouveau_loyer = ancien_loyer * (nouvel_indice / ancien_indice)

        # Récupérer l'ancien trimestre
        tarif_actuel = self.bail.tarification_actuelle
        ancien_trimestre = tarif_actuel.trimestre_reference if tarif_actuel else "?"

        # GÉNÉRATION PDF
        buffer = BytesIO()
        self.p = canvas.Canvas(buffer, pagesize=A4)

        # En-tête simplifié (style lettre)
        self.p.setFont("Helvetica-Bold", 12)
        self.p.drawString(2*cm, 26*cm, "BAILLEUR :")
        self.p.setFont("Helvetica", 12)
        proprio = self.bail.local.immeuble.proprietaire
        if proprio:
            self.p.drawString(2*cm, 25.5*cm, proprio.nom)
            self.p.drawString(2*cm, 25*cm, f"{proprio.adresse} {proprio.code_postal} {proprio.ville}")

        self.p.setFont("Helvetica-Bold", 12)
        self.p.drawString(12*cm, 26*cm, "LOCATAIRE :")
        self.p.setFont("Helvetica", 12)
        occupant = self.bail.occupants.filter(role='LOCATAIRE').first()
        if occupant:
            self.p.drawString(12*cm, 25.5*cm, f"{occupant.nom} {occupant.prenom}")
        self.p.drawString(12*cm, 25*cm, self.bail.local.immeuble.adresse)

        self.p.setFont("Helvetica-Bold", 14)
        self.p.drawCentredString(10.5*cm, 22*cm, "OBJET : RÉVISION DU LOYER")

        # Corps de la lettre
        self.p.setFont("Helvetica", 11)
        text_y = 20*cm

        self.p.drawString(2*cm, text_y, f"Fait à {self.bail.local.immeuble.ville}, le {date.today().strftime('%d/%m/%Y')}")
        text_y -= 2*cm

        self.p.drawString(2*cm, text_y, "Madame, Monsieur,")
        text_y -= 1*cm
        self.p.drawString(2*cm, text_y, "Conformément à la clause d'indexation inscrite dans votre bail, je vous informe")
        text_y -= 0.5*cm
        self.p.drawString(2*cm, text_y, f"que votre loyer est révisé à compter du {date_application.strftime('%d/%m/%Y')}.")
        text_y -= 1.5*cm

        self.p.drawString(2*cm, text_y, f"Ancien indice : {ancien_indice} ({ancien_trimestre})")
        text_y -= 0.5*cm
        self.p.drawString(2*cm, text_y, f"Nouvel indice : {nouvel_indice} ({nouveau_trimestre})")
        text_y -= 1.5*cm

        self.p.setFont("Helvetica-Bold", 12)
        self.p.drawString(2*cm, text_y, f"Nouveau Loyer Hors Charges : {format_euro(nouveau_loyer)}")

        self.p.showPage()
        self.p.save()

        pdf_content = buffer.getvalue()
        buffer.close()

        logger.info(f"Révision loyer générée : {len(pdf_content)} bytes, nouveau_loyer={nouveau_loyer}")
        return pdf_content
