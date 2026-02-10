from core.models import Immeuble


def navigation_context(request):
    """Injecte la liste des immeubles pour la sidebar de navigation."""
    if request.user.is_authenticated:
        return {
            'nav_immeubles': Immeuble.objects.select_related('proprietaire').order_by('nom'),
        }
    return {}
