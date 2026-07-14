"""Logique de calcul partagée entre views.py et forms.py.

Isolée dans ce module (plutôt que dans views.py) pour que forms.py puisse
l'importer sans créer de dépendance circulaire (views.py importe forms.py).
"""
import decimal
from datetime import date

from django.db.models import Sum

from .models import Transaction, LocationBien, MontantOM, Locataire

# ID du type de transaction "RECETTE - Dépôt de garantie" (caution versée).
# Voir CLAUDE.md §9. Les transactions de caution n'ont pas de mois_concerne.
TYPE_DEPOT_GARANTIE = 18
# ID du type de transaction "DEPENSE - Rbt Dépôt garantie" (caution remboursée).
TYPE_REMBOURSEMENT_CAUTION = 19


def get_loyer_charges_bien(location, bien, annee, mois, revisions=None):
    """Loyer/charges (Decimal) applicables pour (annee, mois), en tenant compte des
    révisions de loyer (RevisionLoyer) de la location, sinon les valeurs du bien.
    Ne tient PAS compte du prorata du premier mois (voir get_loyer_charges_effectifs).
    `revisions` peut être fourni pré-chargée (ex. via prefetch_related) pour éviter une requête."""
    premier_jour_mois = date(annee, mois, 1)
    if revisions is None:
        revisions = list(location.revisions_loyer.all())

    revision_applicable = None
    for r in revisions:
        r_mois = r.date_effet.replace(day=1)
        if r_mois <= premier_jour_mois and (revision_applicable is None or r_mois > revision_applicable.date_effet.replace(day=1)):
            revision_applicable = r

    if revision_applicable:
        loyer = decimal.Decimal(str(revision_applicable.nouveau_loyer))
        charges = decimal.Decimal(str(revision_applicable.nouvelles_charges)) if revision_applicable.nouvelles_charges is not None else decimal.Decimal('0')
        return loyer, charges

    loyer = decimal.Decimal(str(bien.loyer_mensuel or 0))
    charges = decimal.Decimal(str(bien.montant_charges)) if bien.montant_charges is not None else decimal.Decimal('0')
    return loyer, charges


def get_loyer_charges_effectifs(location, bien, annee, mois, revisions=None):
    """Loyer/charges (Decimal) applicables pour (annee, mois) : priorité au prorata du
    premier mois si c'est le mois d'arrivée, sinon get_loyer_charges_bien (révisions/bien)."""
    if (location.date_entree and annee == location.date_entree.year
            and mois == location.date_entree.month
            and location.montant_loyer_premier_mois is not None):
        loyer = decimal.Decimal(str(location.montant_loyer_premier_mois))
        charges = decimal.Decimal(str(location.montant_charges_premier_mois)) if location.montant_charges_premier_mois is not None else decimal.Decimal('0')
        return loyer, charges

    return get_loyer_charges_bien(location, bien, annee, mois, revisions=revisions)


def _calculer_releve(locataire, current_sci):
    """
    Calcule le relevé de compte mensuel d'un locataire depuis son entrée.
    Retourne une liste de dicts par (bien, liste de lignes mensuelles).
    Chaque ligne possède un champ 'type' : 'loyer', 'caution' ou 'om'.
    """
    noms_mois_fr = {
        1: 'Janvier', 2: 'Février', 3: 'Mars', 4: 'Avril', 5: 'Mai', 6: 'Juin',
        7: 'Juillet', 8: 'Août', 9: 'Septembre', 10: 'Octobre', 11: 'Novembre', 12: 'Décembre'
    }
    date_debut_logiciel = date(2025, 1, 1)
    date_aujourd_hui = date.today()

    # Transactions RECETTE mensuelles (hors caution/OM) du locataire pour la SCI
    transactions = list(Transaction.objects.filter(
        sci=current_sci,
        locataire=locataire,
        type_transaction__categorie='RECETTE',
        mois_concerne__isnull=False,
    ).select_related('type_transaction', 'bien'))

    # Indexer par (bien_id, annee, mois)
    trans_idx = {}
    for t in transactions:
        cle = (t.bien_id, t.mois_concerne.year, t.mois_concerne.month)
        if cle not in trans_idx:
            trans_idx[cle] = []
        trans_idx[cle].append(t)

    # Caution versée par bien
    caution_par_bien = {}
    for row in Transaction.objects.filter(
        sci=current_sci,
        locataire=locataire,
        type_transaction__id=TYPE_DEPOT_GARANTIE,
    ).values('bien_id').annotate(total=Sum('montant')):
        caution_par_bien[row['bien_id']] = decimal.Decimal(str(row['total']))

    # OM payés par (bien_id, annee) — transactions RECETTE avec 'om' dans le nom
    om_paye_par_bien_annee = {}
    for row in Transaction.objects.filter(
        sci=current_sci,
        locataire=locataire,
        type_transaction__categorie='RECETTE',
        type_transaction__nom__icontains='om',
        mois_concerne__isnull=False,
    ).values('bien_id', 'mois_concerne__year').annotate(total=Sum('montant')):
        key = (row['bien_id'], row['mois_concerne__year'])
        om_paye_par_bien_annee[key] = decimal.Decimal(str(row['total']))

    # Montants OM attendus par (bien_id, annee)
    om_attendu_par_bien_annee = {}
    for om in MontantOM.objects.filter(sci=current_sci, locataire=locataire):
        om_attendu_par_bien_annee[(om.bien_id, om.annee)] = decimal.Decimal(str(om.montant_attendu))

    locations = LocationBien.objects.filter(
        locataire=locataire,
        bien__sci=current_sci,
    ).select_related('bien').prefetch_related('revisions_loyer').order_by('date_entree')

    biens_releve = []
    for location in locations:
        bien = location.bien
        if not location.date_entree:
            continue
        date_debut = max(location.date_entree, date_debut_logiciel)
        date_fin = location.date_sortie if location.date_sortie else date_aujourd_hui
        revisions_location = list(location.revisions_loyer.all())

        lignes = []
        solde_cumule = decimal.Decimal('0')

        # Ligne de report de solde antérieur à 2025 (si renseignée)
        if location.solde_report_anterieur is not None and location.solde_report_anterieur != 0:
            report = decimal.Decimal(str(location.solde_report_anterieur))
            solde_cumule += report
            lignes.append({
                'type': 'report_anterieur',
                'mois_label': 'Report antérieur à 2025',
                'loyer_du': decimal.Decimal('0'),
                'charges_dues': decimal.Decimal('0'),
                'loyer_paye': decimal.Decimal('0'),
                'charges_payees': decimal.Decimal('0'),
                'ecart': report,
                'solde_cumule': solde_cumule,
            })

        # Ligne caution (première ligne, toujours affichée)
        # Priorité : bien.montant_caution, puis location.montant_caution en repli
        _caution_ref = bien.montant_caution if bien.montant_caution is not None else location.montant_caution
        montant_caution_attendu = decimal.Decimal(str(_caution_ref)) if _caution_ref is not None else decimal.Decimal('0')
        caution_versee = caution_par_bien.get(bien.id, decimal.Decimal('0'))
        ecart_caution = caution_versee - montant_caution_attendu
        solde_cumule += ecart_caution
        lignes.append({
            'type': 'caution',
            'mois_label': 'Dépôt de garantie',
            'loyer_du': montant_caution_attendu,
            'charges_dues': decimal.Decimal('0'),
            'loyer_paye': caution_versee,
            'charges_payees': decimal.Decimal('0'),
            'ecart': ecart_caution,
            'solde_cumule': solde_cumule,
        })

        d = date_debut
        while d <= date_fin:
            trans_mois = trans_idx.get((bien.id, d.year, d.month), [])
            loyer_paye = decimal.Decimal('0')
            charges_payees = decimal.Decimal('0')
            for t in trans_mois:
                nom = t.type_transaction.nom.lower()
                if 'caution' in nom or 'garantie' in nom or 'om' in nom:
                    continue
                if 'charge' in nom:
                    charges_payees += decimal.Decimal(str(t.montant))
                else:
                    loyer_paye += decimal.Decimal(str(t.montant))

            # Loyer/charges applicables à ce mois précis (prorata premier mois ou révision de loyer)
            loyer_du_mois, charges_dues_mois = get_loyer_charges_effectifs(location, bien, d.year, d.month, revisions=revisions_location)

            du_mois = loyer_du_mois + charges_dues_mois
            paye_mois = loyer_paye + charges_payees
            est_mois_courant = (d.year == date_aujourd_hui.year and d.month == date_aujourd_hui.month)
            if est_mois_courant and paye_mois == 0:
                # Mois en cours non échu : tant qu'aucun paiement n'a été fait, ce n'est
                # pas encore une créance (certains locataires paient en fin de mois).
                ecart = decimal.Decimal('0')
            else:
                ecart = paye_mois - du_mois
            solde_cumule += ecart

            lignes.append({
                'type': 'loyer',
                'mois_label': f"{noms_mois_fr[d.month]} {d.year}",
                'loyer_du': loyer_du_mois,
                'charges_dues': charges_dues_mois,
                'loyer_paye': loyer_paye,
                'charges_payees': charges_payees,
                'ecart': ecart,
                'solde_cumule': solde_cumule,
            })

            # Avancer au mois suivant
            if d.month == 12:
                next_d = date(d.year + 1, 1, 1)
            else:
                next_d = date(d.year, d.month + 1, 1)

            # Ajouter ligne OM après le dernier mois de chaque année dans la période
            annee_terminee = (next_d.year != d.year) or (next_d > date_fin)
            if annee_terminee:
                annee = d.year
                om_attendu = om_attendu_par_bien_annee.get((bien.id, annee))
                om_paye = om_paye_par_bien_annee.get((bien.id, annee), decimal.Decimal('0'))
                if om_attendu is not None or om_paye > 0:
                    ecart_om = om_paye - (om_attendu if om_attendu is not None else decimal.Decimal('0'))
                    solde_cumule += ecart_om
                    lignes.append({
                        'type': 'om',
                        'mois_label': f'Ordures Ménagères {annee}',
                        'loyer_du': om_attendu if om_attendu is not None else decimal.Decimal('0'),
                        'charges_dues': decimal.Decimal('0'),
                        'loyer_paye': om_paye,
                        'charges_payees': decimal.Decimal('0'),
                        'ecart': ecart_om,
                        'solde_cumule': solde_cumule,
                    })

            d = next_d

        biens_releve.append({
            'bien': bien,
            'location': location,
            'lignes': lignes,
            'solde_final': solde_cumule,
        })

    return biens_releve


def location_est_soldee(bloc):
    """Une location fermée est 'soldée' quand elle n'a plus aucune raison de rester
    visible/assignable : solde à 0 ET caution réglée (non due ou restituée), et
    qu'elle n'a pas été rouverte manuellement. Une location active n'est jamais soldée."""
    location = bloc['location']
    if location.date_sortie is None:
        return False
    if location.date_cloture_manuelle is not None:
        return True

    bien = bloc['bien']
    montant_caution_attendu = bien.montant_caution if bien.montant_caution is not None else location.montant_caution
    caution_due = montant_caution_attendu is not None and montant_caution_attendu > 0
    caution_reglee = not caution_due or location.date_restitution_caution is not None

    return bloc['solde_final'] == 0 and caution_reglee


def locations_ouvertes(locataire, current_sci):
    """Renvoie les blocs de _calculer_releve() dont la location est encore 'ouverte' :
    active, ou fermée mais avec un solde résiduel (créance ou trop-perçu) ou une
    caution due non restituée -- sauf si elle a été clôturée manuellement
    (LocationBien.date_cloture_manuelle). Sert à la fois à limiter les biens
    sélectionnables dans le formulaire de transaction et à filtrer l'onglet Créances."""
    return [
        bloc for bloc in _calculer_releve(locataire, current_sci)
        if not location_est_soldee(bloc)
    ]


def locataires_avec_bien_ouvert_ids(current_sci):
    """IDs des locataires ayant au moins un bien 'ouvert' dans cette SCI (une
    location active, ou fermée mais pas encore soldée -- voir locations_ouvertes).
    Un locataire totalement parti et soldé partout ne doit plus être proposé dans
    le formulaire de transaction (plus rien à lui affecter).

    Optimisé : le relevé complet (_calculer_releve, coûteux) n'est recalculé que
    pour les locataires sans aucune location active -- les autres sont
    trivialement 'ouverts' via leur location en cours."""
    ids_actifs = set(
        LocationBien.objects.filter(
            bien__sci=current_sci,
            date_sortie__isnull=True,
        ).values_list('locataire_id', flat=True)
    )

    locataires_sans_location_active = Locataire.objects.filter(
        biens__sci=current_sci
    ).exclude(id__in=ids_actifs).distinct()

    ids_ouverts = set(ids_actifs)
    for locataire in locataires_sans_location_active:
        if locations_ouvertes(locataire, current_sci):
            ids_ouverts.add(locataire.id)

    return ids_ouverts
