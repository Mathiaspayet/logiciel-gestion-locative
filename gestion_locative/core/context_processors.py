from django.conf import settings

from core.models import Immeuble


def navigation_context(request):
    """Injecte la liste des immeubles pour la sidebar de navigation."""
    if request.user.is_authenticated:
        return {
            'nav_immeubles': Immeuble.objects.select_related('proprietaire').order_by('nom'),
            'build_version': settings.BUILD_VERSION,
            'build_date': settings.BUILD_DATE,
        }
    return {}
