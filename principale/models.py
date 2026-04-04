from django.db import models

class SCI(models.Model):
    """Modèle pour représenter différentes SCI"""
    nom = models.CharField(max_length=100, verbose_name="Nom de la SCI")
    adresse = models.CharField(max_length=200, verbose_name="Adresse")
    code_postal = models.CharField(max_length=10, verbose_name="Code postal")
    ville = models.CharField(max_length=100, verbose_name="Ville")
    representants = models.CharField(max_length=200, verbose_name="Représentants")
    titre_representants = models.CharField(max_length=100, verbose_name="Titre des représentants")

    class Meta:
        verbose_name = "SCI"
        verbose_name_plural = "SCIs"
        ordering = ['nom']

    def __str__(self):
        return self.nom


class Bien(models.Model):
    """Modèle pour les biens immobiliers (appartements ou maisons)"""
    TYPE_CHOICES = [
        ('LOGEMENT', 'Logement'),
        ('PARKING', 'Parking'),
        ('COMMERCE', 'Commerce'),
    ]
    sci = models.ForeignKey(SCI, on_delete=models.CASCADE, related_name='biens', null=True, db_index=True)  # ← INDEX AJOUTÉ
    type_bien = models.CharField(max_length=20, choices=TYPE_CHOICES, db_index=True)  # ← INDEX AJOUTÉ
    adresse = models.CharField(max_length=255)
    code_postal = models.CharField(max_length=10)
    ville = models.CharField(max_length=100, db_index=True)  # ← INDEX AJOUTÉ
    loyer_mensuel = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Loyer hors charges")
    montant_charges = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="Montant des charges")
    montant_caution = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="Montant de la caution")
    numero = models.CharField(max_length=50, blank=True, null=True)

    class Meta:
        indexes = [
            models.Index(fields=['sci', 'type_bien']),  # ← INDEX COMPOSITE AJOUTÉ
            models.Index(fields=['ville']),  # ← INDEX AJOUTÉ
        ]

    @property
    def numero_formate(self):
        """Retourne le numéro formaté avec préfixe selon le type de bien"""
        if not self.numero:
            return ""
        if self.type_bien == 'PARKING':
            return f"N°{self.numero}"
        else:
            return f"Apt {self.numero}"

    def __str__(self):
        if self.numero:
            return f"{self.numero_formate} - {self.adresse}, {self.ville}"
        return f"{self.adresse}, {self.ville}"


class Locataire(models.Model):
    nom = models.CharField(max_length=100)
    prenom = models.CharField(max_length=100)
    date_naissance = models.DateField(null=True, blank=True, verbose_name="Date de naissance")
    lieu_naissance = models.CharField(max_length=100, blank=True, null=True, verbose_name="Lieu de naissance")
    telephone = models.CharField(max_length=20, blank=True, null=True)
    telephone_portable = models.CharField(max_length=15, blank=True, null=True, verbose_name="Téléphone portable")
    email = models.EmailField(blank=True, null=True)
    adresse = models.CharField(max_length=255, blank=True, null=True, verbose_name="Adresse")
    code_postal = models.CharField(max_length=10, blank=True, null=True, verbose_name="Code postal")
    ville = models.CharField(max_length=100, blank=True, null=True, verbose_name="Ville")
    biens = models.ManyToManyField(Bien, blank=True, related_name='locataires')
    sci = models.ForeignKey(SCI, on_delete=models.CASCADE, related_name='locataires', null=True, db_index=True)  # ← INDEX AJOUTÉ

    # On garde ces champs pour la caution pour le moment
    caution_versee = models.BooleanField(default=False, verbose_name="Caution versée")
    montant_caution = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="Montant de la caution")
    date_versement_caution = models.DateField(null=True, blank=True, verbose_name="Date de versement de la caution")
    date_restitution_caution = models.DateField(null=True, blank=True, verbose_name="Date de restitution de la caution")

    def __str__(self):
        return f"{self.nom} {self.prenom}"

    # Propriétés calculées pour remplacer les champs de date
    @property
    def date_entree(self):
        """Retourne la date d'entrée la plus ancienne parmi toutes les locations"""
        location = self.locations.all().order_by('date_entree').first()
        return location.date_entree if location else None

    @property
    def date_sortie(self):
        """Retourne la date de sortie la plus récente si toutes les locations sont terminées,
        sinon None (car le locataire est toujours présent)"""
        # Si au moins une location est active (sans date de sortie), le locataire est toujours présent
        if self.locations.filter(date_sortie__isnull=True).exists():
            return None

        # Sinon, retourner la date de sortie la plus récente
        location = self.locations.filter(date_sortie__isnull=False).order_by('-date_sortie').first()
        return location.date_sortie if location else None

    @property
    def is_actif(self):
        """Retourne True si le locataire a au moins une location active"""
        return self.locations.filter(date_sortie__isnull=True).exists()

    # Propriété pour compatibilité avec l'ancien code
    @property
    def bien(self):
        """Retourne le premier bien associé pour compatibilité avec l'ancien code"""
        return self.biens.first()


class TypeTransaction(models.Model):
    """Modèle pour les types de transactions (recettes et dépenses)"""
    NOM_CHOICES = [
        ('RECETTE', 'Recette'),
        ('DEPENSE', 'Dépense'),
    ]

    nom = models.CharField(max_length=100)
    categorie = models.CharField(max_length=20, choices=NOM_CHOICES)

    def __str__(self):
        return f"{self.get_categorie_display()} - {self.nom}"


class Transaction(models.Model):
    """Modèle pour les transactions financières (recettes et dépenses)"""
    type_transaction = models.ForeignKey(TypeTransaction, on_delete=models.PROTECT, db_index=True)
    bien = models.ForeignKey(Bien, on_delete=models.SET_NULL, null=True, blank=True, db_index=True)
    locataire = models.ForeignKey(Locataire, on_delete=models.SET_NULL, null=True, blank=True, db_index=True)
    sci = models.ForeignKey(SCI, on_delete=models.CASCADE, related_name='transactions', null=True, db_index=True)
    montant = models.DecimalField(max_digits=10, decimal_places=2)
    date = models.DateField(db_index=True)
    mois_concerne = models.DateField(help_text="Mois et année concernés par cette transaction", blank=True, null=True, db_index=True)
    description = models.TextField(blank=True, null=True)

    class Meta:
        indexes = [
            models.Index(fields=['sci', 'date']),
            models.Index(fields=['sci', '-date']),
            models.Index(fields=['bien', 'date']),
            models.Index(fields=['locataire', 'date']),
        ]

    def __str__(self):
        recipient = self.bien if self.bien else "SCI"
        return f"{self.type_transaction.nom} - {self.montant}€ - {self.date} - {recipient}"

    def save(self, *args, **kwargs):
        # Si mois_concerne n'est pas défini, utiliser la date de la transaction
        if not self.mois_concerne:
            self.mois_concerne = self.date
        super().save(*args, **kwargs)


class ParametresComptables(models.Model):
    """Modèle pour stocker les paramètres comptables de l'application"""
    annee = models.PositiveIntegerField()
    sci = models.ForeignKey(SCI, on_delete=models.CASCADE, null=True)
    solde_initial = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    compte_courant_initial = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    solde_final = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    class Meta:
        unique_together = ('sci', 'annee')

    def __str__(self):
        return f"Paramètres comptables {self.annee}"


class ParametresSCI(models.Model):
    """Modèle pour stocker les paramètres de la SCI"""
    nom_sci = models.CharField(max_length=100, default="SCI les Jonquilles", verbose_name="Nom de la SCI")
    adresse = models.CharField(max_length=200, default="24 rue des jardins de la Somme", verbose_name="Adresse")
    code_postal = models.CharField(max_length=10, default="80800", verbose_name="Code postal")
    ville = models.CharField(max_length=100, default="CORBIE", verbose_name="Ville")
    representants = models.CharField(max_length=200, default="Gisèle et Jean BULTEL", verbose_name="Représentants")
    titre_representants = models.CharField(max_length=100, default="Co-gérants", verbose_name="Titre des représentants")

    class Meta:
        verbose_name = "Paramètres SCI"
        verbose_name_plural = "Paramètres SCIs"
        ordering = ['id']
        permissions = [
            ("view_all_sci", "Can view all SCIs"),
            ("manage_sci", "Can manage SCI properties"),
        ]

    def __str__(self):
        return self.nom_sci

    @classmethod
    def get_instance(cls):
        """Récupère ou crée une instance unique des paramètres"""
        obj, created = cls.objects.get_or_create(pk=1)
        return obj


class LocationBien(models.Model):
    """Modèle pour représenter l'association entre un locataire et un bien avec des détails spécifiques"""
    locataire = models.ForeignKey(Locataire, on_delete=models.CASCADE, related_name='locations', db_index=True)  # ← INDEX AJOUTÉ
    bien = models.ForeignKey(Bien, on_delete=models.CASCADE, related_name='locations', db_index=True)  # ← INDEX AJOUTÉ
    date_entree = models.DateField(verbose_name="Date d'entrée", db_index=True)  # ← INDEX AJOUTÉ
    date_sortie = models.DateField(null=True, blank=True, verbose_name="Date de sortie", db_index=True)  # ← INDEX AJOUTÉ
    montant_caution = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="Montant de la caution")
    date_versement_caution = models.DateField(null=True, blank=True, verbose_name="Date de versement de la caution")
    date_restitution_caution = models.DateField(null=True, blank=True, verbose_name="Date de restitution de la caution")

    class Meta:
        verbose_name = "Location de bien"
        verbose_name_plural = "Locations de biens"
        unique_together = ('locataire', 'bien')
        indexes = [
            models.Index(fields=['bien', 'date_sortie']),  # ← INDEX COMPOSITE : pour trouver les locations actives d'un bien
            models.Index(fields=['locataire', 'date_sortie']),  # ← INDEX COMPOSITE : pour trouver les locations actives d'un locataire
        ]

    def save(self, *args, **kwargs):
        # Supprimer la synchronisation avec Locataire
        # Nous utilisons maintenant les propriétés calculées dans Locataire
        # au lieu de synchroniser les données

        # Appeler la méthode save originale
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.locataire} - {self.bien}"

class MontantOM(models.Model):
    sci = models.ForeignKey('SCI', on_delete=models.CASCADE, related_name='montants_om')
    locataire = models.ForeignKey('Locataire', on_delete=models.CASCADE, related_name='montants_om')
    bien = models.ForeignKey('Bien', on_delete=models.CASCADE, related_name='montants_om')
    annee = models.IntegerField(verbose_name="Année")
    montant_attendu = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Montant attendu")

    class Meta:
        unique_together = ('locataire', 'bien', 'annee')
        ordering = ['-annee', 'locataire__nom']
        verbose_name = "Montant OM"
        verbose_name_plural = "Montants OM"

    def __str__(self):
        return f"OM {self.annee} - {self.locataire} - {self.bien} : {self.montant_attendu} €"

class CommentaireCreance(models.Model):
    """Modèle pour stocker les commentaires sur les créances"""
    sci = models.ForeignKey('SCI', on_delete=models.CASCADE)
    locataire = models.ForeignKey('Locataire', on_delete=models.CASCADE)
    bien = models.ForeignKey('Bien', on_delete=models.CASCADE)
    type_creance = models.CharField(max_length=50)  # 'Loyer', 'Caution', 'Ordures Ménagères'
    periode = models.CharField(max_length=50)  # 'Mars 2025', 'N/A', 'Année 2025'
    commentaire = models.TextField(blank=True, null=True)
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('sci', 'locataire', 'bien', 'type_creance', 'periode')

    def __str__(self):
        return f"Commentaire sur {self.type_creance} - {self.periode} pour {self.locataire}"