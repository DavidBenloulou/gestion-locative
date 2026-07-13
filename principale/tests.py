import decimal
from datetime import date

from django.test import TestCase

from .models import SCI, Bien, Locataire, LocationBien, RevisionLoyer
from .views import get_loyer_charges_effectifs


class GetLoyerChargesEffectifsTests(TestCase):
    def setUp(self):
        self.sci = SCI.objects.create(
            nom="SCI Test", adresse="1 rue Test", code_postal="80000", ville="Amiens",
            representants="Test", titre_representants="Gérant"
        )
        self.bien = Bien.objects.create(
            sci=self.sci, type_bien='LOGEMENT', adresse="1 rue du bien",
            code_postal="80000", ville="Amiens", loyer_mensuel=decimal.Decimal('500'),
            montant_charges=decimal.Decimal('50'),
        )
        self.locataire = Locataire.objects.create(nom="Dupont", prenom="Jean", sci=self.sci)
        self.location = LocationBien.objects.create(
            locataire=self.locataire, bien=self.bien, date_entree=date(2025, 1, 1)
        )

    def test_sans_revision_utilise_le_bien(self):
        loyer, charges = get_loyer_charges_effectifs(self.location, self.bien, 2025, 6)
        self.assertEqual(loyer, decimal.Decimal('500'))
        self.assertEqual(charges, decimal.Decimal('50'))

    def test_revision_passee_s_applique(self):
        RevisionLoyer.objects.create(
            location=self.location, date_effet=date(2026, 3, 1),
            nouveau_loyer=decimal.Decimal('550'), nouvelles_charges=decimal.Decimal('60'),
        )
        loyer, charges = get_loyer_charges_effectifs(self.location, self.bien, 2026, 6)
        self.assertEqual(loyer, decimal.Decimal('550'))
        self.assertEqual(charges, decimal.Decimal('60'))

        # Avant la date d'effet, l'ancien montant s'applique toujours
        loyer_avant, charges_avant = get_loyer_charges_effectifs(self.location, self.bien, 2026, 2)
        self.assertEqual(loyer_avant, decimal.Decimal('500'))
        self.assertEqual(charges_avant, decimal.Decimal('50'))

    def test_plusieurs_revisions_la_plus_recente_applicable_gagne(self):
        RevisionLoyer.objects.create(
            location=self.location, date_effet=date(2026, 3, 1),
            nouveau_loyer=decimal.Decimal('550'), nouvelles_charges=decimal.Decimal('60'),
        )
        RevisionLoyer.objects.create(
            location=self.location, date_effet=date(2027, 3, 1),
            nouveau_loyer=decimal.Decimal('600'), nouvelles_charges=decimal.Decimal('70'),
        )
        loyer_2026, _ = get_loyer_charges_effectifs(self.location, self.bien, 2026, 12)
        loyer_2027, _ = get_loyer_charges_effectifs(self.location, self.bien, 2027, 6)
        self.assertEqual(loyer_2026, decimal.Decimal('550'))
        self.assertEqual(loyer_2027, decimal.Decimal('600'))

    def test_mois_arrivee_avec_prorata_est_prioritaire(self):
        location = LocationBien.objects.create(
            locataire=self.locataire,
            bien=Bien.objects.create(
                sci=self.sci, type_bien='LOGEMENT', adresse="2 rue du bien",
                code_postal="80000", ville="Amiens", loyer_mensuel=decimal.Decimal('500'),
                montant_charges=decimal.Decimal('50'),
            ),
            date_entree=date(2025, 6, 15),
            montant_loyer_premier_mois=decimal.Decimal('250'),
            montant_charges_premier_mois=decimal.Decimal('25'),
        )
        RevisionLoyer.objects.create(
            location=location, date_effet=date(2025, 1, 1),
            nouveau_loyer=decimal.Decimal('999'), nouvelles_charges=decimal.Decimal('99'),
        )
        loyer, charges = get_loyer_charges_effectifs(location, location.bien, 2025, 6)
        self.assertEqual(loyer, decimal.Decimal('250'))
        self.assertEqual(charges, decimal.Decimal('25'))
