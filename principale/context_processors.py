# principale/context_processors.py

from .models import ParametresSCI

def sci_info(request):
    """
    Context processor qui rend disponible les informations de la SCI
    dans tous les templates Django.
    """
    try:
        sci = ParametresSCI.get_instance()
        return {'sci_info': sci}
    except Exception as e:
        # En cas d'erreur (par exemple, pendant les migrations initiales)
        # ou si le modèle n'existe pas encore
        return {'sci_info': None}

# context_processors.py
def sci_context(request):
    context = {}

    if hasattr(request, 'user') and request.user.is_authenticated:
        from .models import SCI
        context['scis_list'] = SCI.objects.all()

        if hasattr(request, 'current_sci'):
            context['current_sci'] = request.current_sci

    return context