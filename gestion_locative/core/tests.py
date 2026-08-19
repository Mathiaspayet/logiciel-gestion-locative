"""
Tests de non-regression pour les calculs financiers et la securite.

Chaque test porte la reference du constat d'audit qu'il verrouille (C-01, E-03...).
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase, Client
from django.test.utils import CaptureQueriesContext
from django.db import connection
from django.core.exceptions import ValidationError

from core.models import (
    Proprietaire, Immeuble, Local, Bail, BailTarification, Occupant,
    CleRepartition, QuotePart, Depense, Consommation, Regularisation,
    CreditImmobilier, ChargeFiscale, VacanceLocative, EstimationValeur, Ajustement,
)
from core.calculators import BailCalculator
from core.patrimoine_calculators import (
    CreditGenerator, FiscaliteCalculator, RentabiliteCalculator,
)


class BaseFixture(TestCase):
    """Jeu de donnees minimal partage."""

    def setUp(self):
        self.proprietaire = Proprietaire.objects.create(
            nom="Dupont", adresse="1 rue A", ville="Lyon", code_postal="69001"
        )
        self.immeuble = Immeuble.objects.create(
            proprietaire=self.proprietaire, nom="Residence A", adresse="1 rue A",
            ville="Lyon", code_postal="69001",
            prix_achat=Decimal("200000"), date_achat=date(2020, 1, 1),
            frais_notaire=Decimal("15000"), frais_agence=Decimal("5000"),
        )
        self.local = Local.objects.create(
            immeuble=self.immeuble, numero_porte="1", surface_m2=Decimal("50")
        )


class ProvisionsMensuellesTests(BaseFixture):
    """C-01 / C-02 : lecture de la tarification au jour de presence, pas au 1er du mois."""

    def test_bail_demarrant_en_cours_de_mois(self):
        """C-01 : un bail entre le 15 ne doit pas faire echouer la regularisation."""
        bail = Bail.objects.create(local=self.local, date_debut=date(2024, 3, 15))
        BailTarification.objects.create(
            bail=bail, date_debut=date(2024, 3, 15),
            loyer_hc=Decimal("500"), charges=Decimal("100"),
        )

        total, details = BailCalculator.calculer_provisions_mensuelles(
            bail, date(2024, 1, 1), date(2024, 12, 31)
        )

        # Mars : 17 jours sur 31, puis 9 mois pleins a 100 EUR.
        attendu = (Decimal("100") * 17 / 31).quantize(Decimal("0.01")) + Decimal("900")
        self.assertEqual(total, attendu)

    def test_changement_de_tarif_en_cours_de_mois(self):
        """C-02 : le mois de bascule est proratise entre les deux tarifs."""
        bail = Bail.objects.create(local=self.local, date_debut=date(2024, 1, 1))
        BailTarification.objects.create(
            bail=bail, date_debut=date(2024, 1, 1), date_fin=date(2024, 6, 14),
            loyer_hc=Decimal("500"), charges=Decimal("100"),
        )
        BailTarification.objects.create(
            bail=bail, date_debut=date(2024, 6, 15),
            loyer_hc=Decimal("600"), charges=Decimal("200"),
        )

        total, details = BailCalculator.calculer_provisions_mensuelles(
            bail, date(2024, 6, 1), date(2024, 6, 30)
        )

        attendu = (
            (Decimal("100") * 14 / 30).quantize(Decimal("0.01"))
            + (Decimal("200") * 16 / 30).quantize(Decimal("0.01"))
        )
        self.assertEqual(total, attendu)
        self.assertGreater(total, Decimal("150"))

    def test_total_est_un_decimal(self):
        """E-04 : l'argent ne circule plus en float."""
        bail = Bail.objects.create(local=self.local, date_debut=date(2024, 1, 1))
        BailTarification.objects.create(
            bail=bail, date_debut=date(2024, 1, 1),
            loyer_hc=Decimal("500"), charges=Decimal("100"),
        )
        total, _ = BailCalculator.calculer_provisions_mensuelles(
            bail, date(2024, 1, 1), date(2024, 1, 31)
        )
        self.assertIsInstance(total, Decimal)
        self.assertEqual(total, Decimal("100.00"))

    def test_mois_complet_hors_periode_de_bail(self):
        """Un bail termine ne genere pas de provisions apres sa date de fin."""
        bail = Bail.objects.create(
            local=self.local, date_debut=date(2024, 1, 1), date_fin=date(2024, 2, 29)
        )
        BailTarification.objects.create(
            bail=bail, date_debut=date(2024, 1, 1),
            loyer_hc=Decimal("500"), charges=Decimal("100"),
        )
        total, _ = BailCalculator.calculer_provisions_mensuelles(
            bail, date(2024, 1, 1), date(2024, 12, 31)
        )
        self.assertEqual(total, Decimal("200.00"))


class BilanFiscalTests(BaseFixture):
    """C-03 : pas de double comptage des interets d'emprunt."""

    def setUp(self):
        super().setUp()
        self.credit = CreditImmobilier.objects.create(
            immeuble=self.immeuble, nom_banque="Banque", capital_emprunte=Decimal("100000"),
            taux_interet=Decimal("2.0"), duree_mois=240, date_debut=date(2024, 1, 1),
            assurance_mensuelle=Decimal("20"),
        )
        CreditGenerator(self.credit).creer_echeances_en_base()

    def test_interets_saisis_non_cumules_avec_echeancier(self):
        ChargeFiscale.objects.create(
            immeuble=self.immeuble, type_charge='INTERETS', annee=2024, montant=Decimal("1980")
        )
        ChargeFiscale.objects.create(
            immeuble=self.immeuble, type_charge='TAXE_FONCIERE', annee=2024, montant=Decimal("800")
        )

        bilan = FiscaliteCalculator.generer_bilan_fiscal(self.immeuble, 2024)

        interets_echeancier = RentabiliteCalculator.get_interets_annuels(self.immeuble, 2024)
        # Seule la taxe fonciere reste dans les charges saisies.
        self.assertEqual(bilan['charges']['total_charges_deductibles'], Decimal("800"))
        self.assertEqual(bilan['charges']['interets_emprunts'], interets_echeancier)
        self.assertEqual(
            bilan['resultat']['total_charges'],
            Decimal("800") + interets_echeancier + bilan['charges']['assurance_emprunt'],
        )

    def test_repli_sur_les_charges_saisies_sans_echeancier(self):
        """Sans echeancier, les interets saisis a la main restent pris en compte."""
        self.credit.echeances.all().delete()
        ChargeFiscale.objects.create(
            immeuble=self.immeuble, type_charge='INTERETS', annee=2024, montant=Decimal("1980")
        )

        bilan = FiscaliteCalculator.generer_bilan_fiscal(self.immeuble, 2024)

        self.assertEqual(bilan['charges']['interets_emprunts'], Decimal("1980"))
        self.assertEqual(bilan['resultat']['total_charges'], Decimal("1980"))


class CoutAcquisitionTests(BaseFixture):
    """E-03 : le prix d'achat est hors frais, les frais s'ajoutent une seule fois."""

    def test_cout_total(self):
        self.assertEqual(self.immeuble.cout_total_acquisition, Decimal("220000"))

    def test_libelle_sans_ambiguite(self):
        champ = Immeuble._meta.get_field('prix_achat')
        self.assertIn("hors frais", champ.verbose_name.lower())


class CreditTests(BaseFixture):
    """E-01 : pas de credit sans echeancier."""

    def test_duree_nulle_refusee(self):
        credit = CreditImmobilier(
            immeuble=self.immeuble, nom_banque="B", capital_emprunte=Decimal("1000"),
            taux_interet=Decimal("2"), duree_mois=0, date_debut=date(2024, 1, 1),
        )
        with self.assertRaises(ValidationError):
            credit.full_clean()

    def test_mensualite_est_un_decimal(self):
        credit = CreditImmobilier.objects.create(
            immeuble=self.immeuble, nom_banque="B", capital_emprunte=Decimal("100000"),
            taux_interet=Decimal("2"), duree_mois=240, date_debut=date(2024, 1, 1),
            assurance_mensuelle=Decimal("20"),
        )
        self.assertIsInstance(credit.mensualite, Decimal)
        self.assertIsInstance(credit.capital_restant_du, Decimal)

    def test_echeancier_solde_le_capital(self):
        credit = CreditImmobilier.objects.create(
            immeuble=self.immeuble, nom_banque="B", capital_emprunte=Decimal("100000"),
            taux_interet=Decimal("2"), duree_mois=120, date_debut=date(2024, 1, 1),
        )
        echeancier = CreditGenerator(credit).generer_echeancier()
        total_capital = sum(e['capital_rembourse'] for e in echeancier)
        self.assertEqual(total_capital, Decimal("100000.00"))
        self.assertEqual(echeancier[-1]['capital_restant_du'], Decimal("0.00"))


class ModelValidationTests(BaseFixture):
    """M-09 : validations metier manquantes."""

    def test_consommation_index_decroissant_refuse(self):
        cle = CleRepartition.objects.create(
            immeuble=self.immeuble, nom="Eau", mode_repartition='CONSOMMATION',
            prix_unitaire=Decimal("3.50"),
        )
        conso = Consommation(
            local=self.local, cle_repartition=cle, date_releve=date(2024, 6, 30),
            index_debut=Decimal("100"), index_fin=Decimal("90"),
        )
        with self.assertRaises(ValidationError):
            conso.full_clean()

    def test_vacances_qui_se_chevauchent_refusees(self):
        VacanceLocative.objects.create(
            local=self.local, date_debut=date(2024, 1, 1), date_fin=date(2024, 3, 31)
        )
        doublon = VacanceLocative(
            local=self.local, date_debut=date(2024, 3, 1), date_fin=date(2024, 4, 30)
        )
        with self.assertRaises(ValidationError):
            doublon.full_clean()

    def test_regularisation_unique_par_periode(self):
        """E-02 : une meme periode ne peut pas etre enregistree deux fois."""
        bail = Bail.objects.create(local=self.local, date_debut=date(2024, 1, 1))
        Regularisation.objects.create(
            bail=bail, date_debut=date(2024, 1, 1), date_fin=date(2024, 12, 31),
            montant_reel=Decimal("1200"), montant_provisions=Decimal("1000"),
            solde=Decimal("200"),
        )
        from django.db import IntegrityError, transaction
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Regularisation.objects.create(
                    bail=bail, date_debut=date(2024, 1, 1), date_fin=date(2024, 12, 31),
                    montant_reel=Decimal("1300"), montant_provisions=Decimal("1000"),
                    solde=Decimal("300"),
                )


class SecuriteTests(BaseFixture):
    """C-04 / C-05 / M-04 : surface web."""

    def setUp(self):
        super().setUp()
        self.user = User.objects.create_user('testuser', password='motdepasse-solide-1')
        self.client = Client()

    def test_redirection_externe_refusee(self):
        """C-05 : ?next= vers un domaine tiers ne doit pas etre suivi."""
        reponse = self.client.post(
            '/app/login/?next=https://example.com/phishing',
            {'username': 'testuser', 'password': 'motdepasse-solide-1'},
        )
        self.assertEqual(reponse.status_code, 302)
        self.assertNotIn('example.com', reponse['Location'])

    def test_redirection_interne_conservee(self):
        reponse = self.client.post(
            '/app/login/?next=/app/patrimoine/',
            {'username': 'testuser', 'password': 'motdepasse-solide-1'},
        )
        self.assertEqual(reponse['Location'], '/app/patrimoine/')

    def test_nom_immeuble_non_injecte_dans_le_script(self):
        """C-04 : XSS stocke via le nom d'un immeuble."""
        charge_utile = '</script><img src=x onerror=alert(1)>'
        self.immeuble.nom = charge_utile
        self.immeuble.save()

        self.client.force_login(self.user)
        html = self.client.get('/app/patrimoine/').content.decode()

        self.assertNotIn(charge_utile, html)
        self.assertIn('\\u003C/script\\u003E', html.replace('\\u003c', '\\u003C'))

    def test_tentatives_de_connexion_limitees(self):
        """M-04 : la 6e tentative echouee est bloquee."""
        for _ in range(5):
            self.client.post('/app/login/', {'username': 'testuser', 'password': 'faux'})

        reponse = self.client.post(
            '/app/login/', {'username': 'testuser', 'password': 'motdepasse-solide-1'}
        )
        self.assertEqual(reponse.status_code, 200)
        self.assertContains(reponse, "Trop de tentatives", status_code=200)


class PerformanceTests(BaseFixture):
    """M-01 : le tableau de bord ne doit plus exploser en requetes."""

    def setUp(self):
        super().setUp()
        self.user = User.objects.create_user('perf', password='motdepasse-solide-1')
        for i in range(3):
            immeuble = Immeuble.objects.create(
                proprietaire=self.proprietaire, nom=f"Immeuble {i}", adresse="a",
                ville="Lyon", code_postal="69001", prix_achat=Decimal("200000"),
                date_achat=date(2020, 1, 1),
            )
            for j in range(4):
                local = Local.objects.create(
                    immeuble=immeuble, numero_porte=str(j), surface_m2=Decimal("50")
                )
                bail = Bail.objects.create(local=local, date_debut=date(2020, 1, 1))
                BailTarification.objects.create(
                    bail=bail, date_debut=date(2020, 1, 1),
                    loyer_hc=Decimal("500"), charges=Decimal("100"),
                )

    def test_dashboard_sous_cent_requetes(self):
        self.client.force_login(self.user)
        with CaptureQueriesContext(connection) as requetes:
            reponse = self.client.get('/app/')
        self.assertEqual(reponse.status_code, 200)
        self.assertLess(
            len(requetes), 100,
            f"Le dashboard execute {len(requetes)} requetes SQL",
        )

    def test_loyer_ttc_ne_requete_qu_une_fois(self):
        bail = Bail.objects.filter(tarifications__isnull=False).first()
        bail = Bail.objects.get(pk=bail.pk)
        with CaptureQueriesContext(connection) as requetes:
            _ = bail.loyer_ttc
        self.assertLessEqual(len(requetes), 1)


class FiltresTests(TestCase):
    """M-08 : une valeur absente ne doit pas s'afficher comme un montant nul."""

    def test_euro_valeur_absente(self):
        from core.templatetags.app_filters import euro
        self.assertEqual(euro(None), "\u2014")
        self.assertEqual(euro("abc"), "\u2014")

    def test_euro_valeur_nulle(self):
        from core.templatetags.app_filters import euro
        self.assertEqual(euro(0), "0,00 \u20ac")


class GenerationPdfTests(BaseFixture):
    """Fumigation : les PDF doivent toujours se generer apres le passage en Decimal."""

    def setUp(self):
        super().setUp()
        self.bail = Bail.objects.create(
            local=self.local, date_debut=date(2024, 1, 1), depot_garantie=Decimal("900"),
        )
        BailTarification.objects.create(
            bail=self.bail, date_debut=date(2024, 1, 1),
            loyer_hc=Decimal("500"), charges=Decimal("100"), taxes=Decimal("10"),
            indice_reference=Decimal("143.46"), trimestre_reference="T1 2024",
        )
        Occupant.objects.create(
            bail=self.bail, nom="Martin", prenom="Claire", role='LOCATAIRE'
        )
        self.cle = CleRepartition.objects.create(
            immeuble=self.immeuble, nom="Charges generales", mode_repartition='TANTIEMES'
        )
        QuotePart.objects.create(cle=self.cle, local=self.local, valeur=Decimal("500"))
        Depense.objects.create(
            immeuble=self.immeuble, cle_repartition=self.cle, date=date(2024, 5, 15),
            libelle="Facture EDF", montant=Decimal("1200"),
            date_debut=date(2024, 1, 1), date_fin=date(2024, 12, 31),
        )

    def _generateur(self):
        from core.pdf_generator import PDFGenerator
        return PDFGenerator(self.bail)

    def test_quittance(self):
        pdf = self._generateur().generer_quittance(['2024-03-01'])
        self.assertTrue(pdf.startswith(b'%PDF'))

    def test_avis_echeance(self):
        pdf = self._generateur().generer_avis_echeance(['2024-03-01'])
        self.assertTrue(pdf.startswith(b'%PDF'))

    def test_regularisation_et_non_duplication(self):
        """E-02 : regenerer le meme decompte met a jour au lieu d'empiler."""
        pdf = self._generateur().generer_regularisation('2024-01-01', '2024-12-31', True)
        self.assertTrue(pdf.startswith(b'%PDF'))
        self.assertEqual(Regularisation.objects.count(), 1)

        self._generateur().generer_regularisation('2024-01-01', '2024-12-31', True)
        self.assertEqual(Regularisation.objects.count(), 1)

        regul = Regularisation.objects.get()
        # Quote-part unique : la totalite de la depense revient au local.
        self.assertEqual(regul.montant_reel, Decimal("1200.00"))
        self.assertEqual(regul.montant_provisions, Decimal("1200.00"))
        self.assertEqual(regul.solde, Decimal("0.00"))

    def test_regularisation_signale_consommation_sans_prix(self):
        """E-05 : un releve non valorisable doit etre signale, pas ignore."""
        cle_eau = CleRepartition.objects.create(
            immeuble=self.immeuble, nom="Eau froide", mode_repartition='CONSOMMATION',
        )
        Consommation.objects.create(
            local=self.local, cle_repartition=cle_eau, date_releve=date(2024, 6, 30),
            index_debut=Decimal("100"), index_fin=Decimal("150"),
        )
        with self.assertLogs('core.pdf_generator', level='WARNING') as journal:
            self._generateur().generer_regularisation('2024-01-01', '2024-12-31', False)
        self.assertTrue(any("NON FACTURE" in ligne for ligne in journal.output))

    def test_solde_tout_compte(self):
        pdf = self._generateur().generer_solde_tout_compte(
            date(2024, 6, 15), "PAYE", Decimal("150"), "Retenue menage"
        )
        self.assertTrue(pdf.startswith(b'%PDF'))

    def test_revision_loyer(self):
        pdf = self._generateur().generer_revision_loyer(
            145.47, "T1 2025", date(2025, 1, 1)
        )
        self.assertTrue(pdf.startswith(b'%PDF'))


class ToutesLesPagesTests(TestCase):
    """Fumigation : chaque page doit repondre, y compris apres le passage en Decimal.

    C'est ce test qui a rattrape les melanges Decimal/float dans les vues de
    presentation (tableau de bord immeuble, admin des credits).
    """

    def setUp(self):
        self.user = User.objects.create_superuser('admin', 'a@b.c', 'motdepasse-solide-1')
        self.proprietaire = Proprietaire.objects.create(
            nom="P", adresse="a", ville="Lyon", code_postal="69001"
        )
        self.immeuble = Immeuble.objects.create(
            proprietaire=self.proprietaire, nom="I", adresse="a", ville="Lyon",
            code_postal="69001", prix_achat=Decimal("200000"), date_achat=date(2020, 1, 1),
            frais_notaire=Decimal("15000"),
        )
        self.local = Local.objects.create(
            immeuble=self.immeuble, numero_porte="1", surface_m2=Decimal("50")
        )
        self.bail = Bail.objects.create(
            local=self.local, date_debut=date(2022, 1, 1), depot_garantie=Decimal("900")
        )
        BailTarification.objects.create(
            bail=self.bail, date_debut=date(2022, 1, 1), loyer_hc=Decimal("500"),
            charges=Decimal("100"), taxes=Decimal("5"),
            indice_reference=Decimal("143.46"), trimestre_reference="T1 2024",
        )
        Occupant.objects.create(bail=self.bail, nom="M", prenom="C", role='LOCATAIRE')
        self.cle = CleRepartition.objects.create(
            immeuble=self.immeuble, nom="Generales", mode_repartition='TANTIEMES'
        )
        QuotePart.objects.create(cle=self.cle, local=self.local, valeur=Decimal("500"))
        Depense.objects.create(
            immeuble=self.immeuble, cle_repartition=self.cle, date=date(2024, 5, 1),
            libelle="EDF", montant=Decimal("1200"),
        )
        self.credit = CreditImmobilier.objects.create(
            immeuble=self.immeuble, nom_banque="B", capital_emprunte=Decimal("100000"),
            taux_interet=Decimal("2"), duree_mois=240, date_debut=date(2022, 1, 1),
            assurance_mensuelle=Decimal("20"),
        )
        CreditGenerator(self.credit).creer_echeances_en_base()
        EstimationValeur.objects.create(
            immeuble=self.immeuble, date_estimation=date(2024, 1, 1),
            valeur_estimee=Decimal("240000"),
        )
        ChargeFiscale.objects.create(
            immeuble=self.immeuble, type_charge='TAXE_FONCIERE', annee=2024,
            montant=Decimal("800"),
        )
        self.client.force_login(self.user)

    def _urls(self):
        i, l, b, c, cr = (
            self.immeuble.pk, self.local.pk, self.bail.pk, self.cle.pk, self.credit.pk
        )
        urls = [
            '/app/', '/app/patrimoine/', '/app/depenses/ajouter/',
            f'/app/immeubles/{i}/', f'/app/baux/{b}/', f'/app/immeubles/{i}/fiscal/',
            f'/app/cles/{c}/',
            '/app/immeubles/creer/', f'/app/immeubles/{i}/modifier/',
            f'/app/immeubles/{i}/supprimer/', f'/app/immeubles/{i}/locaux/creer/',
            f'/app/locaux/{l}/modifier/', f'/app/locaux/{l}/baux/creer/',
            f'/app/baux/{b}/modifier/', f'/app/baux/{b}/tarifications/creer/',
            f'/app/baux/{b}/occupants/creer/', f'/app/immeubles/{i}/estimations/creer/',
            f'/app/immeubles/{i}/credits/creer/', f'/app/credits/{cr}/modifier/',
            f'/app/immeubles/{i}/depenses/creer/', f'/app/immeubles/{i}/cles/creer/',
            f'/app/cles/{c}/quotesparts/creer/', f'/app/immeubles/{i}/consommations/creer/',
            f'/app/baux/{b}/regularisations/creer/', f'/app/baux/{b}/ajustements/creer/',
            '/admin/', '/admin/core/immeuble/', '/admin/core/bail/',
            '/admin/core/regularisation/', '/admin/core/creditimmobilier/',
            '/admin/core/bailtarification/', '/admin/core/vacancelocative/',
            '/api/patrimoine/dashboard/', f'/api/patrimoine/immeuble/{i}/',
            f'/api/fiscal/immeuble/{i}/', f'/api/quittance/{b}/',
            f'/api/avis_echeance/{b}/', f'/api/regularisation/{b}/',
            f'/api/solde_tout_compte/{b}/',
        ]
        urls += [f'/app/immeubles/{i}/tab/{t}/'
                 for t in ('general', 'locaux', 'finances', 'estimations', 'consommations')]
        urls += [f'/app/baux/{b}/tab/{t}/'
                 for t in ('info', 'occupants', 'regularisations', 'documents')]
        return urls

    def test_toutes_les_pages_repondent(self):
        echecs = []
        for url in self._urls():
            try:
                reponse = self.client.get(url)
                if reponse.status_code >= 400:
                    echecs.append(f"{url} -> HTTP {reponse.status_code}")
            except Exception as erreur:
                echecs.append(f"{url} -> {type(erreur).__name__}: {erreur}")
        self.assertEqual(echecs, [], "Pages en erreur :\n" + "\n".join(echecs))

    def test_assistant_credit_refuse_une_duree_nulle(self):
        """E-01 : aucun credit orphelin ne doit rester en base."""
        avant = CreditImmobilier.objects.count()
        self.client.post(f'/app/immeubles/{self.immeuble.pk}/credits/creer/', {
            'nom_banque': 'Test', 'date_debut': '2024-01-01', 'type_credit': 'AMORTISSABLE',
            'capital_emprunte': '100000', 'taux_interet': '2', 'duree_mois': '0',
            'assurance_mensuelle': '0',
        })
        self.assertEqual(CreditImmobilier.objects.count(), avant)

    def test_assistant_credit_genere_l_echeancier(self):
        self.client.post(f'/app/immeubles/{self.immeuble.pk}/credits/creer/', {
            'nom_banque': 'Nouvelle banque', 'date_debut': '2024-01-01',
            'type_credit': 'AMORTISSABLE', 'capital_emprunte': '50000',
            'taux_interet': '1.5', 'duree_mois': '120', 'assurance_mensuelle': '10',
        })
        credit = CreditImmobilier.objects.get(nom_banque='Nouvelle banque')
        self.assertEqual(credit.echeances.count(), 120)
