from django.contrib import admin
from .models import Bien, Locataire, Transaction, TypeTransaction, ParametresSCI, SCI

# Tenter de désinscrire SCI s'il est déjà inscrit ailleurs
try:
    admin.site.unregister(SCI)
except admin.sites.NotRegistered:
    pass

class ParametresSCIAdmin(admin.ModelAdmin):
    """
    Configuration de l'interface d'administration pour les paramètres de la SCI
    Permet d'éditer les paramètres sans possibilité d'en créer de nouveaux
    """
    def has_add_permission(self, request):
        # Empêcher la création de nouveaux paramètres si un existe déjà
        return not ParametresSCI.objects.exists()

    def has_delete_permission(self, request, obj=None):
        # Empêcher la suppression des paramètres
        return False

class SCIAdmin(admin.ModelAdmin):
    """
    Configuration de l'interface d'administration pour les SCI
    """
    list_display = ('nom', 'adresse', 'code_postal', 'ville', 'representants')
    search_fields = ('nom', 'ville', 'representants')
    list_filter = ('ville',)
    exclude = ('titre_representants',)

# Enregistrement des modèles
admin.site.register(Bien)
admin.site.register(Locataire)
admin.site.register(Transaction)
admin.site.register(TypeTransaction)
#admin.site.register(ParametresSCI, ParametresSCIAdmin)
admin.site.register(SCI, SCIAdmin)