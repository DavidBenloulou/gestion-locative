from .models import SCI
from django.contrib.auth import login
from django.contrib.auth.models import User

class SCIMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Authentification automatique
        if hasattr(request, 'user') and not request.user.is_authenticated:
            try:
                # Trouver un utilisateur existant ou utiliser l'administrateur
                user = User.objects.filter(is_superuser=True).first() or User.objects.first()
                if user:
                    # Fournir le backend pour éviter les erreurs
                    login(request, user, backend='django.contrib.auth.backends.ModelBackend')
            except Exception as e:
                print(f"Erreur d'authentification auto: {e}")

        # Le reste de votre code inchangé
        if not hasattr(request, 'session') or not request.session.session_key:
            request.session.save()

        sci_id = request.session.get('sci_id')

        if not sci_id:
            default_sci = SCI.objects.first()
            if default_sci:
                request.session['sci_id'] = default_sci.id
                sci_id = default_sci.id
                request.session.save()

        if sci_id:
            try:
                request.current_sci = SCI.objects.get(id=sci_id)
            except SCI.DoesNotExist:
                default_sci = SCI.objects.first()
                if default_sci:
                    request.session['sci_id'] = default_sci.id
                    request.current_sci = default_sci
                    request.session.save()
                else:
                    request.current_sci = None
        else:
            request.current_sci = None

        request.scis_list = SCI.objects.all()

        response = self.get_response(request)
        return response

