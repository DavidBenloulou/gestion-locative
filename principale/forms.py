from django import forms
from django.core.exceptions import ValidationError
from .models import Bien, Locataire, Transaction, LocationBien, TypeTransaction

class BienForm(forms.ModelForm):
    class Meta:
        model = Bien
        fields = ['type_bien', 'adresse', 'code_postal', 'ville', 'loyer_mensuel', 'montant_charges', 'montant_caution', 'numero']
        widgets = {
            'type_bien': forms.Select(attrs={'class': 'form-select'}),
            'adresse': forms.TextInput(attrs={'class': 'form-control'}),
            'code_postal': forms.TextInput(attrs={'class': 'form-control'}),
            'ville': forms.TextInput(attrs={'class': 'form-control'}),
            'loyer_mensuel': forms.NumberInput(attrs={'class': 'form-control'}),
            'montant_charges': forms.NumberInput(attrs={'class': 'form-control'}),
            'montant_caution': forms.NumberInput(attrs={'class': 'form-control'}),
            'numero': forms.TextInput(attrs={'class': 'form-control'}),
        }
# Modifications dans forms.py

class LocataireForm(forms.ModelForm):
    class Meta:
        model = Locataire
        # Inclure les nouveaux champs
        fields = [
            'nom', 'prenom', 'date_naissance', 'lieu_naissance',
            'telephone', 'telephone_portable', 'email',
            'adresse', 'code_postal', 'ville'
        ]

        widgets = {
            'nom': forms.TextInput(attrs={'class': 'form-control'}),
            'prenom': forms.TextInput(attrs={'class': 'form-control'}),
            'date_naissance': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'lieu_naissance': forms.TextInput(attrs={'class': 'form-control'}),
            'telephone': forms.TextInput(attrs={'class': 'form-control'}),
            'telephone_portable': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'adresse': forms.TextInput(attrs={'class': 'form-control'}),
            'code_postal': forms.TextInput(attrs={'class': 'form-control'}),
            'ville': forms.TextInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        sci = kwargs.pop('sci', None)
        super().__init__(*args, **kwargs)

        if self.instance.pk and self.instance.date_naissance:
            self.initial['date_naissance'] = self.instance.date_naissance.strftime('%Y-%m-%d')

class TransactionForm(forms.ModelForm):
    sci_transaction = forms.BooleanField(
        label="Transaction liée à la SCI",
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )

    bien_specifique = forms.ModelChoiceField(
        queryset=Bien.objects.none(),
        label="Bien concerné",
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    # Champ pour les transactions de travaux
    bien = forms.ModelChoiceField(
        queryset=Bien.objects.none(),
        label="Bien concerné par les travaux",
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    # Nouveau champ pour l'année concernée (ordures ménagères)
    annee_concernee = forms.ChoiceField(
        label="Année concernée",
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    class Meta:
        model = Transaction
        fields = ['type_transaction', 'locataire', 'montant', 'date', 'mois_concerne', 'description']
        widgets = {
            'type_transaction': forms.Select(attrs={'class': 'form-select'}),
            'locataire': forms.Select(attrs={'class': 'form-select'}),
            'montant': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'mois_concerne': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        from datetime import date as date_class

        # Récupérer current_sci du contexte
        current_sci = kwargs.pop('current_sci', None)

        # Initialiser le formulaire
        super().__init__(*args, **kwargs)

        # Générer les choix pour annee_concernee (de 2024 à année courante + 1)
        annee_courante = date_class.today().year
        choix_annees = [('', '---------')]
        for annee in range(annee_courante + 1, 2023, -1):
            choix_annees.append((str(annee), str(annee)))
        self.fields['annee_concernee'].choices = choix_annees

        # Ordonner les types de transactions par catégorie puis par nom
        self.fields['type_transaction'].queryset = TypeTransaction.objects.order_by('categorie', 'nom')

        # Filtrer les locataires de la SCI
        if current_sci:
            self.fields['locataire'].queryset = Locataire.objects.filter(
                biens__sci=current_sci
            ).distinct().order_by('nom', 'prenom')

            # Ajouter queryset pour le champ bien (travaux)
            biens_queryset = Bien.objects.filter(sci=current_sci)
            self.fields['bien'].queryset = biens_queryset
            self.fields['bien'].label_from_instance = lambda obj: f"{obj.get_type_bien_display()} - {obj.numero + ' - ' if obj.numero else ''}{obj.adresse}"

        # Rendre les champs non obligatoires
        self.fields['locataire'].required = False
        self.fields['mois_concerne'].required = False

        # Pour les instances existantes, conserver les dates
        if self.instance.pk:
            if self.instance.date:
                self.initial['date'] = self.instance.date.strftime('%Y-%m-%d')
            if self.instance.mois_concerne:
                self.initial['mois_concerne'] = self.instance.mois_concerne.strftime('%Y-%m-%d')

                # Si c'est une transaction OM, pré-remplir annee_concernee
                if self.instance.type_transaction and 'om' in self.instance.type_transaction.nom.lower():
                    self.initial['annee_concernee'] = str(self.instance.mois_concerne.year)

            # Si l'instance a un bien, l'initialiser dans le champ bien
            if self.instance.bien:
                self.initial['bien'] = self.instance.bien

        # Modification clé : charger les biens du locataire
        locataire = None

        # Vérifier s'il y a un locataire dans les données POST
        if 'locataire' in self.data:
            try:
                locataire_id = int(self.data.get('locataire'))
                locataire = Locataire.objects.get(id=locataire_id)
            except (ValueError, TypeError, Locataire.DoesNotExist):
                locataire = None

        # Si pas de locataire dans POST, vérifier l'instance existante
        if not locataire and self.instance.pk and self.instance.locataire:
            locataire = self.instance.locataire

        # Si un locataire est trouvé, charger ses biens
        if locataire:
            biens_locataire = locataire.biens.all()
            self.fields['bien_specifique'].queryset = biens_locataire

            # Gérer la visibilité et l'obligation du champ bien_specifique
            if biens_locataire.count() > 1:
                self.fields['bien_specifique'].required = True
                # Pré-sélectionner le bien existant lors d'une modification
                if self.instance.pk and self.instance.bien:
                    self.initial['bien_specifique'] = self.instance.bien
            else:
                self.fields['bien_specifique'].required = False
                if biens_locataire.count() == 1:
                    self.initial['bien_specifique'] = biens_locataire.first()

    def clean(self):
        from datetime import date as date_class

        cleaned_data = super().clean()
        locataire = cleaned_data.get('locataire')
        sci_transaction = cleaned_data.get('sci_transaction')
        bien_specifique = cleaned_data.get('bien_specifique')
        bien = cleaned_data.get('bien')
        type_transaction = cleaned_data.get('type_transaction')
        annee_concernee = cleaned_data.get('annee_concernee')

        # Si c'est une transaction OM avec une année concernée, créer la date mois_concerne
        if type_transaction and 'om' in type_transaction.nom.lower() and annee_concernee:
            try:
                annee = int(annee_concernee)
                cleaned_data['mois_concerne'] = date_class(annee, 1, 1)
            except (ValueError, TypeError):
                pass

        # Validation de base
        if not sci_transaction and not locataire and not (type_transaction and 'travaux' in type_transaction.nom.lower()):
            raise ValidationError({
                'locataire': 'Vous devez sélectionner un locataire ou cocher "Transaction liée à la SCI" pour les transactions non-travaux.',
            })

        # Si c'est une transaction travaux sans locataire ni SCI, le bien est optionnel
        if type_transaction and 'travaux' in type_transaction.nom.lower() and not sci_transaction and not locataire:
            pass
        # Si locataire avec plusieurs biens
        elif locataire and locataire.biens.count() > 1 and not sci_transaction:
            if not bien_specifique:
                raise ValidationError({
                    'bien_specifique': 'Vous devez sélectionner un bien pour ce locataire qui en possède plusieurs.'
                })

        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)

        # Logique pour transaction SCI
        if self.cleaned_data.get('sci_transaction'):
            instance.bien = None
            instance.locataire = None
        else:
            # Pour les transactions de travaux
            type_transaction = self.cleaned_data.get('type_transaction')
            if type_transaction and 'travaux' in type_transaction.nom.lower():
                instance.bien = self.cleaned_data.get('bien')
                instance.locataire = self.cleaned_data.get('locataire')
            # Pour les autres transactions avec locataire
            elif instance.locataire:
                bien_specifique = self.cleaned_data.get('bien_specifique')
                instance.bien = bien_specifique or instance.locataire.biens.first()

        # Si c'est une transaction OM, appliquer l'année concernée dans mois_concerne
        if self.cleaned_data.get('mois_concerne') and self.cleaned_data.get('annee_concernee'):
            instance.mois_concerne = self.cleaned_data['mois_concerne']

        if commit:
            instance.save()

        return instance


class LocationBienForm(forms.ModelForm):
    class Meta:
        model = LocationBien
        fields = [
            'bien', 'date_entree', 'date_sortie'
        ]
        widgets = {
            'bien': forms.Select(attrs={'class': 'form-select'}),
            'date_entree': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'date_sortie': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        # Extraire sci des kwargs
        sci = kwargs.pop('sci', None)
        locataire = kwargs.pop('locataire', None)
        vacant_only = kwargs.pop('vacant_only', False)

        # Appeler le constructeur parent
        super().__init__(*args, **kwargs)

        # Filtrer les biens en fonction de la SCI
        if sci:
            if vacant_only and not self.instance.pk:
                biens_occupes = LocationBien.objects.filter(
                    bien__sci=sci,
                    date_sortie__isnull=True
                ).values_list('bien_id', flat=True)

                queryset = Bien.objects.filter(sci=sci).exclude(id__in=biens_occupes)
                print(f"Biens vacants pour SCI {sci.id}: {queryset.count()}")
            else:
                queryset = Bien.objects.filter(sci=sci)
                print(f"Biens disponibles pour SCI {sci.id}: {queryset.count()}")

            self.fields['bien'].queryset = queryset

            # Personnalisation de l'affichage avec le numéro entre le type et l'adresse
            self.fields['bien'].label_from_instance = lambda obj: f"{obj.get_type_bien_display()} - {obj.adresse} - {obj.numero}" if obj.numero else f"{obj.get_type_bien_display()} - {obj.adresse}"
        else:
            print("Aucune SCI fournie pour filtrer les biens")

        # Désactiver explicitement les attributs readonly et disabled
        for field_name, field in self.fields.items():
            if hasattr(field.widget, 'attrs'):
                field.widget.attrs.pop('readonly', None)
                field.widget.attrs.pop('disabled', None)

        # Si c'est une instance existante, initialiser le bien et les dates
        if self.instance.pk:
            # Initialiser le bien
            if self.instance.bien:
                self.initial['bien'] = self.instance.bien

            # Formater les dates pour le widget HTML5 date
            date_fields = [
                'date_entree',
                'date_sortie',
                'date_versement_caution',
                'date_restitution_caution'
            ]
            for field in date_fields:
                date_value = getattr(self.instance, field)
                if date_value:
                    self.initial[field] = date_value.strftime('%Y-%m-%d')

    def clean_bien(self):
        bien = self.cleaned_data.get('bien')
        # Si c'est une modification existante
        if self.instance.pk:
            # Vérifier que le bien n'a pas changé
            if bien != self.instance.bien:
                raise forms.ValidationError("Vous ne pouvez pas changer le bien lors de la modification.")
        else:
            # Pour l'ajout, vérifier que le bien est disponible
            locations_actives = LocationBien.objects.filter(
                bien=bien,
                date_sortie__isnull=True
            )
            if locations_actives.exists():
                raise forms.ValidationError("Ce bien est déjà occupé.")
        return bien