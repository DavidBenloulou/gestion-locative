from django.shortcuts import render, get_object_or_404, redirect
from django.db.models import Sum, Q
from django.contrib import messages
from .models import Bien, Locataire, Transaction, ParametresComptables, ParametresSCI, LocationBien, MontantOM
from .forms import BienForm, LocataireForm, TransactionForm, LocationBienForm
from datetime import date, datetime
import calendar
import io
from reportlab.lib.pagesizes import landscape, A4
from reportlab.lib import colors
import decimal
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from django.http import Http404, HttpResponse, JsonResponse
from django.urls import reverse


def dashboard(request):
    """Dashboard optimisé"""
    # Filtrer par SCI active
    total_biens = Bien.objects.filter(sci=request.current_sci).count()

    # Utiliser biens__sci au lieu de biens__sci
    total_locataires = Locataire.objects.filter(
        biens__sci=request.current_sci,
        locations__date_sortie__isnull=True
    ).distinct().count()

    # Récupérer l'année courante
    annee_courante = date.today().year

    # ← OPTIMISATION : Utiliser ExtractYear pour éviter dates()
    from django.db.models.functions import ExtractYear

    annees_disponibles = list(Transaction.objects.filter(
        sci=request.current_sci
    ).annotate(
        annee=ExtractYear('date')
    ).values_list('annee', flat=True).distinct().order_by('-annee'))

    # S'assurer que l'année courante est incluse
    if annee_courante not in annees_disponibles:
        annees_disponibles.insert(0, annee_courante)

    # Résumé financier annuel (ces requêtes sont déjà optimales)
    recettes_annuelles = Transaction.objects.filter(
        sci=request.current_sci,
        type_transaction__categorie='RECETTE',
        date__year=annee_courante
    ).aggregate(total=Sum('montant'))['total'] or 0

    depenses_annuelles = Transaction.objects.filter(
        sci=request.current_sci,
        type_transaction__categorie='DEPENSE',
        date__year=annee_courante
    ).aggregate(total=Sum('montant'))['total'] or 0

    bilan = recettes_annuelles - depenses_annuelles

    context = {
        'total_biens': total_biens,
        'total_locataires': total_locataires,
        'recettes_annuelles': recettes_annuelles,
        'depenses_annuelles': depenses_annuelles,
        'bilan': bilan,
        'annee_courante': annee_courante,
        'annees_disponibles': annees_disponibles,
        'annees_export': list(range(2024, annee_courante + 1)),
    }

    return render(request, 'principale/dashboard.html', context)

def liste_biens(request):
    """Vue pour la liste des biens - OPTIMISÉE"""
    biens = Bien.objects.filter(
        sci=request.current_sci
    ).prefetch_related(
        'locations',
        'locations__locataire'
    ).select_related(
        'sci'
    ).order_by('adresse')

    # Ajouter le locataire actif à chaque bien
    biens_avec_locataires = []
    for bien in biens:
        locataire_actif = None
        for location in bien.locations.all():
            if not location.date_sortie:
                locataire_actif = location.locataire
                break
        biens_avec_locataires.append({
            'bien': bien,
            'locataire_actif': locataire_actif,
        })

    return render(request, 'principale/liste_biens.html', {'biens_list': biens_avec_locataires})

def detail_bien(request, bien_id):
    """Vue pour le détail d'un bien - OPTIMISÉE"""
    bien = get_object_or_404(Bien, id=bien_id, sci=request.current_sci)

    # Locataires actuels
    locataires_actuels = Locataire.objects.filter(
        locations__bien=bien,
        locations__date_sortie__isnull=True
    ).distinct()

    # Locations actives avec infos caution
    locations_actives = LocationBien.objects.filter(
        bien=bien,
        date_sortie__isnull=True
    ).select_related('locataire')

    for location in locations_actives:
        trans_caution = Transaction.objects.filter(
            locataire=location.locataire,
            bien=bien,
            type_transaction_id=18
        ).order_by('date')
        total_verse = sum(t.montant for t in trans_caution)
        nb_versements = trans_caution.count()
        premiere_date = trans_caution.first().date if trans_caution.exists() else None
        location.caution_total_verse = total_verse
        location.caution_nb_versements = nb_versements
        location.caution_premiere_date = premiere_date

    # Créer un dict locataire_id -> location pour accès facile dans le template
    locations_par_locataire = {loc.locataire_id: loc for loc in locations_actives}

    transactions = Transaction.objects.filter(
        bien=bien
    ).select_related(
        'type_transaction',
        'locataire',
        'bien',
        'sci'
    ).order_by('-date')

    context = {
        'bien': bien,
        'locataires_actuels': locataires_actuels,
        'locations_actives': locations_actives,
        'transactions': transactions,
    }
    return render(request, 'principale/detail_biens.html', context)

def ajouter_bien(request):
    """Vue pour ajouter un nouveau bien"""
    if request.method == 'POST':
        form = BienForm(request.POST)
        if form.is_valid():
            bien = form.save(commit=False)
            bien.sci = request.current_sci  # Associer à la SCI active
            bien.save()
            messages.success(request, f"Le bien a été ajouté avec succès.")
            return redirect('detail_bien', bien_id=bien.id)  # Rediriger vers le détail du bien, pas du locataire
    else:
        form = BienForm()

    return render(request, 'principale/formulaire_bien.html', {
        'form': form,
        'titre': 'Ajouter un bien'
    })

def modifier_bien(request, bien_id):
    """Vue pour modifier un bien existant"""
    bien = get_object_or_404(Bien, id=bien_id, sci=request.current_sci)  # Vérifier que le bien appartient à la SCI active

    if request.method == 'POST':
        form = BienForm(request.POST, instance=bien)
        if form.is_valid():
            bien = form.save()
            messages.success(request, f"Le bien a été modifié avec succès.")
            return redirect('detail_bien', bien_id=bien.id)
    else:
        form = BienForm(instance=bien)

    return render(request, 'principale/formulaire_bien.html', {
        'form': form,
        'titre': f'Modifier le bien : {bien.adresse}',
        'bien': bien
    })

def supprimer_bien(request, bien_id):
    """Vue pour supprimer un bien"""
    bien = get_object_or_404(Bien, id=bien_id, sci=request.current_sci)  # Vérifier que le bien appartient à la SCI active

    if request.method == 'POST':
        bien.delete()
        messages.success(request, f"Le bien a été supprimé avec succès.")
        return redirect('liste_biens')

    return render(request, 'principale/confirmer_suppression.html', {
        'objet': bien,
        'type_objet': 'bien',
        'url_retour': 'liste_biens'
    })

def liste_locataires(request):
    """Vue pour la liste des locataires - OPTIMISÉE"""
    locataires = Locataire.objects.filter(
        sci=request.current_sci
    ).prefetch_related(
        'biens',
        'locations',
        'locations__bien'
    ).order_by('nom', 'prenom')

    # Enrichir les locations avec les données de caution
    for locataire in locataires:
        for location in locataire.locations.all():
            trans_caution = Transaction.objects.filter(
                locataire=locataire,
                bien=location.bien,
                type_transaction_id=18
            ).order_by('date')
            total_verse = sum(t.montant for t in trans_caution)
            nb_versements = trans_caution.count()
            premiere_date = trans_caution.first().date if trans_caution.exists() else None
            location.caution_total_verse = total_verse
            location.caution_nb_versements = nb_versements
            location.caution_premiere_date = premiere_date

    return render(request, 'principale/liste_locataires.html', {'locataires': locataires})

def detail_locataire(request, locataire_id):
    """Vue pour le détail d'un locataire - OPTIMISÉE"""

    # ← OPTIMISATION : Précharger le locataire avec ses relations
    try:
        locataire = Locataire.objects.select_related('sci').prefetch_related(
            'biens__sci',
            'locations__bien__sci'
        ).get(id=locataire_id)

        # Vérifier si le locataire appartient à la SCI actuelle
        if locataire.sci and locataire.sci.id == request.current_sci.id:
            pass
        elif locataire.biens.filter(sci=request.current_sci).exists():
            pass
        else:
            raise Http404("Locataire non trouvé dans cette SCI")

    except Locataire.DoesNotExist:
        raise Http404("Locataire non trouvé")

    # ← OPTIMISATION : Précharger les relations
    biens = locataire.biens.select_related('sci').all()

    locations = LocationBien.objects.filter(
        locataire=locataire
    ).select_related('bien__sci')

    transactions = Transaction.objects.filter(
        locataire=locataire
    ).select_related(
        'type_transaction',  # ← OPTIMISATION
        'bien__sci',         # ← OPTIMISATION
        'locataire',         # ← OPTIMISATION
        'sci'                # ← OPTIMISATION
    ).order_by('-date')

    # Préparer les années pour le dropdown de quittance
    annee_courante = date.today().year
    date_entree = locataire.date_entree
    annee_debut = date_entree.year if date_entree else annee_courante
    range_annees = range(annee_debut, annee_courante + 1)
    # Enrichir les locations avec les données de caution
    for location in locations:
        trans_caution = Transaction.objects.filter(
            locataire=locataire,
            bien=location.bien,
            type_transaction_id=18
        ).order_by('date')
        
        total_verse = sum(t.montant for t in trans_caution)
        nb_versements = trans_caution.count()
        premiere_date = trans_caution.first().date if trans_caution.exists() else None
        
        location.caution_total_verse = total_verse
        location.caution_nb_versements = nb_versements
        location.caution_premiere_date = premiere_date

    context = {
        'locataire': locataire,
        'biens': biens,
        'locations': locations,
        'transactions': transactions,
        'range_annees': range_annees,
        'annee_courante': annee_courante,
    }
    return render(request, 'principale/detail_locataire.html', context)

def generer_quittance(request, locataire_id):
    """Vue pour générer une quittance de loyer en PDF avec filtrage précis par bien et par mois concerné"""
    # Récupérer le bien spécifique
    bien_id = request.GET.get('bien_id')

    if not bien_id:
        # Si pas de bien_id et que le locataire a plusieurs biens, afficher la sélection
        locataire = get_object_or_404(Locataire, id=locataire_id, biens__sci=request.current_sci)
        if locataire.biens.count() > 1:
            biens = locataire.biens.filter(sci=request.current_sci)
            return render(request, 'principale/selectionner_bien_quittance.html', {
                'locataire': locataire,
                'biens': biens,
                'annee': request.GET.get('annee'),
                'mois': request.GET.get('mois')
            })
        # Si un seul bien, le prendre par défaut
        bien_id = locataire.biens.first().id

    # Récupérer le locataire ET le bien en une seule requête
    locataire = get_object_or_404(
        Locataire,
        id=locataire_id,
        biens__id=bien_id,  # Filtre sur le bien spécifique
        biens__sci=request.current_sci
    )

    # Récupérer le bien concerné
    bien = get_object_or_404(Bien, id=bien_id, sci=request.current_sci)

    # Récupérer le mois et l'année de la quittance
    try:
        mois = int(request.GET.get('mois', date.today().month))
        annee = int(request.GET.get('annee', date.today().year))
    except ValueError:
        mois = date.today().month
        annee = date.today().year

    # Vérifier que le locataire était bien présent ce mois-là pour ce bien spécifique
    location = LocationBien.objects.filter(
        locataire=locataire,
        bien=bien,
        date_entree__lte=date(annee, mois, calendar.monthrange(annee, mois)[1])  # Dernier jour du mois
    ).first()

    if not location:
        messages.error(request, f"Le locataire n'occupait pas ce bien en {mois}/{annee}.")
        return redirect('detail_locataire', locataire_id=locataire.id)

    if location.date_sortie and location.date_sortie < date(annee, mois, 1):
        messages.error(request, f"Le locataire avait déjà quitté ce logement avant {mois}/{annee}.")
        return redirect('detail_locataire', locataire_id=locataire.id)

    # Récupérer les paiements pour ce bien spécifique et pour le mois concerné

    # 1. Paiements de loyer directs du locataire (sans charges et sans CAF)
    paiements_loyer_locataire = Transaction.objects.filter(
        locataire=locataire,
        bien=bien,  # Filtrer sur le bien spécifique
        type_transaction__categorie='RECETTE',
        mois_concerne__year=annee,
        mois_concerne__month=mois
    ).filter(
        type_transaction__nom__icontains='loyer'
    ).exclude(
        Q(type_transaction__nom__icontains='charge') |
        Q(type_transaction__nom__icontains='caf')
    )

    # 2. Paiements de la CAF pour ce bien
    paiements_caf = Transaction.objects.filter(
        locataire=locataire,
        bien=bien,  # Filtrer sur le bien spécifique
        type_transaction__categorie='RECETTE',
        type_transaction__nom__icontains='caf',
        mois_concerne__year=annee,
        mois_concerne__month=mois
    )

    # 3. Paiements des charges pour ce bien
    paiements_charges = Transaction.objects.filter(
        locataire=locataire,
        bien=bien,  # Filtrer sur le bien spécifique
        type_transaction__categorie='RECETTE',
        mois_concerne__year=annee,
        mois_concerne__month=mois
    ).filter(
        type_transaction__nom__icontains='charge'
    ).exclude(
        type_transaction__nom__icontains='om')

    # Calculer les montants
    montant_loyer_locataire = sum(p.montant for p in paiements_loyer_locataire)
    montant_charges_locataire = sum(p.montant for p in paiements_charges)
    montant_caf = sum(p.montant for p in paiements_caf)

    # Total du paiement du locataire = loyer direct + charges
    montant_paiement_locataire = montant_loyer_locataire + montant_charges_locataire

    # Total général
    montant_total = montant_paiement_locataire + montant_caf

    # Noms des mois en français
    noms_mois_fr = {
        1: 'Janvier', 2: 'Février', 3: 'Mars', 4: 'Avril', 5: 'Mai', 6: 'Juin',
        7: 'Juillet', 8: 'Août', 9: 'Septembre', 10: 'Octobre', 11: 'Novembre', 12: 'Décembre'
    }

    # Utiliser les informations de la SCI active plutôt que les paramètres globaux
    if hasattr(request, 'current_sci') and request.current_sci:
        sci_active = request.current_sci
        ville_sci = sci_active.ville
        nom_sci = sci_active.nom
        representants = sci_active.representants
        titre_representants = sci_active.titre_representants
        adresse_sci = sci_active.adresse
        code_postal_sci = sci_active.code_postal
    else:
        # Fallback sur les paramètres globaux si aucune SCI n'est sélectionnée
        parametres_sci = ParametresSCI.get_instance()
        ville_sci = parametres_sci.ville
        nom_sci = parametres_sci.nom_sci
        representants = parametres_sci.representants
        titre_representants = parametres_sci.titre_representants
        adresse_sci = parametres_sci.adresse
        code_postal_sci = parametres_sci.code_postal

    # Loyer et charges attendus
    loyer_attendu = bien.loyer_mensuel if bien and bien.loyer_mensuel else 0
    charges_attendues = bien.montant_charges if bien and bien.montant_charges is not None else 0

    # Créer le PDF
    buffer = io.BytesIO()

    # Configurer le document PDF avec des marges réduites
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=1*cm,
        rightMargin=1*cm,
        topMargin=1*cm,
        bottomMargin=1*cm
    )

    elements = []

    # Styles pour le PDF
    styles = getSampleStyleSheet()

    # Style pour le titre
    titre_style = ParagraphStyle(
        'TitreQuittance',
        parent=styles['Heading1'],
        fontSize=18,
        alignment=TA_CENTER,
        spaceAfter=0.3*cm,
    )

    # Style pour le sous-titre (mois/année)
    sous_titre_style = ParagraphStyle(
        'SousTitreQuittance',
        parent=styles['Heading2'],
        fontSize=14,
        alignment=TA_CENTER,
        spaceAfter=0.5*cm,
    )

    # Style pour le texte normal
    texte_style = ParagraphStyle(
        'TexteQuittance',
        parent=styles['Normal'],
        fontSize=11,
        leading=14,
    )

    # Style pour le texte en gras
    gras_style = ParagraphStyle(
        'TexteGras',
        parent=texte_style,
        fontName='Helvetica-Bold',
    )

    # Style pour le texte gris
    gris_style = ParagraphStyle(
        'TexteGris',
        parent=texte_style,
        textColor=colors.gray,
    )

    # Style pour les données
    donnee_style = ParagraphStyle(
        'DonneeQuittance',
        parent=texte_style,
        fontName='Helvetica-Bold',
        leftIndent=0.5*cm,
    )

    # Créer les en-têtes avec des tableaux
    # Table pour le bailleur
    bailleur_data = [
        [Paragraph("<b>Bailleur</b>", texte_style)],
        [Paragraph(f"{nom_sci}<br/>{representants}<br/>{adresse_sci}, {code_postal_sci} {ville_sci}", texte_style)]
    ]

    bailleur_table = Table(bailleur_data, colWidths=[doc.width/2 - 0.5*cm])
    bailleur_table.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 0.5, colors.black),
        ('BACKGROUND', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 1), (-1, 1), 6),
        ('BOTTOMPADDING', (0, 1), (-1, 1), 6),
    ]))

    # Table pour le locataire
    locataire_data = [
        [Paragraph("<b>Locataire Destinataire</b>", texte_style)],
        [Paragraph(f"{locataire.nom} {locataire.prenom}<br/>{bien.adresse}, {bien.code_postal} {bien.ville}", texte_style)]
    ]

    locataire_table = Table(locataire_data, colWidths=[doc.width/2 - 0.5*cm])
    locataire_table.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 0.5, colors.black),
        ('BACKGROUND', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 1), (-1, 1), 6),
        ('BOTTOMPADDING', (0, 1), (-1, 1), 6),
    ]))

    # Table pour l'en-tête complet
    entete_data = [[bailleur_table, ""]]
    entete_table = Table(entete_data, colWidths=[doc.width/2, doc.width/2])
    elements.append(entete_table)

    # Espacer les deux tables
    elements.append(Spacer(1, 0.5*cm))

    # Table pour l'en-tête côté locataire
    entete_locataire_data = [["", locataire_table]]
    entete_locataire_table = Table(entete_locataire_data, colWidths=[doc.width/2, doc.width/2])
    elements.append(entete_locataire_table)

    # Titre du document
    elements.append(Spacer(1, 1*cm))
    titre = Paragraph("Quittance de loyer", titre_style)
    elements.append(titre)

    # Sous-titre avec mois et année
    sous_titre = Paragraph(f"{noms_mois_fr[mois]} {annee}", sous_titre_style)
    elements.append(sous_titre)

    # Préparation du détail des paiements (placé juste après "La somme de")
    detail_paiements = ""
    if montant_caf > 0 or montant_paiement_locataire > 0:
        detail_paiements = (
            f"<br/><b>Détail des paiements</b><br/>"
            f"- Paiement locataire : {montant_paiement_locataire:.2f} €<br/>"
        )
        if montant_caf > 0:
            detail_paiements += f"- Paiement CAF : {montant_caf:.2f} €<br/>"

    # Créer un conteneur pour les détails de la quittance avec bordure grise
    contenu_data = [[
        Paragraph(
            f"<b>Reçu de :</b> {locataire.nom} {locataire.prenom}<br/><br/>"
            f"<b>La somme de :</b> {montant_total:.2f} €<br/>{detail_paiements}<br/>"
            f"<b>Pour le bien :</b><br/>"
            f"{bien.numero or ''} / {bien.adresse}, {bien.code_postal} {bien.ville}<br/><br/>"
            f"<b>Rappel des montants attendus :</b><br/>"
            f"- Loyer nu : {loyer_attendu:.2f} €<br/>"
            f"- Charges / Provisions de Charges : {charges_attendues:.2f} €<br/><br/>"
            f"<b>Montant total attendu : {loyer_attendu + charges_attendues:.2f} €</b>",
            texte_style
        )
    ]]

    contenu_table = Table(contenu_data, colWidths=[doc.width - 1*cm])
    contenu_table.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 0.5, colors.grey),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
        ('LEFTPADDING', (0, 0), (-1, 0), 10),
        ('RIGHTPADDING', (0, 0), (-1, 0), 10),
    ]))

    elements.append(contenu_table)

    # Table pour la signature
    elements.append(Spacer(1, 1*cm))
    signature_data = [
        [Paragraph(f"Fait à {ville_sci}", texte_style), Paragraph(f"le {date.today().strftime('%d/%m/%Y')}", texte_style)],
        [Paragraph("<br/><br/><br/>", texte_style), ""]
    ]

    signature_table = Table(signature_data, colWidths=[doc.width/2 - 0.5*cm, doc.width/2 - 0.5*cm])
    signature_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (0, 0), 'LEFT'),
        ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))

    elements.append(signature_table)

    # Générer le PDF
    doc.build(elements)

    # Configurer la réponse
    buffer.seek(0)
    response = HttpResponse(buffer, content_type='application/pdf')
    nom_fichier = f"quittance_{locataire.nom}_{noms_mois_fr[mois]}_{annee}.pdf"
    response['Content-Disposition'] = f'attachment; filename="{nom_fichier}"'

    return response

def ajouter_locataire(request):
    """Vue pour ajouter un nouveau locataire"""
    if request.method == 'POST':
        form = LocataireForm(request.POST, sci=request.current_sci)
        if form.is_valid():
            locataire = form.save(commit=False)
            locataire.sci = request.current_sci  # Associer à la SCI courante
            locataire.save()
            messages.success(request, f"Le locataire {locataire.nom} {locataire.prenom} a été ajouté avec succès.")
            return redirect('detail_locataire', locataire_id=locataire.id)
    else:
        form = LocataireForm(sci=request.current_sci)

    return render(request, 'principale/formulaire_locataire.html', {
        'form': form,
        'titre': 'Ajouter un locataire'
    })

def modifier_locataire(request, locataire_id):
    # D'abord, chercher le locataire par ID
    try:
        locataire = Locataire.objects.get(id=locataire_id)

        # Vérifier si le locataire appartient à la SCI actuelle
        if locataire.sci and locataire.sci.id == request.current_sci.id:
            # Le locataire appartient à la SCI actuelle via le champ sci
            pass
        elif locataire.biens.filter(sci=request.current_sci).exists():
            # Le locataire a au moins un bien dans la SCI actuelle
            pass
        else:
            # Le locataire n'appartient pas à la SCI actuelle
            raise Http404("Locataire non trouvé dans cette SCI")

    except Locataire.DoesNotExist:
        raise Http404("Locataire non trouvé")

    if request.method == 'POST':
        form = LocataireForm(request.POST, instance=locataire)

        if form.is_valid():
            locataire = form.save()
            messages.success(request, f"Le locataire {locataire.nom} {locataire.prenom} a été modifié avec succès.")
            return redirect('detail_locataire', locataire_id=locataire.id)
    else:
        form = LocataireForm(instance=locataire)

    return render(request, 'principale/formulaire_locataire.html', {
        'form': form,
        'titre': f'Modifier le locataire : {locataire.nom} {locataire.prenom}',
        'locataire': locataire
    })

def supprimer_locataire(request, locataire_id):
    """Vue pour supprimer un locataire"""
    # D'abord chercher par l'ID et la SCI directe
    locataire = Locataire.objects.filter(id=locataire_id, sci=request.current_sci).first()

    # Si non trouvé, chercher par les biens associés
    if not locataire:
        locataire = Locataire.objects.filter(
            id=locataire_id,
            biens__sci=request.current_sci
        ).distinct().first()

    if not locataire:
        raise Http404("Locataire non trouvé")

    if request.method == 'POST':
        locataire.delete()
        messages.success(request, f"Le locataire a été supprimé avec succès.")
        return redirect('liste_locataires')

    return render(request, 'principale/confirmer_suppression.html', {
        'objet': locataire,
        'type_objet': 'locataire',
        'url_retour': 'liste_locataires'
    })

def liste_transactions(request):
    # Récupérer les paramètres de filtrage
    categorie = request.GET.get('categorie')
    type_id = request.GET.get('type_transaction')
    locataire_id = request.GET.get('locataire')
    date_debut = request.GET.get('date_debut')
    date_fin = request.GET.get('date_fin')
    sci_only = request.GET.get('sci') == 'true'

    # Requête de base avec TOUS les select_related nécessaires
    transactions = Transaction.objects.filter(
        sci=request.current_sci
    ).select_related(
        'type_transaction',
        'bien',
        'locataire',
        'sci'
    )

    # Appliquer les filtres
    if categorie:
        transactions = transactions.filter(type_transaction__categorie=categorie)
    if type_id:
        transactions = transactions.filter(type_transaction_id=type_id)
    if locataire_id:
        transactions = transactions.filter(locataire_id=locataire_id)
    if date_debut:
        transactions = transactions.filter(date__gte=date_debut)
    if date_fin:
        transactions = transactions.filter(date__lte=date_fin)
    if sci_only:
        transactions = transactions.filter(locataire__isnull=True, bien__isnull=True)

    # Trier par date décroissante
    transactions = transactions.order_by('-date')

    # Calculer les totaux AVANT la pagination
    recettes = transactions.filter(
        type_transaction__categorie='RECETTE'
    ).aggregate(total=Sum('montant'))['total'] or 0

    depenses = transactions.filter(
        type_transaction__categorie='DEPENSE'
    ).aggregate(total=Sum('montant'))['total'] or 0

    bilan = recettes - depenses

    # Pagination
    from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger

    paginator = Paginator(transactions, 50)
    page_number = request.GET.get('page', 1)

    try:
        transactions_page = paginator.get_page(page_number)
    except PageNotAnInteger:
        transactions_page = paginator.get_page(1)
    except EmptyPage:
        transactions_page = paginator.get_page(paginator.num_pages)

    # Années disponibles
    from django.db.models.functions import ExtractYear
    annees_disponibles = list(Transaction.objects.filter(
        sci=request.current_sci
    ).annotate(
        annee=ExtractYear('date')
    ).values_list('annee', flat=True).distinct().order_by('-annee'))

    # Liste des types de transaction disponibles pour le filtre
    from .models import TypeTransaction
    types_transaction = TypeTransaction.objects.all().order_by('categorie', 'nom')

    # Liste des locataires actifs pour le filtre
    locataires_filtre = Locataire.objects.filter(
        biens__sci=request.current_sci
    ).distinct().order_by('nom', 'prenom')

    query_params = request.GET.copy()
    query_params.pop('page', None)
    context = {
        'transactions': transactions_page,
        'recettes': recettes,
        'depenses': depenses,
        'bilan': bilan,
        'annees_disponibles': annees_disponibles,
        'annee_courante': date.today().year,
        'types_transaction': types_transaction,
        'locataires_filtre': locataires_filtre,
        'filtre_categorie': categorie or '',
        'filtre_type_id': type_id or '',
        'filtre_locataire_id': locataire_id or '',
        'filtre_date_debut': date_debut or '',
        'filtre_date_fin': date_fin or '',
        'filtre_sci_only': sci_only,
        'query_params': query_params.urlencode(),
    }
    return render(request, 'principale/liste_transactions.html', context)

def ajouter_transaction(request):
    """Vue pour ajouter une nouvelle transaction - VERSION OPTIMISÉE"""

    # Récupérer la SCI courante du middleware
    current_sci = getattr(request, 'current_sci', None)

    # Vérifier que la SCI courante existe
    if not current_sci:
        messages.error(request, "Aucune SCI n'est sélectionnée.")
        return redirect('dashboard')

    # Précharger le locataire si fourni dans l'URL
    locataire_id = request.GET.get('locataire')

    # Définir initial_data
    initial_data = {
        'date': date.today(),
        'mois_concerne': date.today(),
        'sci_transaction': False
    }

    if locataire_id:
        try:
            locataire = Locataire.objects.filter(
                id=locataire_id,
                biens__sci=current_sci
            ).first()
            if locataire:
                initial_data['locataire'] = locataire
        except Exception as e:
            messages.warning(request, f"Erreur lors de la récupération du locataire: {str(e)}")

    if request.method == 'POST':
        # Gérer explicitement le champ sci_transaction
        post_data = request.POST.copy()
        sci_transaction = 'sci_transaction' in request.POST
        post_data['sci_transaction'] = 'on' if sci_transaction else ''

        form = TransactionForm(
            post_data,
            current_sci=current_sci,
            initial=initial_data
        )

        if form.is_valid():
            try:
                # ✅ UTILISER L'ORM DJANGO au lieu de SQL brut
                transaction = form.save(commit=False)
                transaction.sci = current_sci

                # Logique métier pour déterminer le bien et le locataire
                cleaned_data = form.cleaned_data
                is_sci_transaction = cleaned_data.get('sci_transaction', False)
                type_transaction_nom = transaction.type_transaction.nom.lower()

                if is_sci_transaction:
                    transaction.locataire = None
                    transaction.bien = None
                elif 'travaux' in type_transaction_nom:
                    # Le bien et le locataire sont déjà définis par le formulaire
                    pass
                else:
                    # Pour les transactions locataire normales
                    if transaction.locataire:
                        bien_specifique = cleaned_data.get('bien_specifique')
                        if bien_specifique:
                            transaction.bien = bien_specifique
                        elif transaction.locataire.biens.exists():
                            transaction.bien = transaction.locataire.biens.first()

                # Sauvegarder la transaction (1 seule requête SQL optimisée)
                transaction.save()

                # Traitement spécial pour les transactions de type caution
                if transaction.locataire and transaction.bien:
                    type_transaction_categorie = transaction.type_transaction.categorie

                    # Si c'est une caution versée
                    if (('caution' in type_transaction_nom or
                         'dépôt de garantie' in type_transaction_nom or
                         'depot de garantie' in type_transaction_nom) and
                        type_transaction_categorie == 'RECETTE'):

                        location = LocationBien.objects.filter(
                            locataire=transaction.locataire,
                            bien=transaction.bien,
                            date_sortie__isnull=True
                        ).first()

                        if location:
                            location.date_versement_caution = transaction.date
                            location.save()
                            messages.info(request, "Les informations de caution ont été automatiquement mises à jour.")

                    # Si c'est un remboursement de caution
                    elif (('remboursement' in type_transaction_nom or
                          'rbt' in type_transaction_nom or
                          'restitution' in type_transaction_nom) and
                          ('caution' in type_transaction_nom or
                           'garantie' in type_transaction_nom) and
                          type_transaction_categorie == 'DEPENSE'):

                        location = LocationBien.objects.filter(
                            locataire=transaction.locataire,
                            bien=transaction.bien
                        ).first()

                        if location:
                            location.date_restitution_caution = transaction.date
                            location.save()
                            messages.info(request, "La date de restitution de caution a été automatiquement mise à jour.")

                messages.success(request, "La transaction a été ajoutée avec succès.")
                return redirect('liste_transactions')

            except Exception as e:
                import traceback
                print("Erreur détaillée :")
                print(traceback.format_exc())
                messages.error(request, f"Erreur lors de l'ajout de la transaction: {str(e)}")

                return render(request, 'principale/formulaire_transaction.html', {
                    'form': form,
                    'titre': 'Ajouter une transaction'
                })
    else:
        form = TransactionForm(
            current_sci=current_sci,
            initial=initial_data
        )

    return render(request, 'principale/formulaire_transaction.html', {
        'form': form,
        'titre': 'Ajouter une transaction'
    })

def modifier_transaction(request, transaction_id):
    """Vue pour modifier une transaction existante - VERSION OPTIMISÉE"""

    # Récupérer la transaction
    transaction = get_object_or_404(Transaction, id=transaction_id, sci=request.current_sci)

    if request.method == 'POST':
        # Gérer le champ sci_transaction explicitement
        post_data = request.POST.copy()
        sci_transaction = 'sci_transaction' in request.POST
        post_data['sci_transaction'] = 'on' if sci_transaction else ''

        form = TransactionForm(post_data, instance=transaction, current_sci=request.current_sci)

        if form.is_valid():
            try:
                # ✅ UTILISER L'ORM DJANGO au lieu de SQL brut
                transaction = form.save(commit=False)

                # Logique métier
                cleaned_data = form.cleaned_data
                type_transaction_nom = transaction.type_transaction.nom.lower()

                if cleaned_data.get('sci_transaction'):
                    transaction.locataire = None
                    transaction.bien = None
                elif 'travaux' in type_transaction_nom:
                    # Le bien est déjà défini par le formulaire
                    pass
                else:
                    if transaction.locataire:
                        bien_specifique = cleaned_data.get('bien_specifique')
                        if bien_specifique:
                            transaction.bien = bien_specifique
                        elif transaction.locataire.biens.exists():
                            transaction.bien = transaction.locataire.biens.first()

                # Sauvegarder (1 seule requête SQL optimisée)
                transaction.save()

                # Traitement spécial pour les cautions
                if transaction.locataire and transaction.bien:
                    type_transaction_categorie = transaction.type_transaction.categorie

                    if (('caution' in type_transaction_nom or
                         'dépôt de garantie' in type_transaction_nom or
                         'depot de garantie' in type_transaction_nom) and
                        type_transaction_categorie == 'RECETTE'):

                        location = LocationBien.objects.filter(
                            locataire=transaction.locataire,
                            bien=transaction.bien,
                            date_sortie__isnull=True
                        ).first()

                        if location:
                            location.date_versement_caution = transaction.date
                            location.save()
                            messages.info(request, "Les informations de caution ont été automatiquement mises à jour.")

                    elif (('remboursement' in type_transaction_nom or
                          'rbt' in type_transaction_nom or
                          'restitution' in type_transaction_nom) and
                          ('caution' in type_transaction_nom or
                           'garantie' in type_transaction_nom) and
                          type_transaction_categorie == 'DEPENSE'):

                        location = LocationBien.objects.filter(
                            locataire=transaction.locataire,
                            bien=transaction.bien
                        ).first()

                        if location:
                            location.date_restitution_caution = transaction.date
                            location.save()
                            messages.info(request, "La date de restitution de caution a été automatiquement mise à jour.")

                messages.success(request, "La transaction a été modifiée avec succès.")
                return redirect('liste_transactions')

            except Exception as e:
                import traceback
                print(traceback.format_exc())
                messages.error(request, f"Erreur lors de la modification de la transaction: {str(e)}")
    else:
        # Déterminer si c'est une transaction SCI
        initial_data = {'sci_transaction': transaction.locataire is None and transaction.bien is None}

        # Pour les transactions de travaux avec un bien
        if transaction.bien and transaction.type_transaction and 'travaux' in transaction.type_transaction.nom.lower():
            initial_data['bien'] = transaction.bien

        form = TransactionForm(
            instance=transaction,
            current_sci=request.current_sci,
            initial=initial_data
        )

    return render(request, 'principale/formulaire_transaction.html', {
        'form': form,
        'titre': f'Modifier la transaction du {transaction.date}',
        'transaction': transaction
    })

def supprimer_transaction(request, transaction_id):
    """Vue pour supprimer une transaction"""
    transaction = get_object_or_404(Transaction, id=transaction_id, sci=request.current_sci)  # Vérifier que la transaction appartient à la SCI active

    # Stocker l'URL de retour
    referer = request.META.get('HTTP_REFERER', None)

    if request.method == 'POST':
        # Avant de supprimer, vérifier s'il s'agit d'une transaction de caution
        # et stocker les informations pertinentes
        type_transaction_obj = transaction.type_transaction
        type_transaction_nom = type_transaction_obj.nom.lower() if type_transaction_obj else ""
        type_transaction_categorie = type_transaction_obj.categorie if type_transaction_obj else ""

        locataire_id = transaction.locataire_id if transaction.locataire else None
        bien_id = transaction.bien_id if transaction.bien else None

        # Vérifier si c'est une transaction de caution
        est_caution_versee = (('caution' in type_transaction_nom or
                              'dépôt de garantie' in type_transaction_nom or
                              'depot de garantie' in type_transaction_nom) and
                              type_transaction_categorie == 'RECETTE')

        est_caution_remboursee = ((('remboursement' in type_transaction_nom or
                                   'rbt' in type_transaction_nom or
                                   'restitution' in type_transaction_nom) and
                                  ('caution' in type_transaction_nom or
                                   'garantie' in type_transaction_nom)) and
                                 type_transaction_categorie == 'DEPENSE')

        # Supprimer la transaction
        transaction.delete()
        messages.success(request, "La transaction a été supprimée avec succès.")

        # Mise à jour de la relation LocationBien correspondante si nécessaire
        if locataire_id and bien_id:
            if est_caution_versee:
                # Chercher la location active
                location = LocationBien.objects.filter(
                    locataire_id=locataire_id,
                    bien_id=bien_id,
                    date_sortie__isnull=True
                ).first()

                if location:
                    # Réinitialiser les informations de versement de caution
                    location.montant_caution = None
                    location.date_versement_caution = None
                    location.save()
                    messages.info(request, "Les informations de versement de caution ont été réinitialisées.")

            elif est_caution_remboursee:
                # Chercher la location (active ou non)
                location = LocationBien.objects.filter(
                    locataire_id=locataire_id,
                    bien_id=bien_id
                ).first()

                if location:
                    # Réinitialiser la date de restitution
                    location.date_restitution_caution = None
                    location.save()
                    messages.info(request, "La date de restitution de caution a été réinitialisée.")

        # Déterminer l'URL de redirection
        if referer and 'detail_locataire' in referer and transaction.locataire:
            return redirect('detail_locataire', locataire_id=transaction.locataire.id)
        elif referer and 'detail_bien' in referer and transaction.bien:
            return redirect('detail_bien', bien_id=transaction.bien.id)
        else:
            return redirect('liste_transactions')

    return render(request, 'principale/confirmer_suppression.html', {
        'objet': transaction,
        'type_objet': 'transaction',
        'url_retour': 'liste_transactions'
    })

def detail_transaction(request, transaction_id):
    """Vue pour afficher le détail d'une transaction"""
    transaction = get_object_or_404(Transaction, id=transaction_id, sci=request.current_sci)  # Vérifier que la transaction appartient à la SCI active

    context = {
        'transaction': transaction,
    }

    return render(request, 'principale/detail_transaction.html', context)

def etat_paiements(request):
    """Vue pour afficher l'état des paiements des locataires"""
    locataires = Locataire.objects.filter(
        biens__sci=request.current_sci,
        locations__date_sortie__isnull=True
    ).distinct().order_by('nom', 'prenom')

    date_aujourd_hui = date.today()
    date_courante = datetime.now().date()
    mois_courant = date_courante.month
    annee_courante = date_courante.year

    premier_jour_mois_courant = date(annee_courante, mois_courant, 1)
    dernier_jour_mois_courant = date(
        annee_courante,
        mois_courant,
        calendar.monthrange(annee_courante, mois_courant)[1]
    )

    noms_mois_fr = {
        1: 'Janvier', 2: 'Février', 3: 'Mars', 4: 'Avril', 5: 'Mai', 6: 'Juin',
        7: 'Juillet', 8: 'Août', 9: 'Septembre', 10: 'Octobre', 11: 'Novembre', 12: 'Décembre'
    }

    noms_mois_fr_court = {
        1: 'Jan', 2: 'Fév', 3: 'Mar', 4: 'Avr', 5: 'Mai', 6: 'Juin',
        7: 'Juil', 8: 'Août', 9: 'Sep', 10: 'Oct', 11: 'Nov', 12: 'Déc'
    }

    locataires_count = {}

    for locataire in locataires:
        biens_actifs = LocationBien.objects.filter(
            locataire=locataire,
            bien__sci=request.current_sci,
            date_sortie__isnull=True
        ).count()
        locataires_count[locataire.id] = max(1, biens_actifs)

    tableau_paiements = []

    for locataire in locataires:
        biens_locataire = locataire.biens.filter(sci=request.current_sci)

        if not biens_locataire.exists():
            continue

        premier_bien = True

        for bien in biens_locataire:
            location = LocationBien.objects.filter(
                locataire=locataire,
                bien=bien,
                date_sortie__isnull=True
            ).first()

            if not location:
                continue

            montant_caution_attendu = bien.montant_caution
            total_caution_verse = Transaction.objects.filter(
                locataire=locataire,
                bien=bien,
                type_transaction_id=18
            ).aggregate(total=Sum('montant'))['total'] or 0

            nb_transactions_caution = Transaction.objects.filter(
                locataire=locataire,
                bien=bien,
                type_transaction_id=18
            ).count()

            if montant_caution_attendu is None:
                depot_garantie_status = "Non renseigné"
            elif montant_caution_attendu == 0:
                depot_garantie_status = "N/A"
            elif total_caution_verse >= montant_caution_attendu:
                depot_garantie_status = "OK"
            elif total_caution_verse > 0:
                depot_garantie_status = f"Partiel ({total_caution_verse}€ / {montant_caution_attendu}€)"
            else:
                depot_garantie_status = "Manquant"

            if location.date_entree and location.date_entree <= dernier_jour_mois_courant:
                paiements_loyer = Transaction.objects.filter(
                    locataire=locataire,
                    bien=bien,
                    type_transaction__categorie='RECETTE',
                    mois_concerne__year=annee_courante,
                    mois_concerne__month=mois_courant
                ).filter(
                    Q(type_transaction__nom__icontains='loyer') |
                    Q(type_transaction__nom__icontains='caf') |
                    Q(type_transaction__nom__icontains='retard loyer')
                ).exclude(
                    type_transaction__nom__icontains='charge'
                )

                paiements_charges = Transaction.objects.filter(
                    locataire=locataire,
                    bien=bien,
                    type_transaction__categorie='RECETTE',
                    mois_concerne__year=annee_courante,
                    mois_concerne__month=mois_courant
                ).filter(
                    type_transaction__nom__icontains='charge'
                ).exclude(
                    type_transaction__nom__icontains='om'
                )

                remboursements_retard = Transaction.objects.filter(
                    locataire=locataire,
                    bien=bien,
                    type_transaction__nom__icontains='retard loyer',
                    type_transaction__categorie='RECETTE',
                    mois_concerne__year=annee_courante,
                    mois_concerne__month=mois_courant
                )

                total_loyer_paye = sum(p.montant for p in paiements_loyer) + sum(p.montant for p in remboursements_retard)
                total_charges_paye = sum(p.montant for p in paiements_charges)

                loyer_mensuel = bien.loyer_mensuel or 0
                montant_charges = bien.montant_charges if bien.montant_charges is not None else 0

                if location.date_entree and location.date_entree <= premier_jour_mois_courant:
                    if total_loyer_paye >= loyer_mensuel and loyer_mensuel > 0:
                        loyer_status = "OK"
                    elif total_loyer_paye > 0:
                        loyer_status = "Partiel"
                    else:
                        loyer_status = "En attente"
                else:
                    if total_loyer_paye > 0:
                        loyer_status = "OK"
                    else:
                        loyer_status = "N/A (arrivée récente)"

                if montant_charges is not None and montant_charges > 0:
                    if total_charges_paye >= montant_charges:
                        charges_status = "OK"
                    elif total_charges_paye > 0:
                        charges_status = "Partiel"
                    else:
                        charges_status = "En attente"
                else:
                    charges_status = "N/A"
            else:
                total_loyer_paye = 0
                total_charges_paye = 0
                loyer_status = "N/A (non présent)"
                charges_status = "N/A (non présent)"
                loyer_mensuel = bien.loyer_mensuel or 0
                montant_charges = bien.montant_charges if bien.montant_charges is not None else 0

            mois_verifies = []
            for i in range(1, 4):
                mois_a_verifier = mois_courant - i
                annee_a_verifier = annee_courante

                if mois_a_verifier <= 0:
                    mois_a_verifier = 12 + mois_a_verifier
                    annee_a_verifier = annee_courante - 1

                premier_jour_mois = date(annee_a_verifier, mois_a_verifier, 1)
                dernier_jour_mois = date(
                    annee_a_verifier,
                    mois_a_verifier,
                    calendar.monthrange(annee_a_verifier, mois_a_verifier)[1]
                )

                if not location.date_entree or location.date_entree > dernier_jour_mois:
                    loyer_status_prec = "N/A"
                    charges_status_prec = "N/A"
                else:
                    paiements_loyer_prec = Transaction.objects.filter(
                        locataire=locataire,
                        bien=bien,
                        type_transaction__categorie='RECETTE',
                        mois_concerne__year=annee_a_verifier,
                        mois_concerne__month=mois_a_verifier
                    ).filter(
                        Q(type_transaction__nom__icontains='loyer') |
                        Q(type_transaction__nom__icontains='caf') |
                        Q(type_transaction__nom__icontains='retard loyer')
                    ).exclude(
                        type_transaction__nom__icontains='charge'
                    )

                    paiements_charges_prec = Transaction.objects.filter(
                        locataire=locataire,
                        bien=bien,
                        type_transaction__categorie='RECETTE',
                        mois_concerne__year=annee_a_verifier,
                        mois_concerne__month=mois_a_verifier
                    ).filter(
                        type_transaction__nom__icontains='charge'
                    ).exclude(
                        type_transaction__nom__icontains='om'
                    )

                    total_loyer_prec = sum(p.montant for p in paiements_loyer_prec)
                    total_charges_prec = sum(p.montant for p in paiements_charges_prec)

                    if total_loyer_prec >= loyer_mensuel and loyer_mensuel > 0:
                        loyer_status_prec = "OK"
                    elif total_loyer_prec > 0:
                        loyer_status_prec = "Partiel"
                    else:
                        loyer_status_prec = "Manquant"

                    if montant_charges is not None and montant_charges > 0:
                        if total_charges_prec >= montant_charges:
                            charges_status_prec = "OK"
                        elif total_charges_prec > 0:
                            charges_status_prec = "Partiel"
                        else:
                            charges_status_prec = "Manquant"
                    else:
                        charges_status_prec = "N/A"

                nom_mois = noms_mois_fr_court[mois_a_verifier]

                mois_verifies.append({
                    'nom': f"{nom_mois} {annee_a_verifier}",
                    'loyer_status': loyer_status_prec,
                    'charges_status': charges_status_prec
                })

            entry = {
                'locataire': locataire,
                'locataire_id': locataire.id,
                'est_premier_bien': premier_bien,
                'bien': bien,
                'loyer_mensuel': loyer_mensuel,
                'montant_charges': montant_charges,
                'total_paye': total_loyer_paye + total_charges_paye,
                'total_loyer_paye': total_loyer_paye,
                'total_charges_paye': total_charges_paye,
                'depot_garantie': depot_garantie_status,
                'loyer': loyer_status,
                'charges': charges_status,
                'mois_precedents': mois_verifies,
                }

            if premier_bien:
                entry['rowspan'] = locataires_count[locataire.id]

            tableau_paiements.append(entry)

            premier_bien = False

    mois_courant_fr = f"{noms_mois_fr[mois_courant]} {annee_courante}"

    context = {
        'tableau_paiements': tableau_paiements,
        'mois_courant': mois_courant_fr,
        'date_aujourd_hui': date_aujourd_hui
    }

    return render(request, 'principale/etat_paiements.html', context)

def bilan_comptable_detaille(request):
    """Vue pour afficher le bilan comptable détaillé"""
    # Obtenir l'année demandée ou l'année en cours par défaut
    annee_courante = date.today().year
    annee_selectionnee = request.GET.get('annee', annee_courante)
    try:
        annee_selectionnee = int(annee_selectionnee)
    except ValueError:
        annee_selectionnee = annee_courante

    # Liste des années disponibles (à partir de 2024 jusqu'à l'année courante)
    annee_min = 2024
    annees_disponibles = range(annee_min, annee_courante + 1)

    # ============================================================================
    # CORRECTION 1 : Fonction pour recalculer le SOLDE final d'une année
    # ============================================================================
    def recalculer_solde_annee(annee):
        """Calcule le solde final d'une année donnée"""
        try:
            params = ParametresComptables.objects.get(sci=request.current_sci, annee=annee)
            solde_initial = params.solde_initial
        except ParametresComptables.DoesNotExist:
            # Si l'année n'existe pas, le solde initial est 0
            solde_initial = 0

        # Calculer toutes les recettes et dépenses de l'année
        recettes = Transaction.objects.filter(
            sci=request.current_sci,
            date__year=annee,
            type_transaction__categorie='RECETTE'
        ).aggregate(total=Sum('montant'))['total'] or 0

        depenses = Transaction.objects.filter(
            sci=request.current_sci,
            date__year=annee,
            type_transaction__categorie='DEPENSE'
        ).aggregate(total=Sum('montant'))['total'] or 0

        return solde_initial + recettes - depenses

    # ============================================================================
    # CORRECTION 2 : Fonction pour recalculer le CC final d'une année
    # ============================================================================
    def recalculer_cc_annee(annee):
        """Calcule le CC final d'une année donnée"""
        try:
            params = ParametresComptables.objects.get(sci=request.current_sci, annee=annee)
            cc_initial = params.compte_courant_initial
        except ParametresComptables.DoesNotExist:
            # Si l'année n'existe pas, le CC initial est 0
            cc_initial = 0

        # Calculer les apports et remboursements de l'année
        apports = Transaction.objects.filter(
            sci=request.current_sci,
            date__year=annee,
            type_transaction__categorie='RECETTE',
            type_transaction__nom__icontains='apport cc'
        ).aggregate(total=Sum('montant'))['total'] or 0

        remb = Transaction.objects.filter(
            sci=request.current_sci,
            date__year=annee,
            type_transaction__categorie='DEPENSE',
            type_transaction__nom__icontains='rbt cc'
        ).aggregate(total=Sum('montant'))['total'] or 0

        return cc_initial + apports - remb

    # ============================================================================
    # CORRECTION 3 : Recalculer en cascade TOUTES les années depuis 2024
    # ============================================================================
    for annee in range(annee_min, annee_selectionnee + 1):
        if annee == annee_min:
            # Pour 2024, le CC initial et le solde initial sont 0 par défaut
            cc_initial_annee = 0
            solde_initial_annee = 0
        else:
            # Pour les autres années :
            # - CC initial = CC final de l'année précédente
            # - Solde initial = Solde final de l'année précédente
            cc_initial_annee = recalculer_cc_annee(annee - 1)
            solde_initial_annee = recalculer_solde_annee(annee - 1)

        # Mettre à jour ou créer les paramètres comptables
        params, created = ParametresComptables.objects.get_or_create(
            sci=request.current_sci,
            annee=annee,
            defaults={
                'compte_courant_initial': cc_initial_annee,
                'solde_initial': solde_initial_annee
            }
        )

        # Mettre à jour le CC initial si nécessaire
        if params.compte_courant_initial != cc_initial_annee:
            params.compte_courant_initial = cc_initial_annee
            params.save()

        # Mettre à jour le solde initial si nécessaire
        if params.solde_initial != solde_initial_annee:
            params.solde_initial = solde_initial_annee
            params.save()

    # ============================================================================
    # Récupérer le solde et CC de décembre de l'année précédente
    # ============================================================================
    solde_decembre_precedent = None
    cc_decembre_precedent = None

    if annee_selectionnee > annee_min:
        # Les valeurs ont déjà été calculées dans la boucle ci-dessus
        solde_decembre_precedent = recalculer_solde_annee(annee_selectionnee - 1)
        cc_decembre_precedent = recalculer_cc_annee(annee_selectionnee - 1)

    # Récupérer les paramètres comptables pour l'année sélectionnée
    params_comptables = ParametresComptables.objects.get(
        sci=request.current_sci,
        annee=annee_selectionnee
    )

    # Définir les noms des mois en français
    noms_mois_fr = {
        1: 'janvier', 2: 'février', 3: 'mars', 4: 'avril', 5: 'mai', 6: 'juin',
        7: 'juillet', 8: 'août', 9: 'septembre', 10: 'octobre', 11: 'novembre', 12: 'décembre'
    }

    # Tableau des données pour chaque mois
    donnees_mensuelles = []

    # Initialiser les totaux
    total_recettes = 0
    total_depenses = 0
    total_loyers = 0
    total_charges_om = 0
    total_apport_cc = 0
    total_divers_recettes = 0
    total_depenses_locataires = 0
    total_travaux = 0
    total_remboursement_cc = 0
    total_frais_impots = 0
    total_autres_depenses = 0

    # Utiliser le solde de décembre précédent s'il existe, sinon le solde initial défini
    solde_courant = solde_decembre_precedent if solde_decembre_precedent is not None else params_comptables.solde_initial

    # Compte courant d'associé initial
    cc_associe = params_comptables.compte_courant_initial

    # Ligne pour le solde initial au 1er janvier
    donnees_mensuelles.append({
        'mois': f"Solde 1er Janvier",
        'recettes': None,
        'depenses': None,
        'solde': solde_courant,
        'loyers': None,
        'charges_om': None,
        'apport_cc': None,
        'divers_recettes': None,
        'depenses_locataires': None,
        'travaux': None,
        'remboursement_cc': None,
        'frais_impots': None,
        'autres_depenses': cc_associe
    })

    for mois in range(1, 13):
        # Loyers: loyer, CAF et rbt retard loyer
        loyers = Transaction.objects.filter(
            sci=request.current_sci,
            type_transaction__categorie='RECETTE',
            date__year=annee_selectionnee,
            date__month=mois
        ).filter(
            Q(type_transaction__nom__icontains='loyer') |
            Q(type_transaction__nom__icontains='caf') |
            Q(type_transaction__nom__icontains='retard loyer')
        ).exclude(
            Q(type_transaction__nom__icontains='charge')
        ).aggregate(total=Sum('montant'))

        # Charges/OM: charges et OM
        charges_om = Transaction.objects.filter(
            sci=request.current_sci,
            type_transaction__categorie='RECETTE',
            date__year=annee_selectionnee,
            date__month=mois
        ).filter(
            Q(type_transaction__nom__icontains='charge') |
            Q(type_transaction__nom__icontains='om')
        ).aggregate(total=Sum('montant'))

        # Apport CC: apport CC
        apport_cc = Transaction.objects.filter(
            sci=request.current_sci,
            type_transaction__categorie='RECETTE',
            type_transaction__nom__icontains='apport cc',
            date__year=annee_selectionnee,
            date__month=mois
        ).aggregate(total=Sum('montant'))

        # Recettes de cautions/dépôts de garantie
        cautions_recettes = Transaction.objects.filter(
            sci=request.current_sci,
            type_transaction__categorie='RECETTE',
            date__year=annee_selectionnee,
            date__month=mois
        ).filter(
            Q(type_transaction__nom__icontains='caution') |
            Q(type_transaction__nom__icontains='dépôt de garantie') |
            Q(type_transaction__nom__icontains='depot de garantie')
        ).aggregate(total=Sum('montant'))

        # Autres recettes diverses
        autres_recettes_diverses = Transaction.objects.filter(
            sci=request.current_sci,
            type_transaction__categorie='RECETTE',
            date__year=annee_selectionnee,
            date__month=mois
        ).exclude(
            Q(type_transaction__nom__icontains='loyer') |
            Q(type_transaction__nom__icontains='caf') |
            Q(type_transaction__nom__icontains='retard loyer') |
            Q(type_transaction__nom__icontains='charge') |
            Q(type_transaction__nom__icontains='om') |
            Q(type_transaction__nom__icontains='apport cc') |
            Q(type_transaction__nom__icontains='caution') |
            Q(type_transaction__nom__icontains='dépôt de garantie') |
            Q(type_transaction__nom__icontains='depot de garantie')
        ).aggregate(total=Sum('montant'))

        # Fusionner cautions_recettes et autres_recettes_diverses
        divers_recettes_total = (cautions_recettes['total'] or 0) + (autres_recettes_diverses['total'] or 0)

        # Dépenses locataires incluent les remboursements de cautions
        depenses_locataires = Transaction.objects.filter(
            sci=request.current_sci,
            type_transaction__categorie='DEPENSE',
            date__year=annee_selectionnee,
            date__month=mois
        ).filter(
            Q(type_transaction__nom__icontains='locataire') |
            Q(type_transaction__nom__icontains='remboursement caution') |
            Q(type_transaction__nom__icontains='rbt caution') |
            Q(type_transaction__nom__icontains='restitution caution') |
            Q(type_transaction__nom__icontains='remboursement dépôt de garantie') |
            Q(type_transaction__nom__icontains='remboursement depot de garantie') |
            Q(type_transaction__nom__icontains='rbt dépôt garantie') |
            Q(type_transaction__nom__icontains='rbt depot garantie')
        ).aggregate(total=Sum('montant'))

        # Travaux
        travaux = Transaction.objects.filter(
            sci=request.current_sci,
            type_transaction__nom__icontains='travaux',
            type_transaction__categorie='DEPENSE',
            date__year=annee_selectionnee,
            date__month=mois
        ).aggregate(total=Sum('montant'))

        # Remboursement CC sans les cautions
        remboursement_cc = Transaction.objects.filter(
            sci=request.current_sci,
            type_transaction__categorie='DEPENSE',
            date__year=annee_selectionnee,
            date__month=mois,
            type_transaction__nom__icontains='rbt cc'
        ).aggregate(total=Sum('montant'))

        # Frais/Impôts
        frais_impots = Transaction.objects.filter(
            sci=request.current_sci,
            type_transaction__categorie='DEPENSE',
            date__year=annee_selectionnee,
            date__month=mois
        ).filter(
            Q(type_transaction__nom__icontains='frais') |
            Q(type_transaction__nom__icontains='impot') |
            Q(type_transaction__nom__icontains='impôt')
        ).aggregate(total=Sum('montant'))

        # Autres dépenses
        autres_depenses = Transaction.objects.filter(
            sci=request.current_sci,
            type_transaction__categorie='DEPENSE',
            date__year=annee_selectionnee,
            date__month=mois
        ).exclude(
            Q(type_transaction__nom__icontains='locataire') |
            Q(type_transaction__nom__icontains='travaux') |
            Q(type_transaction__nom__icontains='rbt cc') |
            Q(type_transaction__nom__icontains='frais') |
            Q(type_transaction__nom__icontains='impot') |
            Q(type_transaction__nom__icontains='impôt') |
            Q(type_transaction__nom__icontains='remboursement caution') |
            Q(type_transaction__nom__icontains='rbt caution') |
            Q(type_transaction__nom__icontains='restitution caution') |
            Q(type_transaction__nom__icontains='remboursement dépôt de garantie') |
            Q(type_transaction__nom__icontains='remboursement depot de garantie') |
            Q(type_transaction__nom__icontains='rbt dépôt garantie') |
            Q(type_transaction__nom__icontains='rbt depot garantie')
        ).aggregate(total=Sum('montant'))

        # Traiter les valeurs None pour chaque catégorie
        loyers_total = loyers['total'] or 0
        charges_om_total = charges_om['total'] or 0
        apport_cc_total = apport_cc['total'] or 0

        depenses_locataires_total = depenses_locataires['total'] or 0
        travaux_total = travaux['total'] or 0
        remboursement_cc_total = remboursement_cc['total'] or 0
        frais_impots_total = frais_impots['total'] or 0
        autres_depenses_total = autres_depenses['total'] or 0

        # Calculer les recettes et dépenses totales du mois
        recettes_mois = loyers_total + charges_om_total + apport_cc_total + divers_recettes_total
        depenses_mois = depenses_locataires_total + travaux_total + remboursement_cc_total + frais_impots_total + autres_depenses_total

        # Mettre à jour le solde courant
        solde_courant += recettes_mois - depenses_mois

        # Calcul correct du CC (sans les cautions)
        cc_associe = cc_associe + apport_cc_total - remboursement_cc_total

        # Ajouter aux totaux annuels
        total_recettes += recettes_mois
        total_depenses += depenses_mois
        total_loyers += loyers_total
        total_charges_om += charges_om_total
        total_apport_cc += apport_cc_total
        total_divers_recettes += divers_recettes_total
        total_depenses_locataires += depenses_locataires_total
        total_travaux += travaux_total
        total_remboursement_cc += remboursement_cc_total
        total_frais_impots += frais_impots_total
        total_autres_depenses += autres_depenses_total

        # Ajouter les données du mois au tableau
        donnees_mensuelles.append({
            'mois': f"{noms_mois_fr[mois]}-{str(annee_selectionnee)[-2:]}",
            'recettes': recettes_mois,
            'depenses': depenses_mois,
            'solde': solde_courant,
            'loyers': loyers_total,
            'charges_om': charges_om_total,
            'apport_cc': apport_cc_total,
            'divers_recettes': divers_recettes_total,
            'depenses_locataires': depenses_locataires_total,
            'travaux': travaux_total,
            'remboursement_cc': remboursement_cc_total,
            'frais_impots': frais_impots_total,
            'autres_depenses': autres_depenses_total
        })

    # Mettre à jour le solde final pour l'année sélectionnée
    params_comptables.solde_final = solde_courant
    params_comptables.save()

    # Ajouter la ligne de totaux
    donnees_mensuelles.append({
        'mois': f"Total {annee_selectionnee}",
        'recettes': total_recettes,
        'depenses': total_depenses,
        'solde': solde_courant,
        'loyers': total_loyers,
        'charges_om': total_charges_om,
        'apport_cc': total_apport_cc,
        'divers_recettes': total_divers_recettes,
        'depenses_locataires': total_depenses_locataires,
        'travaux': total_travaux,
        'remboursement_cc': total_remboursement_cc,
        'frais_impots': total_frais_impots,
        'autres_depenses': total_autres_depenses
    })

    # Calcul des loyers spécifiques aux parkings
    loyers_parking = Transaction.objects.filter(
        sci=request.current_sci,
        bien__type_bien='PARKING',
        type_transaction__categorie='RECETTE',
        type_transaction__nom__icontains='loyer',
        date__year=annee_selectionnee
    ).aggregate(total=Sum('montant'))['total'] or 0

    # Calcul des loyers spécifiques aux logements
    loyers_logement = Transaction.objects.filter(
        sci=request.current_sci,
        bien__type_bien='LOGEMENT',
        type_transaction__categorie='RECETTE',
        type_transaction__nom__icontains='loyer',
        date__year=annee_selectionnee
    ).aggregate(total=Sum('montant'))['total'] or 0

    # Calcul des loyers spécifiques aux commerces
    loyers_commerce = Transaction.objects.filter(
        sci=request.current_sci,
        bien__type_bien='COMMERCE',
        type_transaction__categorie='RECETTE',
        type_transaction__nom__icontains='loyer',
        date__year=annee_selectionnee
    ).aggregate(total=Sum('montant'))['total'] or 0

    # Convertir en decimal pour éviter des problèmes de type
    loyers_parking = decimal.Decimal(str(loyers_parking))
    loyers_logement = decimal.Decimal(str(loyers_logement))
    loyers_commerce = decimal.Decimal(str(loyers_commerce))

    # Calcul du CRL (2,5% des loyers de logements et commerces)
    loyers_soumis_crl = loyers_logement + loyers_commerce
    crl_montant = loyers_soumis_crl * decimal.Decimal('0.025')

    # Calcul du total des cautions versées et non restituées
    cautions_total = Locataire.objects.filter(
        biens__sci=request.current_sci,
        montant_caution__isnull=False,
        montant_caution__gt=0,
        date_restitution_caution__isnull=True
    ).aggregate(total=Sum('montant_caution'))['total'] or 0

    # Créer le contexte avec toutes les valeurs
    context = {
        'annee_selectionnee': annee_selectionnee,
        'annees_disponibles': annees_disponibles,
        'donnees_mensuelles': donnees_mensuelles,
        'solde_initial': params_comptables.solde_initial,
        'cc_initial': params_comptables.compte_courant_initial,
        'cc_final': cc_associe,
        'total_recettes': total_recettes,
        'total_depenses': total_depenses,
        'crl_montant': crl_montant,
        'cautions_total': cautions_total,
        'loyers_parking': loyers_parking,
        'loyers_logement': loyers_logement
    }

    return render(request, 'principale/bilan_comptable_detaille.html', context)

def exporter_bilan_detaille_pdf(request):
    """Vue pour exporter le bilan comptable détaillé en PDF"""
    # Obtenir l'année demandée ou l'année en cours par défaut
    annee_courante = date.today().year
    annee_selectionnee = request.GET.get('annee', annee_courante)
    try:
        annee_selectionnee = int(annee_selectionnee)
    except ValueError:
        annee_selectionnee = annee_courante

    # Liste des années disponibles
    annee_min = 2024

    # ============================================================================
    # CORRECTION 1 : Fonction pour recalculer le SOLDE final d'une année
    # ============================================================================
    def recalculer_solde_annee(annee):
        """Calcule le solde final d'une année donnée"""
        try:
            params = ParametresComptables.objects.get(sci=request.current_sci, annee=annee)
            solde_initial = params.solde_initial
        except ParametresComptables.DoesNotExist:
            solde_initial = 0

        recettes = Transaction.objects.filter(
            sci=request.current_sci,
            date__year=annee,
            type_transaction__categorie='RECETTE'
        ).aggregate(total=Sum('montant'))['total'] or 0

        depenses = Transaction.objects.filter(
            sci=request.current_sci,
            date__year=annee,
            type_transaction__categorie='DEPENSE'
        ).aggregate(total=Sum('montant'))['total'] or 0

        return solde_initial + recettes - depenses

    # ============================================================================
    # CORRECTION 2 : Fonction pour recalculer le CC final d'une année
    # ============================================================================
    def recalculer_cc_annee(annee):
        """Calcule le CC final d'une année donnée"""
        try:
            params = ParametresComptables.objects.get(sci=request.current_sci, annee=annee)
            cc_initial = params.compte_courant_initial
        except ParametresComptables.DoesNotExist:
            cc_initial = 0

        apports = Transaction.objects.filter(
            sci=request.current_sci,
            date__year=annee,
            type_transaction__categorie='RECETTE',
            type_transaction__nom__icontains='apport cc'
        ).aggregate(total=Sum('montant'))['total'] or 0

        remb = Transaction.objects.filter(
            sci=request.current_sci,
            date__year=annee,
            type_transaction__categorie='DEPENSE',
            type_transaction__nom__icontains='rbt cc'
        ).aggregate(total=Sum('montant'))['total'] or 0

        return cc_initial + apports - remb

    # ============================================================================
    # CORRECTION 3 : Recalculer en cascade toutes les années depuis 2024
    # ============================================================================
    for annee in range(annee_min, annee_selectionnee + 1):
        if annee == annee_min:
            cc_initial_annee = 0
            solde_initial_annee = 0
        else:
            cc_initial_annee = recalculer_cc_annee(annee - 1)
            solde_initial_annee = recalculer_solde_annee(annee - 1)

        params, created = ParametresComptables.objects.get_or_create(
            sci=request.current_sci,
            annee=annee,
            defaults={
                'compte_courant_initial': cc_initial_annee,
                'solde_initial': solde_initial_annee
            }
        )

        if params.compte_courant_initial != cc_initial_annee:
            params.compte_courant_initial = cc_initial_annee
            params.save()

        if params.solde_initial != solde_initial_annee:
            params.solde_initial = solde_initial_annee
            params.save()

    # Récupérer le solde et CC de décembre de l'année précédente
    solde_decembre_precedent = None
    cc_decembre_precedent = None

    if annee_selectionnee > annee_min:
        solde_decembre_precedent = recalculer_solde_annee(annee_selectionnee - 1)
        cc_decembre_precedent = recalculer_cc_annee(annee_selectionnee - 1)

    # Récupérer les paramètres comptables
    try:
        params_comptables = ParametresComptables.objects.get(
            sci=request.current_sci,
            annee=annee_selectionnee
        )
    except ParametresComptables.DoesNotExist:
        params_comptables = ParametresComptables.objects.create(
            sci=request.current_sci,
            annee=annee_selectionnee,
            solde_initial=solde_decembre_precedent or 0,
            compte_courant_initial=cc_decembre_precedent or 0,
            solde_final=None
        )
    except ParametresComptables.MultipleObjectsReturned:
        params_comptables = ParametresComptables.objects.filter(
            sci=request.current_sci,
            annee=annee_selectionnee
        ).first()

    # Définir les noms des mois en français
    noms_mois_fr = {
        1: 'janvier', 2: 'février', 3: 'mars', 4: 'avril', 5: 'mai', 6: 'juin',
        7: 'juillet', 8: 'août', 9: 'septembre', 10: 'octobre', 11: 'novembre', 12: 'décembre'
    }

    # Tableau des données pour chaque mois
    donnees_mensuelles = []

    # Initialiser les totaux
    total_recettes = 0
    total_depenses = 0
    total_loyers = 0
    total_charges_om = 0
    total_apport_cc = 0
    total_divers_recettes = 0
    total_depenses_locataires = 0
    total_travaux = 0
    total_remboursement_cc = 0
    total_frais_impots = 0
    total_autres_depenses = 0

    # Utiliser le solde de décembre précédent s'il existe, sinon le solde initial défini
    solde_courant = solde_decembre_precedent if solde_decembre_precedent is not None else params_comptables.solde_initial

    # Compte courant d'associé initial
    cc_associe = params_comptables.compte_courant_initial

    # Ligne pour le solde initial au 1er janvier
    donnees_mensuelles.append({
        'mois': f"Solde 1er Janvier",
        'recettes': None,
        'depenses': None,
        'solde': solde_courant,
        'loyers': None,
        'charges_om': None,
        'apport_cc': None,
        'divers_recettes': None,
        'depenses_locataires': None,
        'travaux': None,
        'remboursement_cc': None,
        'frais_impots': None,
        'autres_depenses': cc_associe
    })

    for mois in range(1, 13):
        # Loyers: loyer, CAF et rbt retard loyer
        loyers = Transaction.objects.filter(
            sci=request.current_sci,
            date__year=annee_selectionnee,
            date__month=mois,
            type_transaction__categorie='RECETTE'
        ).filter(
            Q(type_transaction__nom__icontains='loyer') |
            Q(type_transaction__nom__icontains='caf') |
            Q(type_transaction__nom__icontains='retard loyer')
        ).exclude(
            Q(type_transaction__nom__icontains='charge')
        ).aggregate(total=Sum('montant'))

        # Charges/OM: charges et OM
        charges_om = Transaction.objects.filter(
            sci=request.current_sci,
            date__year=annee_selectionnee,
            date__month=mois,
            type_transaction__categorie='RECETTE'
        ).filter(
            Q(type_transaction__nom__icontains='charge') |
            Q(type_transaction__nom__icontains='om')
        ).aggregate(total=Sum('montant'))

        # Apport CC: apport CC
        apport_cc = Transaction.objects.filter(
            sci=request.current_sci,
            date__year=annee_selectionnee,
            date__month=mois,
            type_transaction__categorie='RECETTE',
            type_transaction__nom__icontains='apport cc'
        ).aggregate(total=Sum('montant'))

        # Recettes de cautions/dépôts de garantie
        cautions_recettes = Transaction.objects.filter(
            sci=request.current_sci,
            date__year=annee_selectionnee,
            date__month=mois,
            type_transaction__categorie='RECETTE'
        ).filter(
            Q(type_transaction__nom__icontains='caution') |
            Q(type_transaction__nom__icontains='dépôt de garantie') |
            Q(type_transaction__nom__icontains='depot de garantie')
        ).aggregate(total=Sum('montant'))

        # Autres recettes diverses
        autres_recettes_diverses = Transaction.objects.filter(
            sci=request.current_sci,
            date__year=annee_selectionnee,
            date__month=mois,
            type_transaction__categorie='RECETTE'
        ).exclude(
            Q(type_transaction__nom__icontains='loyer') |
            Q(type_transaction__nom__icontains='caf') |
            Q(type_transaction__nom__icontains='retard loyer') |
            Q(type_transaction__nom__icontains='charge') |
            Q(type_transaction__nom__icontains='om') |
            Q(type_transaction__nom__icontains='apport cc') |
            Q(type_transaction__nom__icontains='caution') |
            Q(type_transaction__nom__icontains='dépôt de garantie') |
            Q(type_transaction__nom__icontains='depot de garantie')
        ).aggregate(total=Sum('montant'))

        # Fusionner cautions_recettes et autres_recettes_diverses
        divers_recettes_total = (cautions_recettes['total'] or 0) + (autres_recettes_diverses['total'] or 0)

        # Dépenses locataires incluent les remboursements de cautions
        depenses_locataires = Transaction.objects.filter(
            sci=request.current_sci,
            date__year=annee_selectionnee,
            date__month=mois,
            type_transaction__categorie='DEPENSE'
        ).filter(
            Q(type_transaction__nom__icontains='locataire') |
            Q(type_transaction__nom__icontains='remboursement caution') |
            Q(type_transaction__nom__icontains='rbt caution') |
            Q(type_transaction__nom__icontains='restitution caution') |
            Q(type_transaction__nom__icontains='remboursement dépôt de garantie') |
            Q(type_transaction__nom__icontains='remboursement depot de garantie') |
            Q(type_transaction__nom__icontains='rbt dépôt garantie') |
            Q(type_transaction__nom__icontains='rbt depot garantie')
        ).aggregate(total=Sum('montant'))

        # Travaux
        travaux = Transaction.objects.filter(
            sci=request.current_sci,
            date__year=annee_selectionnee,
            date__month=mois,
            type_transaction__nom__icontains='travaux',
            type_transaction__categorie='DEPENSE'
        ).aggregate(total=Sum('montant'))

        # Remboursement CC uniquement (sans les cautions)
        remboursement_cc = Transaction.objects.filter(
            sci=request.current_sci,
            date__year=annee_selectionnee,
            date__month=mois,
            type_transaction__categorie='DEPENSE',
            type_transaction__nom__icontains='rbt cc'
        ).aggregate(total=Sum('montant'))

        # Frais/Impôts: frais et impôts
        frais_impots = Transaction.objects.filter(
            sci=request.current_sci,
            date__year=annee_selectionnee,
            date__month=mois,
            type_transaction__categorie='DEPENSE'
        ).filter(
            Q(type_transaction__nom__icontains='frais') |
            Q(type_transaction__nom__icontains='impot') |
            Q(type_transaction__nom__icontains='impôt')
        ).aggregate(total=Sum('montant'))

        # Autres dépenses
        autres_depenses = Transaction.objects.filter(
            sci=request.current_sci,
            date__year=annee_selectionnee,
            date__month=mois,
            type_transaction__categorie='DEPENSE'
        ).exclude(
            Q(type_transaction__nom__icontains='locataire') |
            Q(type_transaction__nom__icontains='travaux') |
            Q(type_transaction__nom__icontains='rbt cc') |
            Q(type_transaction__nom__icontains='frais') |
            Q(type_transaction__nom__icontains='impot') |
            Q(type_transaction__nom__icontains='impôt') |
            Q(type_transaction__nom__icontains='remboursement caution') |
            Q(type_transaction__nom__icontains='rbt caution') |
            Q(type_transaction__nom__icontains='restitution caution') |
            Q(type_transaction__nom__icontains='remboursement dépôt de garantie') |
            Q(type_transaction__nom__icontains='remboursement depot de garantie') |
            Q(type_transaction__nom__icontains='rbt dépôt garantie') |
            Q(type_transaction__nom__icontains='rbt depot garantie')
        ).aggregate(total=Sum('montant'))

        # Traiter les valeurs None pour chaque catégorie
        loyers_total = loyers['total'] or 0
        charges_om_total = charges_om['total'] or 0
        apport_cc_total = apport_cc['total'] or 0

        depenses_locataires_total = depenses_locataires['total'] or 0
        travaux_total = travaux['total'] or 0
        remboursement_cc_total = remboursement_cc['total'] or 0
        frais_impots_total = frais_impots['total'] or 0
        autres_depenses_total = autres_depenses['total'] or 0

        # Calculer les recettes et dépenses totales du mois
        recettes_mois = loyers_total + charges_om_total + apport_cc_total + divers_recettes_total
        depenses_mois = depenses_locataires_total + travaux_total + remboursement_cc_total + frais_impots_total + autres_depenses_total

        # Mettre à jour le solde courant
        solde_courant += recettes_mois - depenses_mois

        # Calcul correct du CC (sans les cautions)
        cc_associe = cc_associe + apport_cc_total - remboursement_cc_total

        # Ajouter aux totaux annuels
        total_recettes += recettes_mois
        total_depenses += depenses_mois
        total_loyers += loyers_total
        total_charges_om += charges_om_total
        total_apport_cc += apport_cc_total
        total_divers_recettes += divers_recettes_total
        total_depenses_locataires += depenses_locataires_total
        total_travaux += travaux_total
        total_remboursement_cc += remboursement_cc_total
        total_frais_impots += frais_impots_total
        total_autres_depenses += autres_depenses_total

        # Ajouter les données du mois au tableau
        donnees_mensuelles.append({
            'mois': f"{noms_mois_fr[mois]}-{str(annee_selectionnee)[-2:]}",
            'recettes': recettes_mois,
            'depenses': depenses_mois,
            'solde': solde_courant,
            'loyers': loyers_total,
            'charges_om': charges_om_total,
            'apport_cc': apport_cc_total,
            'divers_recettes': divers_recettes_total,
            'depenses_locataires': depenses_locataires_total,
            'travaux': travaux_total,
            'remboursement_cc': remboursement_cc_total,
            'frais_impots': frais_impots_total,
            'autres_depenses': autres_depenses_total
        })

    # Mettre à jour le solde final pour l'année sélectionnée
    params_comptables.solde_final = solde_courant
    params_comptables.save()

    # Ajouter la ligne de totaux
    donnees_mensuelles.append({
        'mois': f"Total {annee_selectionnee}",
        'recettes': total_recettes,
        'depenses': total_depenses,
        'solde': solde_courant,
        'loyers': total_loyers,
        'charges_om': total_charges_om,
        'apport_cc': total_apport_cc,
        'divers_recettes': total_divers_recettes,
        'depenses_locataires': total_depenses_locataires,
        'travaux': total_travaux,
        'remboursement_cc': total_remboursement_cc,
        'frais_impots': total_frais_impots,
        'autres_depenses': total_autres_depenses
    })

    # Préparation du PDF
    buffer = io.BytesIO()

    # Utiliser un format paysage A4 pour plus d'espace horizontal
    page_width, page_height = landscape(A4)

    # Marges réduites pour maximiser l'espace disponible
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        leftMargin=15,
        rightMargin=15,
        topMargin=25,
        bottomMargin=25
    )

    elements = []

    # Styles pour le PDF
    styles = getSampleStyleSheet()

    # Style de titre amélioré
    titre_style = styles['Heading1']
    titre_style.alignment = 1  # Centré
    titre_style.fontSize = 16
    titre_style.spaceAfter = 15

    # Titre du PDF avec le nom de la SCI
    sci_nom = request.current_sci.nom if hasattr(request, 'current_sci') and request.current_sci else "SCI"
    titre = Paragraph(f"<b>Bilan Comptable Annuel {annee_selectionnee} - {sci_nom}</b>", titre_style)
    elements.append(titre)

    # Ajouter la date d'impression
    date_style = styles['Normal']
    date_style.alignment = 1  # Centré
    date_style.fontSize = 8
    date_impression = Paragraph(f"Édité le {date.today().strftime('%d/%m/%Y')}", date_style)
    elements.append(date_impression)
    elements.append(Spacer(1, 10))

    # Largeurs de colonnes optimisées
    col_widths = [
        50,     # Mois
        55,     # Recettes
        55,     # Dépenses
        55,     # Solde banque
        55,     # Loyers
        55,     # Charges et OM
        50,     # Apport CC
        50,     # Divers recettes
        55,     # Dépenses locataires
        50,     # Travaux
        55,     # Remboursement CC
        50,     # Frais et impôts
        55      # Autres dépenses
    ]

    # Ajuster les largeurs des colonnes pour s'adapter à la page
    available_width = page_width - doc.leftMargin - doc.rightMargin
    total_width = sum(col_widths)
    scaling_factor = available_width / total_width
    col_widths = [width * scaling_factor for width in col_widths]

    # En-têtes du tableau avec des libellés plus courts
    data = [
        ["Mois", "Recettes", "Dépenses", "Solde", "Loyers", "Charges/OM", "Apport CC", "Autres Rec.", "Dép. Locat.", "Travaux", "Remb. CC", "Frais/Impôts", "Autres Dép."]
    ]

    # Ajouter une ligne de sous-titres pour clarifier
    data.append([
        "",
        "€",
        "€",
        "€",
        "Recettes",
        "Recettes",
        "Recettes",
        "Recettes",
        "Dépenses",
        "Dépenses",
        "Dépenses",
        "Dépenses",
        "Dépenses"
    ])

    # Fonction pour formater les nombres
    def format_money(amount):
        if amount is None:
            return ""
        # Utiliser un espace insécable avant le symbole € pour éviter les sauts de ligne
        return f"{amount:,.2f}\u00A0€".replace(",", " ").replace(".", ",")

    # Ajouter les données mensuelles
    for item in donnees_mensuelles:
        row = [
            item['mois'],
            format_money(item['recettes']) if item['recettes'] is not None else "",
            format_money(item['depenses']) if item['depenses'] is not None else "",
            format_money(item['solde']) if item['solde'] is not None else "",
            format_money(item['loyers']) if item['loyers'] is not None else "",
            format_money(item['charges_om']) if item['charges_om'] is not None else "",
            format_money(item['apport_cc']) if item['apport_cc'] is not None else "",
            format_money(item['divers_recettes']) if item['divers_recettes'] is not None else "",
            format_money(item['depenses_locataires']) if item['depenses_locataires'] is not None else "",
            format_money(item['travaux']) if item['travaux'] is not None else "",
            format_money(item['remboursement_cc']) if item['remboursement_cc'] is not None else "",
            format_money(item['frais_impots']) if item['frais_impots'] is not None else "",
            format_money(item['autres_depenses']) if item['autres_depenses'] is not None else ""
        ]
        data.append(row)

    # Création et stylisation du tableau
    table = Table(data, colWidths=col_widths, repeatRows=2)

    # Couleurs plus douces et harmonisées
    bleu_clair = colors.Color(0.75, 0.85, 0.95)
    bleu_fonce = colors.Color(0.3, 0.5, 0.75)
    gris_clair = colors.Color(0.9, 0.9, 0.9)

    style = TableStyle([
        # Style des en-têtes
        ('BACKGROUND', (0, 0), (-1, 0), bleu_fonce),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 9),
        ('VALIGN', (0, 0), (-1, 0), 'MIDDLE'),

        # Style des sous-en-têtes
        ('BACKGROUND', (0, 1), (-1, 1), bleu_clair),
        ('TEXTCOLOR', (0, 1), (-1, 1), colors.black),
        ('ALIGN', (0, 1), (-1, 1), 'CENTER'),
        ('FONTNAME', (0, 1), (-1, 1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 1), (-1, 1), 8),

        # Style du total
        ('BACKGROUND', (0, -1), (-1, -1), bleu_fonce),
        ('TEXTCOLOR', (0, -1), (-1, -1), colors.whitesmoke),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),

        # Style général
        ('FONTSIZE', (0, 2), (-1, -2), 8),
        ('ALIGN', (0, 0), (0, -1), 'CENTER'),
        ('ALIGN', (1, 2), (-1, -1), 'RIGHT'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
    ])

    # Ajouter des lignes alternées pour la lisibilité
    for i in range(2, len(data)-1):
        if i % 2 == 0:
            style.add('BACKGROUND', (0, i), (-1, i), gris_clair)

    # Ajouter une ligne de style spéciale pour la ligne Solde 1er janvier
    style.add('BACKGROUND', (0, 2), (-1, 2), bleu_clair)
    style.add('FONTNAME', (0, 2), (-1, 2), 'Helvetica-Bold')

    table.setStyle(style)
    elements.append(table)

    # Ajouter une légende
    elements.append(Spacer(1, 15))

    legende_style = styles['Normal']
    legende_style.fontSize = 8
    legende = Paragraph("<b>Légende :</b> CC = Compte Courant d'associés, Rec. = Recettes, Dép. = Dépenses, Locat. = Locataires, Remb. = Remboursement", legende_style)
    elements.append(legende)

    # Générer le PDF
    doc.build(elements)

    # Configurer la réponse
    buffer.seek(0)
    response = HttpResponse(buffer, content_type='application/pdf')

    # Récupérer le nom de la SCI pour l'inclure dans le nom du fichier
    sci_nom = request.current_sci.nom if hasattr(request, 'current_sci') and request.current_sci else "SCI"

    # Nettoyer le nom de la SCI pour qu'il soit valide dans un nom de fichier
    safe_sci_nom = sci_nom.replace(' ', '_').replace('/', '_').replace('\\', '_')

    # Créer le nom du fichier avec la SCI et l'année
    response['Content-Disposition'] = f'attachment; filename=bilan_comptable_{safe_sci_nom}_{annee_selectionnee}.pdf'

    return response

def creances(request):
    """Vue pour afficher l'état des paiements des locataires - VERSION OPTIMISÉE"""
    locataires = Locataire.objects.filter(
        biens__sci=request.current_sci,
        locations__date_sortie__isnull=True
    ).distinct().order_by('nom', 'prenom').prefetch_related('biens')

    recapitulatif_paiements = []

    date_aujourd_hui = date.today()
    date_debut_logiciel = date(2025, 1, 1)

    noms_mois_fr = {
        1: 'Janvier', 2: 'Février', 3: 'Mars', 4: 'Avril', 5: 'Mai', 6: 'Juin',
        7: 'Juillet', 8: 'Août', 9: 'Septembre', 10: 'Octobre', 11: 'Novembre', 12: 'Décembre'
    }

    # ====================================================================
    # OPTIMISATION : Charger TOUTES les données en quelques requêtes
    # ====================================================================

    # 1. Toutes les locations actives de la SCI
    toutes_locations = {
        (loc.locataire_id, loc.bien_id): loc
        for loc in LocationBien.objects.filter(
            bien__sci=request.current_sci,
            date_sortie__isnull=True
        ).select_related('bien', 'locataire')
    }

    # 2. Toutes les transactions RECETTE depuis 2025 pour la SCI
    toutes_transactions = Transaction.objects.filter(
        sci=request.current_sci,
        type_transaction__categorie='RECETTE',
        mois_concerne__gte=date_debut_logiciel
    ).select_related('type_transaction', 'locataire', 'bien')

    # Organiser les transactions par (locataire_id, bien_id, annee, mois)
    transactions_par_cle = {}
    for t in toutes_transactions:
        if t.locataire_id and t.bien_id and t.mois_concerne:
            cle = (t.locataire_id, t.bien_id, t.mois_concerne.year, t.mois_concerne.month)
            if cle not in transactions_par_cle:
                transactions_par_cle[cle] = []
            transactions_par_cle[cle].append(t)

    # 3. Transactions de caution SANS filtre de date (historique complet)
    transactions_caution = Transaction.objects.filter(
        sci=request.current_sci,
        type_transaction_id=18
    ).select_related('locataire', 'bien')

    # 4. Tous les montants OM attendus (TOUTES les années)
    montants_om_dict = {}
    for om in MontantOM.objects.filter(sci=request.current_sci):
        cle = (om.locataire_id, om.bien_id)
        if cle not in montants_om_dict:
            montants_om_dict[cle] = []
        montants_om_dict[cle].append(om)

    # ====================================================================
    # Parcourir les locataires et calculer en Python
    # ====================================================================
    for locataire in locataires:
        biens_locataire = locataire.biens.filter(sci=request.current_sci)

        if not biens_locataire.exists():
            continue

        paiements_problematiques = []
        adresses_biens = []

        for bien in biens_locataire:
            formatted_adresse = bien.adresse
            if bien.numero:
                formatted_adresse = f"{bien.numero_formate} - {formatted_adresse}"
            adresses_biens.append(formatted_adresse)

            location = toutes_locations.get((locataire.id, bien.id))
            if not location:
                continue

            # Vérifier la caution
            montant_caution_attendu = bien.montant_caution
            total_caution_verse = sum(
                t.montant for t in transactions_caution
                if t.locataire_id == locataire.id
                and t.bien_id == bien.id
            )

            if montant_caution_attendu is not None and montant_caution_attendu > 0:
                if total_caution_verse < montant_caution_attendu:
                    montant_caution_decimal = decimal.Decimal(str(montant_caution_attendu))
                    verse_decimal = decimal.Decimal(str(total_caution_verse))
                    statut = 'Partiel' if total_caution_verse > 0 else 'Non versée'
                    paiements_problematiques.append({
                        'type': f'Caution ({bien.numero}-{bien.adresse})',
                        'mois': 'N/A',
                        'montant_attendu': montant_caution_decimal,
                        'montant_paye': verse_decimal,
                        'montant_manquant': montant_caution_decimal - verse_decimal,
                        'statut': statut
                    })

            if location.date_entree:
                date_debut_verification = max(location.date_entree, date_debut_logiciel)
                loyer_mensuel = bien.loyer_mensuel or 0
                montant_charges = bien.montant_charges if bien.montant_charges is not None else 0

                date_courante = date_debut_verification
                while date_courante <= date_aujourd_hui:
                    mois_v = date_courante.month
                    annee_v = date_courante.year

                    trans_mois = transactions_par_cle.get((locataire.id, bien.id, annee_v, mois_v), [])

                    total_loyer_paye = 0
                    total_charges_paye = 0
                    for t in trans_mois:
                        nom_lower = t.type_transaction.nom.lower()
                        if 'charge' in nom_lower and 'om' not in nom_lower:
                            total_charges_paye += t.montant
                        elif 'loyer' in nom_lower or 'caf' in nom_lower or 'retard loyer' in nom_lower:
                            total_loyer_paye += t.montant

                    if total_loyer_paye < loyer_mensuel and loyer_mensuel > 0:
                        statut = "Partiel" if total_loyer_paye > 0 else "Non payé"
                        loyer_decimal = decimal.Decimal(str(loyer_mensuel))
                        paye_decimal = decimal.Decimal(str(total_loyer_paye))
                        paiements_problematiques.append({
                            'type': f'Loyer ({bien.numero}-{bien.adresse})',
                            'mois': f"{noms_mois_fr[mois_v]} {annee_v}",
                            'montant_attendu': loyer_decimal,
                            'montant_paye': paye_decimal,
                            'montant_manquant': loyer_decimal - paye_decimal,
                            'statut': statut
                        })

                    if montant_charges is not None and montant_charges > 0 and total_charges_paye < montant_charges:
                        statut = "Partiel" if total_charges_paye > 0 else "Non payé"
                        charges_decimal = decimal.Decimal(str(montant_charges))
                        paye_decimal = decimal.Decimal(str(total_charges_paye))
                        paiements_problematiques.append({
                            'type': f'Charges ({bien.numero}-{bien.adresse})',
                            'mois': f"{noms_mois_fr[mois_v]} {annee_v}",
                            'montant_attendu': charges_decimal,
                            'montant_paye': paye_decimal,
                            'montant_manquant': charges_decimal - paye_decimal,
                            'statut': statut
                        })

                    if mois_v == 12:
                        date_courante = date(annee_v + 1, 1, 1)
                    else:
                        date_courante = date(annee_v, mois_v + 1, 1)

            # Vérification OM
            liste_om = montants_om_dict.get((locataire.id, bien.id), [])
            for om in liste_om:
                total_om_paye = 0
                for cle, trans_list in transactions_par_cle.items():
                    if cle[0] == locataire.id and cle[1] == bien.id:
                        for t in trans_list:
                            if 'om' in t.type_transaction.nom.lower() and t.mois_concerne and t.mois_concerne.year == om.annee:
                                total_om_paye += t.montant

                if om.montant_attendu > 0 and total_om_paye < om.montant_attendu:
                    montant_om_decimal = decimal.Decimal(str(om.montant_attendu))
                    total_om_paye_decimal = decimal.Decimal(str(total_om_paye))
                    statut = "Partiel" if total_om_paye > 0 else "Non payé"
                    paiements_problematiques.append({
                        'type': f'Ordures Ménagères ({bien.numero}-{bien.adresse})',
                        'mois': f"Année {om.annee}",
                        'montant_attendu': montant_om_decimal,
                        'montant_paye': total_om_paye_decimal,
                        'montant_manquant': montant_om_decimal - total_om_paye_decimal,
                        'statut': statut
                    })

        if paiements_problematiques:
            total_manquant = decimal.Decimal('0')
            for p in paiements_problematiques:
                if isinstance(p['montant_manquant'], (int, float, decimal.Decimal)):
                    if isinstance(p['montant_manquant'], (int, float)):
                        total_manquant += decimal.Decimal(str(p['montant_manquant']))
                    else:
                        total_manquant += p['montant_manquant']

            tous_biens_str = " / ".join(adresses_biens)

            recapitulatif_paiements.append({
                'locataire': locataire,
                'bien': biens_locataire.first(),
                'all_biens_str': tous_biens_str,
                'paiements': paiements_problematiques,
                'total_manquant': total_manquant
            })

    context = {
        'recapitulatif_paiements': recapitulatif_paiements,
    }

    return render(request, 'principale/creances.html', context)

def changer_sci(request):
    """Vue pour changer la SCI active"""
    if request.method == 'POST':
        sci_id = request.POST.get('sci_id')

        try:
            sci_id = int(sci_id)
            from .models import SCI
            if SCI.objects.filter(id=sci_id).exists():
                request.session['sci_id'] = sci_id
                request.session.save()  # Assurez-vous que la session est sauvegardée
        except (ValueError, TypeError):
            pass

    return redirect('dashboard')

def ajouter_location_bien(request, locataire_id):
    locataire = get_object_or_404(Locataire, id=locataire_id)

    if request.method == 'POST':
        form = LocationBienForm(
            request.POST,
            sci=request.current_sci,
            locataire=locataire
        )
        if form.is_valid():
            location = form.save(commit=False)
            location.locataire = locataire
            location.save()

            # Ajouter le bien à la relation ManyToMany si pas déjà présent
            if not locataire.biens.filter(id=location.bien.id).exists():
                locataire.biens.add(location.bien)

            messages.success(request, f"Le logement a été ajouté avec succès.")
            return redirect('detail_locataire', locataire_id=locataire.id)
    else:
        # Filtrer pour n'afficher que les biens vacants
        form = LocationBienForm(sci=request.current_sci, locataire=locataire, vacant_only=True)

    return render(request, 'principale/formulaire_location_bien.html', {
        'form': form,
        'locataire': locataire,
        'titre': f'Ajouter un logement pour {locataire.nom} {locataire.prenom}'
    })

def modifier_location_bien(request, location_id):
    # Récupérer la location et le locataire
    location = get_object_or_404(LocationBien, id=location_id, bien__sci=request.current_sci)
    locataire = location.locataire

    # Debug info
    print(f"Modification de location - ID: {location.id}, date_entree: {location.date_entree}")

    if request.method == 'POST':
        form = LocationBienForm(
            request.POST,
            instance=location,
            sci=request.current_sci
        )
        if form.is_valid():
            location = form.save()
            messages.success(request, f"Les informations du logement ont été modifiées avec succès.")
            return redirect('detail_locataire', locataire_id=locataire.id)
    else:
        # Forcer les valeurs initiales directement dans initial
        form = LocationBienForm(
            instance=location,
            sci=request.current_sci,
            initial={
                'date_entree': location.date_entree,
                'date_sortie': location.date_sortie,
                'montant_caution': location.montant_caution,
                'date_versement_caution': location.date_versement_caution,
                'date_restitution_caution': location.date_restitution_caution
            }
        )

        # Vérifier ce qui se trouve dans initial après création du formulaire
        print(f"Valeur initiale de date_entree dans le formulaire: {form.initial.get('date_entree')}")

    return render(request, 'principale/formulaire_location_bien.html', {
        'form': form,
        'locataire': locataire,
        'location': location,
        'titre': f'Modifier le logement pour {locataire.nom} {locataire.prenom}'
    })

def supprimer_location_bien(request, location_id):
    location = get_object_or_404(LocationBien, id=location_id, bien__sci=request.current_sci)
    locataire = location.locataire

    if request.method == 'POST':
        location.delete()
        messages.success(request, f"Le logement a été retiré du locataire avec succès.")
        return redirect('detail_locataire', locataire_id=locataire.id)

    return render(request, 'principale/confirmer_suppression.html', {
        'objet': f"l'association du locataire {locataire.nom} {locataire.prenom} avec le bien {location.bien}",
        'type_objet': 'location',
        'url_retour': 'detail_locataire',
        'url_retour_id': locataire.id
    })

def get_biens_locataire(request, locataire_id):
    try:
        locataire = Locataire.objects.get(id=locataire_id)
        biens = locataire.biens.all()

        # Préparer les données des biens
        biens_data = [
            {
                'id': bien.id,
                'adresse': str(bien)  # Utiliser la méthode __str__ du modèle Bien
            }
            for bien in biens
        ]

        return JsonResponse({
            'biens': biens_data
        })
    except Locataire.DoesNotExist:
        return JsonResponse({'biens': []}, status=404)

def apercu_impression_creances(request):
    """Vue pour l'export des créances en Excel avec filtre date optionnel"""

    date_fin_str = request.GET.get('date_fin', '')
    if date_fin_str:
        try:
            date_fin = datetime.strptime(date_fin_str, '%Y-%m-%d').date()
        except ValueError:
            date_fin = date.today()
    else:
        date_fin = date.today()

    locataires = Locataire.objects.filter(
        biens__sci=request.current_sci,
        locations__date_sortie__isnull=True
    ).distinct()

    commentaires = {}
    if 'commentaires' in request.GET:
        try:
            import json
            commentaires = json.loads(request.GET.get('commentaires', '{}'))
        except:
            commentaires = {}

    liste_creances = []
    date_debut_logiciel = date(2025, 1, 1)

    for locataire in locataires:
        biens_locataire = locataire.biens.filter(sci=request.current_sci)

        if not biens_locataire.exists():
            continue

        for bien in biens_locataire:
            location = LocationBien.objects.filter(
                locataire=locataire,
                bien=bien,
                date_sortie__isnull=True
            ).first()

            if not location:
                continue

            # Vérifier la caution — uniquement si un montant est défini
            if not getattr(location, 'date_versement_caution', None):
                montant_caution = None
                if hasattr(location, 'montant_caution') and location.montant_caution is not None:
                    montant_caution = location.montant_caution
                elif hasattr(bien, 'montant_caution') and bien.montant_caution:
                    montant_caution = bien.montant_caution

                if montant_caution:
                    creance_id = f"caution_{locataire.id}_{bien.id}"
                    commentaire = commentaires.get(creance_id, '')

                    liste_creances.append({
                        'locataire': f"{locataire.nom} {locataire.prenom}",
                        'bien': f"{bien.adresse}, {bien.code_postal} {bien.ville}",
                        'type': f'Caution ({bien.numero}-{bien.adresse})',
                        'periode': 'N/A',
                        'montant_attendu': decimal.Decimal(str(montant_caution)),
                        'montant_paye': decimal.Decimal('0'),
                        'montant_manquant': decimal.Decimal(str(montant_caution)),
                        'commentaire': commentaire,
                        'id': creance_id
                    })

            if location.date_entree:
                date_entree = location.date_entree
                date_debut_verification = max(date_entree, date_debut_logiciel)

                noms_mois_fr = {
                    1: 'Janvier', 2: 'Février', 3: 'Mars', 4: 'Avril', 5: 'Mai', 6: 'Juin',
                    7: 'Juillet', 8: 'Août', 9: 'Septembre', 10: 'Octobre', 11: 'Novembre', 12: 'Décembre'
                }

                loyer_mensuel = bien.loyer_mensuel or 0
                montant_charges = bien.montant_charges if bien.montant_charges is not None else 0

                date_courante = date_debut_verification
                while date_courante <= date_fin:
                    mois_a_verifier = date_courante.month
                    annee_a_verifier = date_courante.year

                    paiements_loyer = Transaction.objects.filter(
                        locataire=locataire,
                        bien=bien,
                        type_transaction__categorie='RECETTE',
                        mois_concerne__year=annee_a_verifier,
                        mois_concerne__month=mois_a_verifier
                    ).filter(
                        Q(type_transaction__nom__icontains='loyer') |
                        Q(type_transaction__nom__icontains='caf') |
                        Q(type_transaction__nom__icontains='retard loyer')
                    ).exclude(
                        type_transaction__nom__icontains='charge'
                    )

                    paiements_charges = Transaction.objects.filter(
                        locataire=locataire,
                        bien=bien,
                        type_transaction__categorie='RECETTE',
                        mois_concerne__year=annee_a_verifier,
                        mois_concerne__month=mois_a_verifier
                    ).filter(
                        type_transaction__nom__icontains='charge'
                    ).exclude(
                        type_transaction__nom__icontains='om'
                    )

                    total_loyer_paye = sum(p.montant for p in paiements_loyer)
                    total_charges_paye = sum(p.montant for p in paiements_charges)

                    if total_loyer_paye < loyer_mensuel and loyer_mensuel > 0:
                        creance_id = f"loyer_{locataire.id}_{bien.id}_{mois_a_verifier}_{annee_a_verifier}"
                        commentaire = commentaires.get(creance_id, '')

                        adresse_bien = f"{bien.adresse}, {bien.code_postal} {bien.ville}"
                        if bien.numero:
                            adresse_bien = f"{bien.numero} - {adresse_bien}"

                        liste_creances.append({
                            'locataire': f"{locataire.nom} {locataire.prenom}",
                            'bien': adresse_bien,
                            'type': f'Loyer ({bien.numero}-{bien.adresse})',
                            'periode': f"{noms_mois_fr[mois_a_verifier]} {annee_a_verifier}",
                            'montant_attendu': decimal.Decimal(str(loyer_mensuel)),
                            'montant_paye': decimal.Decimal(str(total_loyer_paye)),
                            'montant_manquant': decimal.Decimal(str(loyer_mensuel - total_loyer_paye)),
                            'commentaire': commentaire,
                            'id': creance_id
                        })

                    if montant_charges is not None and montant_charges > 0 and total_charges_paye < montant_charges:
                        creance_id = f"charges_{locataire.id}_{bien.id}_{mois_a_verifier}_{annee_a_verifier}"
                        commentaire = commentaires.get(creance_id, '')

                        adresse_bien = f"{bien.adresse}, {bien.code_postal} {bien.ville}"
                        if bien.numero:
                            adresse_bien = f"{bien.numero} - {adresse_bien}"

                        liste_creances.append({
                            'locataire': f"{locataire.nom} {locataire.prenom}",
                            'bien': adresse_bien,
                            'type': f'Charges ({bien.numero}-{bien.adresse})',
                            'periode': f"{noms_mois_fr[mois_a_verifier]} {annee_a_verifier}",
                            'montant_attendu': decimal.Decimal(str(montant_charges)),
                            'montant_paye': decimal.Decimal(str(total_charges_paye)),
                            'montant_manquant': decimal.Decimal(str(montant_charges - total_charges_paye)),
                            'commentaire': commentaire,
                            'id': creance_id
                        })

                    if mois_a_verifier == 12:
                        date_courante = date(annee_a_verifier + 1, 1, 1)
                    else:
                        date_courante = date(annee_a_verifier, mois_a_verifier + 1, 1)

            # Vérification OM — pour TOUTES les années où un montant est défini (jusqu'à date_fin)
            montants_om_locataire = MontantOM.objects.filter(
                sci=request.current_sci,
                locataire=locataire,
                bien=bien,
                annee__lte=date_fin.year
            )

            for om in montants_om_locataire:
                paiement_om = Transaction.objects.filter(
                    locataire=locataire,
                    bien=bien,
                    type_transaction__nom__icontains='OM',
                    type_transaction__categorie='RECETTE',
                    mois_concerne__year=om.annee
                )
                total_om_paye = sum(p.montant for p in paiement_om)

                if total_om_paye < om.montant_attendu:
                    montant_om_decimal = decimal.Decimal(str(om.montant_attendu))
                    total_om_paye_decimal = decimal.Decimal(str(total_om_paye))

                    creance_id = f"om_{locataire.id}_{bien.id}_{om.annee}"
                    commentaire = commentaires.get(creance_id, '')

                    adresse_bien = f"{bien.adresse}, {bien.code_postal} {bien.ville}"
                    if bien.numero:
                        adresse_bien = f"{bien.numero} - {adresse_bien}"

                    liste_creances.append({
                        'locataire': f"{locataire.nom} {locataire.prenom}",
                        'bien': adresse_bien,
                        'type': f'Ordures Ménagères ({bien.numero}-{bien.adresse})',
                        'periode': f"Année {om.annee}",
                        'montant_attendu': montant_om_decimal,
                        'montant_paye': total_om_paye_decimal,
                        'montant_manquant': montant_om_decimal - total_om_paye_decimal,
                        'commentaire': commentaire,
                        'id': creance_id
                    })

    total_attendu = decimal.Decimal('0')
    for creance in liste_creances:
        if isinstance(creance['montant_attendu'], (int, float, decimal.Decimal)):
            if isinstance(creance['montant_attendu'], (int, float)):
                total_attendu += decimal.Decimal(str(creance['montant_attendu']))
            else:
                total_attendu += creance['montant_attendu']

    total_paye = decimal.Decimal('0')
    for creance in liste_creances:
        if isinstance(creance['montant_paye'], (int, float, decimal.Decimal)):
            if isinstance(creance['montant_paye'], (int, float)):
                total_paye += decimal.Decimal(str(creance['montant_paye']))
            else:
                total_paye += creance['montant_paye']

    total_manquant = total_attendu - total_paye

    date_fin_affichage = date_fin.strftime('%d/%m/%Y')

    context = {
        'liste_creances': liste_creances,
        'date_edition': date.today().strftime('%d/%m/%Y'),
        'date_fin_affichage': date_fin_affichage,
        'total_attendu': total_attendu,
        'total_paye': total_paye,
        'total_manquant': total_manquant,
    }

    try:
        import xlsxwriter
        return generer_excel_creances(request, liste_creances, context)
    except ImportError:
        messages.error(request, "L'export Excel n'est pas disponible (module xlsxwriter manquant).")
        return redirect('creances')
    except Exception as e:
        messages.error(request, f"Erreur lors de la génération Excel : {str(e)}")
        return redirect('creances')

def generer_excel_creances(request, liste_creances, context):
    """Générer un fichier Excel des créances"""
    import xlsxwriter

    # Créer un buffer pour stocker le fichier Excel
    buffer = io.BytesIO()

    # Créer un nouveau classeur Excel
    workbook = xlsxwriter.Workbook(buffer)

    # Ajouter une feuille
    worksheet = workbook.add_worksheet("Créances")

    # Définir les styles
    titre_style = workbook.add_format({
        'bold': True,
        'font_size': 14,
        'align': 'center',
        'valign': 'vcenter'
    })

    header_style = workbook.add_format({
        'bold': True,
        'bg_color': '#CCCCCC',
        'border': 1,
        'align': 'center',
        'valign': 'vcenter'
    })

    cell_style_center = workbook.add_format({
        'border': 1,
        'align': 'center',
        'valign': 'vcenter'
    })

    cell_style_left = workbook.add_format({
        'border': 1,
        'align': 'left',
        'valign': 'vcenter'
    })

    cell_style_right = workbook.add_format({
        'border': 1,
        'align': 'right',
        'valign': 'vcenter',
        'num_format': '0.00 €'
    })

    total_style = workbook.add_format({
        'bold': True,
        'bg_color': '#CCCCCC',
        'border': 1,
        'align': 'right',
        'valign': 'vcenter',
        'num_format': '0.00 €'
    })

    # Écrire les titres
    worksheet.merge_range('A1:G1', f"État des créances - {request.current_sci.nom}", titre_style)
    worksheet.merge_range('A2:G2', f"Édité le {context['date_edition']}", cell_style_center)

    # Écrire les en-têtes de colonnes
    headers = ['Locataire', 'Bien', 'Type', 'Période', 'Montant attendu', 'Montant payé', 'Commentaire']
    for col, header in enumerate(headers):
        worksheet.write(3, col, header, header_style)

    # Écrire les données
    row = 4
    for creance in liste_creances:
        # Locataire
        worksheet.write(row, 0, creance['locataire'], cell_style_left)

        # Bien
        worksheet.write(row, 1, creance['bien'], cell_style_left)

        # Type
        worksheet.write(row, 2, creance['type'], cell_style_center)

        # Période
        worksheet.write(row, 3, creance['periode'], cell_style_center)

        # Montant attendu
        if creance['montant_attendu'] == 'À déterminer':
            worksheet.write(row, 4, 'À déterminer', cell_style_center)
        else:
            worksheet.write_number(row, 4, float(creance['montant_attendu']), cell_style_right)

        # Montant payé
        worksheet.write_number(row, 5, float(creance['montant_paye']), cell_style_right)

        # Commentaire
        commentaire = creance.get('commentaire', '')
        worksheet.write(row, 6, commentaire, cell_style_left)

        row += 1

    # Écrire les totaux
    worksheet.merge_range(row, 0, row, 3, 'TOTAL', header_style)

    # Total montant attendu
    if isinstance(context['total_attendu'], (int, float, decimal.Decimal)):
        worksheet.write_number(row, 4, float(context['total_attendu']), total_style)
    else:
        worksheet.write(row, 4, 'N/A', total_style)

    # Total montant payé
    worksheet.write_number(row, 5, float(context['total_paye']), total_style)

    # Reste à payer dans la colonne commentaire
    worksheet.write(row, 6, f"Reste à payer: {float(context['total_manquant']):.2f} €", total_style)

    # Ajuster la largeur des colonnes
    worksheet.set_column('A:A', 20)  # Locataire
    worksheet.set_column('B:B', 30)  # Bien
    worksheet.set_column('C:C', 15)  # Type
    worksheet.set_column('D:D', 15)  # Période
    worksheet.set_column('E:E', 15)  # Montant attendu
    worksheet.set_column('F:F', 15)  # Montant payé
    worksheet.set_column('G:G', 30)  # Commentaire

    # Fermer le classeur
    workbook.close()

    # Préparer la réponse
    buffer.seek(0)
    response = HttpResponse(
        buffer,
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    safe_sci_nom = request.current_sci.nom.replace(' ', '_').replace('/', '_').replace('\\', '_')
    response['Content-Disposition'] = f'attachment; filename=creances_{safe_sci_nom}_{context["date_edition"].replace("/", "_")}.xlsx'

    return response

def exporter_transactions(request):
    """Vue pour exporter les transactions en PDF ou Excel"""
    # Récupérer les paramètres de la requête
    annee = request.GET.get('annee', date.today().year)
    format_export = request.GET.get('format', 'pdf')

    try:
        annee = int(annee)
    except ValueError:
        annee = date.today().year

    # Récupérer les transactions de l'année sélectionnée
    transactions = Transaction.objects.filter(
        sci=request.current_sci,
        date__year=annee
    ).order_by('date')

    # Calculer les totaux
    recettes = transactions.filter(type_transaction__categorie='RECETTE').aggregate(total=Sum('montant'))
    depenses = transactions.filter(type_transaction__categorie='DEPENSE').aggregate(total=Sum('montant'))

    recettes_total = recettes['total'] or 0
    depenses_total = depenses['total'] or 0
    bilan = recettes_total - depenses_total

    # Préparer le contexte commun
    context = {
        'transactions': transactions,
        'recettes_total': recettes_total,
        'depenses_total': depenses_total,
        'bilan': bilan,
        'annee': annee,
        'date_edition': date.today().strftime('%d/%m/%Y')
    }

    # Exporter au format demandé
    if format_export == 'excel':
        return exporter_transactions_excel(request, transactions, context)
    else:  # Par défaut, PDF
        return exporter_transactions_pdf(request, transactions, context)

def exporter_transactions_pdf(request, transactions, context):
    """Générer un PDF des transactions"""
    buffer = io.BytesIO()

    # Configuration du document
    page_width, page_height = landscape(A4)  # Format paysage pour avoir plus de colonnes
    margin_left = 1.0*cm
    margin_right = 1.0*cm
    margin_top = 1.5*cm
    margin_bottom = 1.5*cm

    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        leftMargin=margin_left,
        rightMargin=margin_right,
        topMargin=margin_top,
        bottomMargin=margin_bottom
    )

    elements = []

    # Styles
    styles = getSampleStyleSheet()

    # Titre
    titre_style = ParagraphStyle(
        'TitreTransactions',
        parent=styles['Heading1'],
        fontSize=16,
        alignment=TA_CENTER,
        spaceAfter=0.5*cm
    )

    # Date
    date_style = ParagraphStyle(
        'DateTransactions',
        parent=styles['Normal'],
        fontSize=10,
        textColor=colors.grey,
        alignment=TA_CENTER,
        spaceAfter=0.8*cm
    )

    # Style pour le texte centré
    cell_style = ParagraphStyle(
        'CellStyle',
        parent=styles['Normal'],
        fontSize=9,
        leading=11,
        alignment=TA_CENTER,
        spaceBefore=1,
        spaceAfter=1,
        wordWrap='LTR',
        splitLongWords=False
    )

    # Style pour le texte aligné à gauche
    left_style = ParagraphStyle(
        'LeftStyle',
        parent=cell_style,
        alignment=TA_LEFT
    )

    # Style pour les montants
    montant_style = ParagraphStyle(
        'MontantStyle',
        parent=cell_style,
        alignment=TA_RIGHT
    )

    # Titre et date
    elements.append(Paragraph(f"Transactions {context['annee']} - {request.current_sci.nom}", titre_style))
    elements.append(Paragraph(f"Édité le {context['date_edition']}", date_style))

    # Préparer les données du tableau
    data = [
        [
            Paragraph('<b>Date</b>', cell_style),
            Paragraph('<b>Mois concerné</b>', cell_style),
            Paragraph('<b>Type</b>', cell_style),
            Paragraph('<b>Montant</b>', cell_style),
            Paragraph('<b>Bien / SCI</b>', cell_style),
            Paragraph('<b>Locataire</b>', cell_style),
            Paragraph('<b>Description</b>', cell_style)
        ]
    ]

    # Ajouter les transactions
    for transaction in transactions:
        # Formater la date
        date_str = transaction.date.strftime('%d/%m/%Y')

        # Formater le mois concerné
        if transaction.mois_concerne:
            mois_str = transaction.mois_concerne.strftime('%m/%Y')
        else:
            mois_str = "-"

        # Formater le type
        type_str = f"{transaction.type_transaction.categorie} - {transaction.type_transaction.nom}"

        # Formater le montant
        if transaction.type_transaction.categorie == 'RECETTE':
            montant_str = f"+{transaction.montant:.2f}\u00A0€"
        else:
            montant_str = f"-{transaction.montant:.2f}\u00A0€"

        # Formater le bien ou SCI
        if transaction.sci:
            bien_str = "SCI"
        elif transaction.bien:
            bien_str = str(transaction.bien)  # Utiliser la méthode __str__ du bien
        else:
            bien_str = "-"

        # Formater le locataire
        locataire_str = str(transaction.locataire) if transaction.locataire else "-"

        # Formater la description
        description_str = transaction.description or "-"

        # Ajouter la ligne
        data.append([
            Paragraph(date_str, cell_style),
            Paragraph(mois_str, cell_style),
            Paragraph(type_str, left_style),
            Paragraph(montant_str, montant_style),
            Paragraph(bien_str, left_style),
            Paragraph(locataire_str, left_style),
            Paragraph(description_str, left_style)
        ])

    # Ajouter la ligne de totaux
    total_row = [
        Paragraph('<b>TOTAL</b>', left_style),
        Paragraph('', cell_style),
        Paragraph('', cell_style),
        Paragraph(f"<b>Recettes: +{context['recettes_total']:.2f}\u00A0€<br/>Dépenses: -{context['depenses_total']:.2f}\u00A0€<br/>Bilan: {context['bilan']:.2f}\u00A0€</b>", montant_style),
        Paragraph('', cell_style),
        Paragraph('', cell_style),
        Paragraph('', cell_style)
    ]
    data.append(total_row)

    # Définir les largeurs des colonnes
    available_width = page_width - margin_left - margin_right
    col_widths = [
        available_width * 0.10,  # Date
        available_width * 0.10,  # Mois concerné
        available_width * 0.15,  # Type
        available_width * 0.12,  # Montant
        available_width * 0.15,  # Bien / SCI
        available_width * 0.15,  # Locataire
        available_width * 0.23   # Description
    ]

    # Créer le tableau
    table = Table(data, colWidths=col_widths, repeatRows=1)

    # Style du tableau
    style = TableStyle([
        # En-têtes
        ('BACKGROUND', (0, 0), (-1, 0), colors.Color(0.9, 0.9, 0.9)),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),

        # Alignement des cellules
        ('ALIGN', (0, 1), (1, -2), 'CENTER'),  # Date et Mois concerné centrés
        ('ALIGN', (3, 1), (3, -2), 'RIGHT'),   # Montant à droite

        # Ligne de total
        ('BACKGROUND', (0, -1), (-1, -1), colors.Color(0.9, 0.9, 0.9)),

        # Bordures
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ('BOX', (0, 0), (-1, -1), 1, colors.black),

        # Espacement
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ])

    # Lignes alternées
    for i in range(1, len(data)-1, 2):
        style.add('BACKGROUND', (0, i), (-1, i), colors.Color(0.95, 0.95, 0.95))

    # Couleurs différentes pour recettes et dépenses
    for i in range(1, len(data)-1):
        if 'RECETTE' in data[i][2].text:
            style.add('TEXTCOLOR', (3, i), (3, i), colors.green)
        elif 'DEPENSE' in data[i][2].text:
            style.add('TEXTCOLOR', (3, i), (3, i), colors.red)

    table.setStyle(style)
    elements.append(table)

    # Générer le PDF
    doc.build(elements)

    # Préparer la réponse
    buffer.seek(0)
    response = HttpResponse(buffer, content_type='application/pdf')
    safe_sci_nom = request.current_sci.nom.replace(' ', '_').replace('/', '_').replace('\\', '_')
    response['Content-Disposition'] = f'attachment; filename=transactions_{safe_sci_nom}_{context["annee"]}.pdf'

    return response

def exporter_transactions_excel(request, transactions, context):
    """Générer un fichier Excel des transactions"""
    import xlsxwriter

    # Créer un buffer pour stocker le fichier Excel
    buffer = io.BytesIO()

    # Créer un nouveau classeur Excel
    workbook = xlsxwriter.Workbook(buffer)

    # Ajouter une feuille
    worksheet = workbook.add_worksheet("Transactions")

    # Définir les styles
    titre_style = workbook.add_format({
        'bold': True,
        'font_size': 14,
        'align': 'center',
        'valign': 'vcenter'
    })

    header_style = workbook.add_format({
        'bold': True,
        'bg_color': '#CCCCCC',
        'border': 1,
        'align': 'center',
        'valign': 'vcenter'
    })

    cell_style_center = workbook.add_format({
        'border': 1,
        'align': 'center',
        'valign': 'vcenter'
    })

    cell_style_left = workbook.add_format({
        'border': 1,
        'align': 'left',
        'valign': 'vcenter'
    })

    cell_style_right = workbook.add_format({
        'border': 1,
        'align': 'right',
        'valign': 'vcenter',
        'num_format': '0.00 €'
    })

    cell_style_date = workbook.add_format({
        'border': 1,
        'align': 'center',
        'valign': 'vcenter',
        'num_format': 'dd/mm/yyyy'
    })

    recette_style = workbook.add_format({
        'border': 1,
        'align': 'right',
        'valign': 'vcenter',
        'num_format': '0.00 €',
        'font_color': 'green'
    })

    depense_style = workbook.add_format({
        'border': 1,
        'align': 'right',
        'valign': 'vcenter',
        'num_format': '0.00 €',
        'font_color': 'red'
    })

    total_style = workbook.add_format({
        'bold': True,
        'bg_color': '#CCCCCC',
        'border': 1,
        'align': 'right',
        'valign': 'vcenter',
        'num_format': '0.00 €'
    })

    # Écrire les titres
    worksheet.merge_range('A1:G1', f"Transactions {context['annee']} - {request.current_sci.nom}", titre_style)
    worksheet.merge_range('A2:G2', f"Édité le {context['date_edition']}", cell_style_center)

    # Écrire les en-têtes de colonnes
    headers = ['Date', 'Mois concerné', 'Type', 'Montant', 'Bien / SCI', 'Locataire', 'Description']
    for col, header in enumerate(headers):
        worksheet.write(3, col, header, header_style)

    # Écrire les données
    row = 4
    for transaction in transactions:
        # Date
        worksheet.write_datetime(row, 0, transaction.date, cell_style_date)

        # Mois concerné
        if transaction.mois_concerne:
            worksheet.write(row, 1, transaction.mois_concerne.strftime('%m/%Y'), cell_style_center)
        else:
            worksheet.write(row, 1, "-", cell_style_center)

        # Type
        worksheet.write(row, 2, f"{transaction.type_transaction.categorie} - {transaction.type_transaction.nom}", cell_style_left)

        # Montant avec style selon recette ou dépense
        if transaction.type_transaction.categorie == 'RECETTE':
            worksheet.write_number(row, 3, transaction.montant, recette_style)
        else:
            worksheet.write_number(row, 3, -transaction.montant, depense_style)

        # Bien / SCI
        if transaction.sci:
            worksheet.write(row, 4, "SCI", cell_style_left)
        elif transaction.bien:
            worksheet.write(row, 4, str(transaction.bien), cell_style_left)
        else:
            worksheet.write(row, 4, "-", cell_style_left)

        # Locataire
        worksheet.write(row, 5, str(transaction.locataire) if transaction.locataire else "-", cell_style_left)

        # Description
        worksheet.write(row, 6, transaction.description or "-", cell_style_left)

        row += 1

    # Écrire les totaux
    worksheet.merge_range(row, 0, row, 2, 'TOTAL', header_style)
    worksheet.write_formula(row, 3, f'=SUM(D5:D{row})', total_style)
    worksheet.merge_range(row, 4, row, 6, "", header_style)

    # Écrire les détails des totaux
    row += 2
    worksheet.write(row, 2, "Recettes:", cell_style_right)
    worksheet.write(row, 3, context['recettes_total'], recette_style)

    row += 1
    worksheet.write(row, 2, "Dépenses:", cell_style_right)
    worksheet.write(row, 3, -context['depenses_total'], depense_style)

    row += 1
    worksheet.write(row, 2, "Bilan:", cell_style_right)
    worksheet.write(row, 3, context['bilan'], total_style)

    # Ajuster la largeur des colonnes
    worksheet.set_column('A:A', 12)  # Date
    worksheet.set_column('B:B', 12)  # Mois concerné
    worksheet.set_column('C:C', 20)  # Type
    worksheet.set_column('D:D', 15)  # Montant
    worksheet.set_column('E:E', 25)  # Bien / SCI
    worksheet.set_column('F:F', 20)  # Locataire
    worksheet.set_column('G:G', 40)  # Description

    # Fermer le classeur
    workbook.close()

    # Préparer la réponse
    buffer.seek(0)
    response = HttpResponse(
        buffer,
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    safe_sci_nom = request.current_sci.nom.replace(' ', '_').replace('/', '_').replace('\\', '_')
    response['Content-Disposition'] = f'attachment; filename=transactions_{safe_sci_nom}_{context["annee"]}.xlsx'

    return response

def export_mouvements_locataires(request):
    """Page d'export des mouvements de locataires (entrées/sorties)"""

    # Récupérer l'année sélectionnée (par défaut année courante)
    annee_courante = date.today().year
    annee_selectionnee = request.GET.get('annee', annee_courante)
    try:
        annee_selectionnee = int(annee_selectionnee)
    except ValueError:
        annee_selectionnee = annee_courante

    # Générer l'export dans le format demandé
    format_export = request.GET.get('format', 'pdf')

    # Date de début et fin de l'année sélectionnée
    date_debut_annee = date(annee_selectionnee, 1, 1)
    date_fin_annee = date(annee_selectionnee, 12, 31)

    # Récupérer les locations terminées pendant l'année sélectionnée
    locations_terminees = LocationBien.objects.filter(
        bien__sci=request.current_sci,
        date_sortie__gte=date_debut_annee,
        date_sortie__lte=date_fin_annee
    ).order_by('-date_sortie')

    # Récupérer les locations actives au 31/12 de l'année sélectionnée
    # (entrées avant ou pendant l'année ET pas encore sorties OU sorties après l'année)
    locations_actives = LocationBien.objects.filter(
        bien__sci=request.current_sci,
        date_entree__lte=date_fin_annee
    ).filter(
        Q(date_sortie__isnull=True) |
        Q(date_sortie__gt=date_fin_annee)
    ).order_by('date_entree')

    # Préparer les données pour l'export
    mouvements = []

    # Pour chaque location terminée, recherche si un nouveau locataire a pris la suite
    for location in locations_terminees:
        bien = location.bien
        locataire = location.locataire
        date_sortie = location.date_sortie

        # Rechercher la location suivante pour ce bien
        nouvelle_location = LocationBien.objects.filter(
            bien=bien,
            date_entree__gte=date_sortie
        ).order_by('date_entree').first()

        nouveau_locataire = nouvelle_location.locataire if nouvelle_location else None

        mouvements.append({
            'bien': bien,
            'ancien_locataire': locataire,
            'date_entree': location.date_entree,
            'date_sortie': date_sortie,
            'nouveau_locataire': nouveau_locataire,
            'nouvelle_date_entree': nouvelle_location.date_entree if nouvelle_location else None
        })

    # Trier les mouvements par date de sortie décroissante
    mouvements.sort(key=lambda x: x['date_sortie'] or date.today(), reverse=True)

    # Préparer le contexte
    context = {
        'mouvements': mouvements,
        'locations_actives': locations_actives,
        'date_edition': date.today().strftime('%d/%m/%Y'),
        'sci_nom': request.current_sci.nom,
        'annee_selectionnee': annee_selectionnee
    }

    # Générer le rapport dans le format demandé
    if format_export == 'excel':
        return generer_excel_mouvements_locataires(request, context)
    else:
        return generer_pdf_mouvements_locataires(request, context)

def export_etat_cautions(request):
    """Page d'export de l'état des dépôts de garantie avec sélection d'année"""

    # Récupérer l'année sélectionnée (par défaut année courante)
    annee_courante = date.today().year
    annee_selectionnee = request.GET.get('annee', annee_courante)
    try:
        annee_selectionnee = int(annee_selectionnee)
    except ValueError:
        annee_selectionnee = annee_courante

    # Générer l'export dans le format demandé
    format_export = request.GET.get('format', 'pdf')

    # Récupérer toutes les locations (actives et terminées)
    toutes_locations = LocationBien.objects.filter(
        bien__sci=request.current_sci,
        montant_caution__isnull=False,
        date_versement_caution__isnull=False
    ).order_by('-date_versement_caution')

    # Date de début et fin : 01/01 au 31/12 de l'année sélectionnée
    date_debut_annee = date(annee_selectionnee, 1, 1)
    date_fin_annee = date(annee_selectionnee, 12, 31)

    # Cautions en cours au 31/12/annee_selectionnee
    # = Versées avant ou pendant l'année ET (pas encore restituées OU restituées après le 31/12)
    cautions_en_cours = toutes_locations.filter(
        date_versement_caution__lte=date_fin_annee
    ).filter(
        Q(date_restitution_caution__isnull=True) |
        Q(date_restitution_caution__gt=date_fin_annee)
    )

    # Cautions restituées UNIQUEMENT pendant l'année sélectionnée (entre 01/01 et 31/12)
    cautions_restituees = toutes_locations.filter(
        date_restitution_caution__gte=date_debut_annee,
        date_restitution_caution__lte=date_fin_annee
    )

    # Cautions encaissées pendant l'année sélectionnée
    cautions_encaissees_annee = toutes_locations.filter(
        date_versement_caution__gte=date_debut_annee,
        date_versement_caution__lte=date_fin_annee
    )

    # Cautions remboursées pendant l'année sélectionnée
    cautions_remboursees_annee = toutes_locations.filter(
        date_restitution_caution__gte=date_debut_annee,
        date_restitution_caution__lte=date_fin_annee
    )

    # Total détenu au 31/12/annee_selectionnee
    total_cautions_detenues = sum(l.montant_caution for l in cautions_en_cours if l.montant_caution)

    # Total détenu au 31/12/(annee_selectionnee-1)
    # = Total détenu actuellement - encaissé cette année + remboursé cette année
    total_cautions_debut_annee = total_cautions_detenues

    # Soustraire les cautions encaissées cette année
    for location in cautions_encaissees_annee:
        if location.montant_caution:
            total_cautions_debut_annee -= location.montant_caution

    # Ajouter les cautions remboursées cette année
    for location in cautions_remboursees_annee:
        if location.montant_caution:
            total_cautions_debut_annee += location.montant_caution

    # Calculer les totaux des montants
    total_encaisse_annee = sum(l.montant_caution for l in cautions_encaissees_annee if l.montant_caution)
    total_rembourse_annee = sum(l.montant_caution for l in cautions_remboursees_annee if l.montant_caution)

    # Préparer le contexte
    context = {
        'cautions_en_cours': cautions_en_cours,
        'cautions_restituees': cautions_restituees,
        'total_cautions_detenues': total_cautions_detenues,
        'total_cautions_debut_annee': total_cautions_debut_annee,
        'total_encaisse_annee': total_encaisse_annee,
        'total_rembourse_annee': total_rembourse_annee,
        'cautions_encaissees_annee': cautions_encaissees_annee,
        'cautions_remboursees_annee': cautions_remboursees_annee,
        'annee_selectionnee': annee_selectionnee,
        'date_edition': date.today().strftime('%d/%m/%Y'),
        'sci_nom': request.current_sci.nom
    }

    # Générer le rapport dans le format demandé
    if format_export == 'excel':
        return generer_excel_etat_cautions(request, context)
    else:
        return generer_pdf_etat_cautions(request, context)

def generer_excel_mouvements_locataires(request, context):
    """Génère un fichier Excel des mouvements de locataires"""
    import xlsxwriter

    buffer = io.BytesIO()
    workbook = xlsxwriter.Workbook(buffer)

    titre_format = workbook.add_format({
        'bold': True,
        'font_size': 14,
        'align': 'center',
        'valign': 'vcenter'
    })

    header_format = workbook.add_format({
        'bold': True,
        'bg_color': '#CCCCCC',
        'border': 1,
        'align': 'center',
        'valign': 'vcenter'
    })

    date_format = workbook.add_format({
        'num_format': 'dd/mm/yyyy',
        'align': 'center',
        'border': 1
    })

    cell_format = workbook.add_format({
        'border': 1,
        'align': 'center',
        'valign': 'vcenter'
    })

    left_format = workbook.add_format({
        'border': 1,
        'align': 'left',
        'valign': 'vcenter'
    })

    worksheet = workbook.add_worksheet("Mouvements")

    titre = f"Mouvements des locataires - {context['sci_nom']}"
    if 'annee_selectionnee' in context:
        titre += f" - Année {context['annee_selectionnee']}"

    worksheet.merge_range('A1:I1', titre, titre_format)
    worksheet.merge_range('A2:I2', f"Édité le {context['date_edition']}", cell_format)

    headers = [
        'Bien', 'Type', 'Ancien locataire', 'Date naissance', 'Lieu naissance',
        'Date entrée', 'Date sortie', 'Nouveau locataire', 'Date entrée'
    ]

    for col, header in enumerate(headers):
        worksheet.write(3, col, header, header_format)

    row = 4
    for m in context['mouvements']:
        bien_label = f"{m['bien'].numero_formate} - {m['bien'].adresse}" if m['bien'].numero else m['bien'].adresse
        worksheet.write(row, 0, bien_label, left_format)
        worksheet.write(row, 1, m['bien'].get_type_bien_display(), cell_format)
        worksheet.write(row, 2, f"{m['ancien_locataire'].nom} {m['ancien_locataire'].prenom}", left_format)

        if m['ancien_locataire'].date_naissance:
            worksheet.write_datetime(row, 3, m['ancien_locataire'].date_naissance, date_format)
        else:
            worksheet.write(row, 3, "-", cell_format)

        worksheet.write(row, 4, m['ancien_locataire'].lieu_naissance or "-", left_format)
        worksheet.write_datetime(row, 5, m['date_entree'], date_format)

        if m['date_sortie']:
            worksheet.write_datetime(row, 6, m['date_sortie'], date_format)
        else:
            worksheet.write(row, 6, "-", cell_format)

        if m['nouveau_locataire']:
            worksheet.write(row, 7, f"{m['nouveau_locataire'].nom} {m['nouveau_locataire'].prenom}", left_format)

            if m['nouvelle_date_entree']:
                worksheet.write_datetime(row, 8, m['nouvelle_date_entree'], date_format)
            else:
                worksheet.write(row, 8, "-", cell_format)
        else:
            worksheet.write(row, 7, "-", cell_format)
            worksheet.write(row, 8, "-", cell_format)

        row += 1

    active_sheet = workbook.add_worksheet("Locataires actifs")

    active_titre = f"Locataires actifs - {context['sci_nom']}"
    if 'annee_selectionnee' in context:
        active_titre += f" au 31/12/{context['annee_selectionnee']}"

    active_sheet.merge_range('A1:F1', active_titre, titre_format)
    active_sheet.merge_range('A2:F2', f"Édité le {context['date_edition']}", cell_format)

    active_headers = [
        'Bien', 'Type', 'Locataire', 'Date naissance', 'Lieu naissance', 'Date entrée'
    ]

    for col, header in enumerate(active_headers):
        active_sheet.write(3, col, header, header_format)

    active_row = 4
    for loc in context['locations_actives']:
        bien_label = f"{loc.bien.numero_formate} - {loc.bien.adresse}" if loc.bien.numero else loc.bien.adresse
        active_sheet.write(active_row, 0, bien_label, left_format)
        active_sheet.write(active_row, 1, loc.bien.get_type_bien_display(), cell_format)
        active_sheet.write(active_row, 2, f"{loc.locataire.nom} {loc.locataire.prenom}", left_format)

        if loc.locataire.date_naissance:
            active_sheet.write_datetime(active_row, 3, loc.locataire.date_naissance, date_format)
        else:
            active_sheet.write(active_row, 3, "-", cell_format)

        active_sheet.write(active_row, 4, loc.locataire.lieu_naissance or "-", left_format)
        active_sheet.write_datetime(active_row, 5, loc.date_entree, date_format)

        active_row += 1

    worksheet.set_column('A:A', 30)
    worksheet.set_column('B:B', 12)
    worksheet.set_column('C:C', 25)
    worksheet.set_column('D:D', 14)
    worksheet.set_column('E:E', 20)
    worksheet.set_column('F:F', 12)
    worksheet.set_column('G:G', 12)
    worksheet.set_column('H:H', 25)
    worksheet.set_column('I:I', 12)

    active_sheet.set_column('A:A', 30)
    active_sheet.set_column('B:B', 12)
    active_sheet.set_column('C:C', 25)
    active_sheet.set_column('D:D', 14)
    active_sheet.set_column('E:E', 20)
    active_sheet.set_column('F:F', 12)

    workbook.close()

    buffer.seek(0)
    response = HttpResponse(
        buffer,
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    safe_sci_nom = context['sci_nom'].replace(' ', '_').replace('/', '_').replace('\\', '_')

    if 'annee_selectionnee' in context:
        filename = f'mouvements_locataires_{safe_sci_nom}_{context["annee_selectionnee"]}.xlsx'
    else:
        filename = f'mouvements_locataires_{safe_sci_nom}_{date.today().strftime("%d-%m-%Y")}.xlsx'

    response['Content-Disposition'] = f'attachment; filename={filename}'

    return response

def generer_pdf_mouvements_locataires(request, context):
    """Génère un PDF des mouvements de locataires"""
    buffer = io.BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        leftMargin=1.5*cm,
        rightMargin=1.5*cm,
        topMargin=2*cm,
        bottomMargin=2*cm
    )

    elements = []
    styles = getSampleStyleSheet()

    titre_style = ParagraphStyle(
        'TitreMouvements',
        parent=styles['Heading1'],
        fontSize=16,
        alignment=TA_CENTER,
        spaceAfter=0.5*cm
    )

    date_style = ParagraphStyle(
        'DateMouvements',
        parent=styles['Normal'],
        fontSize=10,
        textColor=colors.grey,
        alignment=TA_CENTER,
        spaceAfter=0.8*cm
    )

    cell_style = ParagraphStyle(
        'CellStyle',
        parent=styles['Normal'],
        fontSize=9,
        leading=11,
        alignment=TA_CENTER
    )

    left_style = ParagraphStyle(
        'LeftStyle',
        parent=cell_style,
        alignment=TA_LEFT
    )

    header_style = ParagraphStyle(
        'HeaderStyle',
        parent=cell_style,
        fontName='Helvetica-Bold'
    )

    elements.append(Paragraph(f"Mouvements des locataires - {context['sci_nom']}", titre_style))

    if 'annee_selectionnee' in context:
        elements.append(Paragraph(f"Année {context['annee_selectionnee']}", date_style))

    elements.append(Paragraph(f"Édité le {context['date_edition']}", date_style))

    if context['mouvements']:
        data = [
            [
                Paragraph('<b>Bien</b>', header_style),
                Paragraph('<b>Type</b>', header_style),
                Paragraph('<b>Ancien locataire</b>', header_style),
                Paragraph('<b>Date naissance</b>', header_style),
                Paragraph('<b>Lieu naissance</b>', header_style),
                Paragraph('<b>Date entrée</b>', header_style),
                Paragraph('<b>Date sortie</b>', header_style),
                Paragraph('<b>Nouveau locataire</b>', header_style),
                Paragraph('<b>Date entrée</b>', header_style)
            ]
        ]

        for m in context['mouvements']:
            bien_label = f"{m['bien'].numero_formate} - {m['bien'].adresse}" if m['bien'].numero else m['bien'].adresse
            row = [
                Paragraph(bien_label, left_style),
                Paragraph(f"{m['bien'].get_type_bien_display()}", cell_style),
                Paragraph(f"{m['ancien_locataire'].nom} {m['ancien_locataire'].prenom}", left_style),
                Paragraph(f"{m['ancien_locataire'].date_naissance.strftime('%d/%m/%Y') if m['ancien_locataire'].date_naissance else '-'}", cell_style),
                Paragraph(f"{m['ancien_locataire'].lieu_naissance or '-'}", left_style),
                Paragraph(f"{m['date_entree'].strftime('%d/%m/%Y')}", cell_style),
                Paragraph(f"{m['date_sortie'].strftime('%d/%m/%Y') if m['date_sortie'] else '-'}", cell_style)
            ]

            if m['nouveau_locataire']:
                row.extend([
                    Paragraph(f"{m['nouveau_locataire'].nom} {m['nouveau_locataire'].prenom}", left_style),
                    Paragraph(f"{m['nouvelle_date_entree'].strftime('%d/%m/%Y') if m['nouvelle_date_entree'] else '-'}", cell_style)
                ])
            else:
                row.extend([
                    Paragraph("-", cell_style),
                    Paragraph("-", cell_style)
                ])

            data.append(row)

        col_widths = [
            doc.width * 0.18,
            doc.width * 0.08,
            doc.width * 0.15,
            doc.width * 0.09,
            doc.width * 0.12,
            doc.width * 0.09,
            doc.width * 0.09,
            doc.width * 0.15,
            doc.width * 0.09
        ]

        table = Table(data, colWidths=col_widths, repeatRows=1)

        style = TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.Color(0.9, 0.9, 0.9)),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            ('BOX', (0, 0), (-1, -1), 1, colors.black),
            ('LEFTPADDING', (0, 0), (-1, -1), 4),
            ('RIGHTPADDING', (0, 0), (-1, -1), 4),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6)
        ])

        for i in range(1, len(data), 2):
            style.add('BACKGROUND', (0, i), (-1, i), colors.Color(0.95, 0.95, 0.95))

        table.setStyle(style)
        elements.append(table)
    else:
        elements.append(Paragraph("Aucun mouvement de locataire trouvé.", styles['Normal']))

    elements.append(Spacer(1, 1*cm))
    elements.append(Paragraph("Locataires actifs", styles['Heading2']))

    if context['locations_actives']:
        active_data = [
            [
                Paragraph('<b>Bien</b>', header_style),
                Paragraph('<b>Type</b>', header_style),
                Paragraph('<b>Locataire</b>', header_style),
                Paragraph('<b>Date naissance</b>', header_style),
                Paragraph('<b>Lieu naissance</b>', header_style),
                Paragraph('<b>Date entrée</b>', header_style)
            ]
        ]

        for loc in context['locations_actives']:
            bien_label = f"{loc.bien.numero_formate} - {loc.bien.adresse}" if loc.bien.numero else loc.bien.adresse
            active_row = [
                Paragraph(bien_label, left_style),
                Paragraph(f"{loc.bien.get_type_bien_display()}", cell_style),
                Paragraph(f"{loc.locataire.nom} {loc.locataire.prenom}", left_style),
                Paragraph(f"{loc.locataire.date_naissance.strftime('%d/%m/%Y') if loc.locataire.date_naissance else '-'}", cell_style),
                Paragraph(f"{loc.locataire.lieu_naissance or '-'}", left_style),
                Paragraph(f"{loc.date_entree.strftime('%d/%m/%Y')}", cell_style)
            ]
            active_data.append(active_row)

        active_col_widths = [
            doc.width * 0.25,
            doc.width * 0.10,
            doc.width * 0.25,
            doc.width * 0.12,
            doc.width * 0.18,
            doc.width * 0.10
        ]

        active_table = Table(active_data, colWidths=active_col_widths, repeatRows=1)

        active_style = TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.Color(0.9, 0.9, 0.9)),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            ('BOX', (0, 0), (-1, -1), 1, colors.black),
            ('LEFTPADDING', (0, 0), (-1, -1), 4),
            ('RIGHTPADDING', (0, 0), (-1, -1), 4),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6)
        ])

        for i in range(1, len(active_data), 2):
            active_style.add('BACKGROUND', (0, i), (-1, i), colors.Color(0.95, 0.95, 0.95))

        active_table.setStyle(active_style)
        elements.append(active_table)
    else:
        elements.append(Paragraph("Aucun locataire actif trouvé.", styles['Normal']))

    doc.build(elements)

    buffer.seek(0)
    response = HttpResponse(buffer, content_type='application/pdf')
    safe_sci_nom = context['sci_nom'].replace(' ', '_').replace('/', '_').replace('\\', '_')

    if 'annee_selectionnee' in context:
        filename = f'mouvements_locataires_{safe_sci_nom}_{context["annee_selectionnee"]}.pdf'
    else:
        filename = f'mouvements_locataires_{safe_sci_nom}_{date.today().strftime("%d-%m-%Y")}.pdf'

    response['Content-Disposition'] = f'attachment; filename={filename}'

    return response

def generer_pdf_etat_cautions(request, context):
    """Génère un PDF de l'état des dépôts de garantie"""
    from reportlab.platypus import KeepTogether

    buffer = io.BytesIO()

    # Configuration du document
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=1.5*cm,
        rightMargin=1.5*cm,
        topMargin=2*cm,
        bottomMargin=2*cm
    )

    elements = []
    styles = getSampleStyleSheet()

    # Titre
    titre_style = ParagraphStyle(
        'TitreCautions',
        parent=styles['Heading1'],
        fontSize=16,
        alignment=TA_CENTER,
        spaceAfter=0.5*cm
    )

    # Date
    date_style = ParagraphStyle(
        'DateCautions',
        parent=styles['Normal'],
        fontSize=10,
        textColor=colors.grey,
        alignment=TA_CENTER,
        spaceAfter=0.8*cm
    )

    # Styles de cellules
    cell_style = ParagraphStyle(
        'CellStyle',
        parent=styles['Normal'],
        fontSize=9,
        leading=11,
        alignment=TA_CENTER
    )

    left_style = ParagraphStyle(
        'LeftStyle',
        parent=cell_style,
        alignment=TA_LEFT
    )

    right_style = ParagraphStyle(
        'RightStyle',
        parent=cell_style,
        alignment=TA_RIGHT
    )

    header_style = ParagraphStyle(
        'HeaderStyle',
        parent=cell_style,
        fontName='Helvetica-Bold'
    )

    # Ajouter titre et date
    elements.append(Paragraph(f"État des dépôts de garantie - {context['sci_nom']}", titre_style))
    elements.append(Paragraph(f"Édité le {context['date_edition']}", date_style))

    # Tableau récapitulatif
    annee = context['annee_selectionnee']

    recap_data = [
        [
            Paragraph(f'<b>Total dépôts de garantie détenus au 31/12/{annee-1}</b>', header_style),
            Paragraph(f'<b>Dépôts de garantie encaissés en {annee}</b>', header_style),
            Paragraph(f'<b>Dépôts de garantie remboursés en {annee}</b>', header_style),
            Paragraph(f'<b>Total dépôts de garantie détenus au 31/12/{annee}</b>', header_style)
        ],
        [
            Paragraph(f"{context['total_cautions_debut_annee']:.2f}\u00A0€", right_style),
            Paragraph(f"{context['total_encaisse_annee']:.2f}\u00A0€", right_style),
            Paragraph(f"{context['total_rembourse_annee']:.2f}\u00A0€", right_style),
            Paragraph(f"{context['total_cautions_detenues']:.2f}\u00A0€", right_style)
        ]
    ]

    # Définir les largeurs des colonnes du tableau récapitulatif
    recap_col_widths = [doc.width/4] * 4

    # Créer le tableau récapitulatif
    recap_table = Table(recap_data, colWidths=recap_col_widths)

    # Style du tableau récapitulatif
    recap_style = TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.Color(0.9, 0.9, 0.9)),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ('BOX', (0, 0), (-1, -1), 1, colors.black),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6)
    ])

    recap_table.setStyle(recap_style)
    elements.append(recap_table)
    elements.append(Spacer(1, 0.5*cm))

    # Tableau des dépôts de garantie en cours
    elements.append(Paragraph("Dépôts de garantie en cours", styles['Heading2']))
    elements.append(Spacer(1, 0.3*cm))

    if context['cautions_en_cours']:
        current_data = [
            [
                Paragraph('<b>Locataire</b>', header_style),
                Paragraph('<b>Bien</b>', header_style),
                Paragraph('<b>Montant</b>', header_style),
                Paragraph('<b>Date versement</b>', header_style),
                Paragraph('<b>Statut</b>', header_style)
            ]
        ]

        for c in context['cautions_en_cours']:
            row = [
                Paragraph(f"{c.locataire.nom} {c.locataire.prenom}", left_style),
                Paragraph(f"{c.bien.adresse}", left_style),
                Paragraph(f"{c.montant_caution:.2f}\u00A0€", right_style),
                Paragraph(f"{c.date_versement_caution.strftime('%d/%m/%Y')}", cell_style),
                Paragraph("En cours", cell_style)
            ]
            current_data.append(row)

        # Définir les largeurs des colonnes
        current_col_widths = [
            doc.width * 0.25,
            doc.width * 0.35,
            doc.width * 0.15,
            doc.width * 0.15,
            doc.width * 0.10
        ]

        # Créer le tableau
        current_table = Table(current_data, colWidths=current_col_widths, repeatRows=1)

        # Style du tableau (SANS COULEURS de mise en évidence)
        current_style = TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.Color(0.9, 0.9, 0.9)),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            ('BOX', (0, 0), (-1, -1), 1, colors.black),
            ('LEFTPADDING', (0, 0), (-1, -1), 4),
            ('RIGHTPADDING', (0, 0), (-1, -1), 4),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6)
        ])

        # Lignes alternées UNIQUEMENT (gris clair)
        for i in range(1, len(current_data)):
            if i % 2 == 0:
                current_style.add('BACKGROUND', (0, i), (-1, i), colors.Color(0.95, 0.95, 0.95))

        current_table.setStyle(current_style)
        elements.append(current_table)
    else:
        elements.append(Paragraph("Aucun dépôt de garantie en cours.", styles['Normal']))

    # Créer un groupe pour le titre et le tableau des dépôts restitués
    elements.append(Spacer(1, 0.5*cm))

    returned_elements = []
    returned_elements.append(Paragraph("Dépôts de garantie restitués", styles['Heading2']))
    returned_elements.append(Spacer(1, 0.3*cm))

    if context['cautions_restituees']:
        returned_data = [
            [
                Paragraph('<b>Locataire</b>', header_style),
                Paragraph('<b>Bien</b>', header_style),
                Paragraph('<b>Montant</b>', header_style),
                Paragraph('<b>Date versement</b>', header_style),
                Paragraph('<b>Date restitution</b>', header_style)
            ]
        ]

        for c in context['cautions_restituees']:
            row = [
                Paragraph(f"{c.locataire.nom} {c.locataire.prenom}", left_style),
                Paragraph(f"{c.bien.adresse}", left_style),
                Paragraph(f"{c.montant_caution:.2f}\u00A0€", right_style),
                Paragraph(f"{c.date_versement_caution.strftime('%d/%m/%Y')}", cell_style),
                Paragraph(f"{c.date_restitution_caution.strftime('%d/%m/%Y')}", cell_style)
            ]
            returned_data.append(row)

        # Définir les largeurs des colonnes
        returned_col_widths = [
            doc.width * 0.25,
            doc.width * 0.30,
            doc.width * 0.15,
            doc.width * 0.15,
            doc.width * 0.15
        ]

        # Créer le tableau
        returned_table = Table(returned_data, colWidths=returned_col_widths, repeatRows=1)

        # Style du tableau (SANS COULEURS de mise en évidence)
        returned_style = TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.Color(0.9, 0.9, 0.9)),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            ('BOX', (0, 0), (-1, -1), 1, colors.black),
            ('LEFTPADDING', (0, 0), (-1, -1), 4),
            ('RIGHTPADDING', (0, 0), (-1, -1), 4),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6)
        ])

        # Lignes alternées UNIQUEMENT (gris clair)
        for i in range(1, len(returned_data)):
            if i % 2 == 0:
                returned_style.add('BACKGROUND', (0, i), (-1, i), colors.Color(0.95, 0.95, 0.95))

        returned_table.setStyle(returned_style)
        returned_elements.append(returned_table)
    else:
        returned_elements.append(Paragraph("Aucun dépôt de garantie restitué.", styles['Normal']))

    # Utiliser KeepTogether pour garder le titre et le tableau sur la même page
    elements.append(KeepTogether(returned_elements))

    # Générer le PDF
    doc.build(elements)

    # Préparer la réponse
    buffer.seek(0)
    response = HttpResponse(buffer, content_type='application/pdf')
    safe_sci_nom = context['sci_nom'].replace(' ', '_').replace('/', '_').replace('\\', '_')
    response['Content-Disposition'] = f'attachment; filename=etat_depots_garantie_{safe_sci_nom}_{context["annee_selectionnee"]}.pdf'

    return response

def generer_excel_etat_cautions(request, context):
    """Génère un fichier Excel de l'état des dépôts de garantie"""
    import xlsxwriter

    # Créer un buffer pour stocker le fichier Excel
    buffer = io.BytesIO()

    # Créer un nouveau classeur Excel
    workbook = xlsxwriter.Workbook(buffer)

    # Styles
    titre_format = workbook.add_format({
        'bold': True,
        'font_size': 14,
        'align': 'center',
        'valign': 'vcenter'
    })

    header_format = workbook.add_format({
        'bold': True,
        'bg_color': '#CCCCCC',
        'border': 1,
        'align': 'center',
        'valign': 'vcenter'
    })

    date_format = workbook.add_format({
        'num_format': 'dd/mm/yyyy',
        'align': 'center',
        'border': 1
    })

    cell_format = workbook.add_format({
        'border': 1,
        'align': 'center',
        'valign': 'vcenter'
    })

    left_format = workbook.add_format({
        'border': 1,
        'align': 'left',
        'valign': 'vcenter'
    })

    money_format = workbook.add_format({
        'border': 1,
        'align': 'right',
        'valign': 'vcenter',
        'num_format': '0.00 €'
    })

    # Créer la feuille "Récapitulatif"
    recap_sheet = workbook.add_worksheet("Récapitulatif")

    # Titre et date
    recap_sheet.merge_range('A1:D1', f"État des dépôts de garantie - {context['sci_nom']}", titre_format)
    recap_sheet.merge_range('A2:D2', f"Édité le {context['date_edition']}", cell_format)

    # En-têtes
    annee = context['annee_selectionnee']
    recap_headers = [
        f"Total dépôts de garantie détenus au 31/12/{annee-1}",
        f"Dépôts de garantie encaissés en {annee}",
        f"Dépôts de garantie remboursés en {annee}",
        f"Total dépôts de garantie détenus au 31/12/{annee}"
    ]

    for col, header in enumerate(recap_headers):
        recap_sheet.write(3, col, header, header_format)

    # Données récapitulatives
    recap_sheet.write_number(4, 0, context['total_cautions_debut_annee'], money_format)
    recap_sheet.write_number(4, 1, context['total_encaisse_annee'], money_format)
    recap_sheet.write_number(4, 2, context['total_rembourse_annee'], money_format)
    recap_sheet.write_number(4, 3, context['total_cautions_detenues'], money_format)

    # Créer la feuille "Dépôts en cours"
    current_sheet = workbook.add_worksheet("Dépôts en cours")

    # Titre et date
    current_sheet.merge_range('A1:E1', f"Dépôts de garantie en cours - {context['sci_nom']}", titre_format)
    current_sheet.merge_range('A2:E2', f"Édité le {context['date_edition']}", cell_format)

    # En-têtes
    current_headers = [
        'Locataire', 'Bien', 'Montant', 'Date versement', 'Statut'
    ]

    for col, header in enumerate(current_headers):
        current_sheet.write(3, col, header, header_format)

    # Données des dépôts en cours
    current_row = 4
    for c in context['cautions_en_cours']:
        current_sheet.write(current_row, 0, f"{c.locataire.nom} {c.locataire.prenom}", left_format)
        current_sheet.write(current_row, 1, c.bien.adresse, left_format)
        current_sheet.write_number(current_row, 2, c.montant_caution, money_format)
        current_sheet.write_datetime(current_row, 3, c.date_versement_caution, date_format)
        current_sheet.write(current_row, 4, "En cours", cell_format)

        current_row += 1

    # Créer la feuille "Dépôts restitués"
    returned_sheet = workbook.add_worksheet("Dépôts restitués")

    # Titre et date
    returned_sheet.merge_range('A1:E1', f"Dépôts de garantie restitués - {context['sci_nom']}", titre_format)
    returned_sheet.merge_range('A2:E2', f"Édité le {context['date_edition']}", cell_format)

    # En-têtes
    returned_headers = [
        'Locataire', 'Bien', 'Montant', 'Date versement', 'Date restitution'
    ]

    for col, header in enumerate(returned_headers):
        returned_sheet.write(3, col, header, header_format)

    # Données des dépôts restitués
    returned_row = 4
    for c in context['cautions_restituees']:
        returned_sheet.write(returned_row, 0, f"{c.locataire.nom} {c.locataire.prenom}", left_format)
        returned_sheet.write(returned_row, 1, c.bien.adresse, left_format)
        returned_sheet.write_number(returned_row, 2, c.montant_caution, money_format)
        returned_sheet.write_datetime(returned_row, 3, c.date_versement_caution, date_format)
        returned_sheet.write_datetime(returned_row, 4, c.date_restitution_caution, date_format)

        returned_row += 1

    # Ajuster les largeurs des colonnes
    recap_sheet.set_column('A:D', 35)
    current_sheet.set_column('A:A', 25)
    current_sheet.set_column('B:B', 40)
    current_sheet.set_column('C:E', 15)
    returned_sheet.set_column('A:A', 25)
    returned_sheet.set_column('B:B', 40)
    returned_sheet.set_column('C:E', 15)

    # Fermer le classeur
    workbook.close()

    # Préparer la réponse
    buffer.seek(0)
    response = HttpResponse(
        buffer,
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    safe_sci_nom = context['sci_nom'].replace(' ', '_').replace('/', '_').replace('\\', '_')
    response['Content-Disposition'] = f'attachment; filename=etat_depots_garantie_{safe_sci_nom}_{context["annee_selectionnee"]}.xlsx'

    return response

def historique_frais_bien(request):
    """Vue pour afficher l'historique des frais associés à un bien - OPTIMISÉE"""
    biens = Bien.objects.filter(sci=request.current_sci).order_by('adresse')

    bien_id = request.GET.get('bien_id')
    transactions = []
    bien_selectionne = None
    total_frais = 0

    if bien_id:
        try:
            bien_selectionne = Bien.objects.get(id=bien_id, sci=request.current_sci)

            transactions = Transaction.objects.filter(
                bien=bien_selectionne,
                type_transaction__categorie='DEPENSE'
            ).select_related(
                'type_transaction',
                'bien',
                'locataire',
                'sci'
            ).order_by('-date')

            total_frais = transactions.aggregate(Sum('montant'))['montant__sum'] or 0

        except Bien.DoesNotExist:
            pass

    context = {
        'biens': biens,
        'bien_selectionne': bien_selectionne,
        'transactions': transactions,
        'total_frais': total_frais,
    }

    return render(request, 'principale/historique_frais_bien.html', context)

def gestion_om(request):
    """Vue pour gérer les montants attendus des ordures ménagères par locataire/bien/année"""

    annee_courante = date.today().year
    annee_selectionnee = request.GET.get('annee', annee_courante)
    try:
        annee_selectionnee = int(annee_selectionnee)
    except ValueError:
        annee_selectionnee = annee_courante

    annees_disponibles = range(2025, annee_courante + 1)

    locataires_actifs = Locataire.objects.filter(
        biens__sci=request.current_sci,
        locations__date_sortie__isnull=True
    ).distinct().order_by('nom', 'prenom')

    if request.method == 'POST':
        nb_modifs = 0
        for key, value in request.POST.items():
            if key.startswith('montant_'):
                parts = key.split('_')
                if len(parts) == 3:
                    try:
                        locataire_id = int(parts[1])
                        bien_id = int(parts[2])
                        montant_str = value.strip().replace(',', '.')

                        if montant_str == '':
                            MontantOM.objects.filter(
                                sci=request.current_sci,
                                locataire_id=locataire_id,
                                bien_id=bien_id,
                                annee=annee_selectionnee
                            ).delete()
                        else:
                            montant = decimal.Decimal(montant_str)
                            MontantOM.objects.update_or_create(
                                sci=request.current_sci,
                                locataire_id=locataire_id,
                                bien_id=bien_id,
                                annee=annee_selectionnee,
                                defaults={'montant_attendu': montant}
                            )
                            nb_modifs += 1
                    except (ValueError, decimal.InvalidOperation):
                        pass

        messages.success(request, f"Les montants OM ont été enregistrés ({nb_modifs} montant(s) mis à jour).")
        return redirect(f"{reverse('gestion_om')}?annee={annee_selectionnee}")

    tableau_om = []

    for locataire in locataires_actifs:
        biens_locataire = locataire.biens.filter(sci=request.current_sci)

        for bien in biens_locataire:
            location = LocationBien.objects.filter(
                locataire=locataire,
                bien=bien,
                date_sortie__isnull=True
            ).first()

            if not location:
                continue

            montant_om = MontantOM.objects.filter(
                sci=request.current_sci,
                locataire=locataire,
                bien=bien,
                annee=annee_selectionnee
            ).first()

            montant_attendu = montant_om.montant_attendu if montant_om else None

            paiements_om = Transaction.objects.filter(
                locataire=locataire,
                bien=bien,
                type_transaction__nom__icontains='OM',
                type_transaction__categorie='RECETTE',
                mois_concerne__year=annee_selectionnee
            )
            montant_paye = sum(p.montant for p in paiements_om)

            if montant_attendu is None:
                statut = "Non défini"
            elif montant_attendu == 0 or montant_paye >= montant_attendu:
                statut = "OK"
            elif montant_paye > 0:
                statut = "Partiel"
            else:
                statut = "Non payé"

            if montant_attendu is not None:
                reste = max(montant_attendu - decimal.Decimal(str(montant_paye)), decimal.Decimal('0'))
            else:
                reste = None

            tableau_om.append({
                'locataire': locataire,
                'bien': bien,
                'montant_attendu': montant_attendu,
                'montant_paye': montant_paye,
                'reste_a_payer': reste,
                'statut': statut,
                'field_name': f"montant_{locataire.id}_{bien.id}",
            })

    context = {
        'tableau_om': tableau_om,
        'annee_selectionnee': annee_selectionnee,
        'annees_disponibles': annees_disponibles,
        'save_om_url': '/ordures-menageres/save/',
    }

    return render(request, 'principale/gestion_om.html', context)

def save_montant_om(request):
    """Endpoint AJAX pour enregistrer un montant OM à la saisie"""
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'Méthode non autorisée'}, status=405)

    field_name = request.POST.get('field_name', '')
    value = request.POST.get('value', '').strip().replace(',', '.')
    annee_str = request.POST.get('annee', '')

    try:
        annee = int(annee_str)
    except ValueError:
        return JsonResponse({'ok': False, 'error': 'Année invalide'}, status=400)

    parts = field_name.split('_')
    if len(parts) != 3 or parts[0] != 'montant':
        return JsonResponse({'ok': False, 'error': 'Champ invalide'}, status=400)

    try:
        locataire_id = int(parts[1])
        bien_id = int(parts[2])
    except ValueError:
        return JsonResponse({'ok': False, 'error': 'Identifiants invalides'}, status=400)
    
    try:
        if value == '':
            MontantOM.objects.filter(
                sci=request.current_sci,
                locataire_id=locataire_id,
                bien_id=bien_id,
                annee=annee
            ).delete()
        else:
            montant = decimal.Decimal(value)
            MontantOM.objects.update_or_create(
                sci=request.current_sci,
                locataire_id=locataire_id,
                bien_id=bien_id,
                annee=annee,
                defaults={'montant_attendu': montant}
            )
    except (ValueError, decimal.InvalidOperation):
        return JsonResponse({'ok': False, 'error': 'Montant invalide'}, status=400)
    return JsonResponse({'ok': True})