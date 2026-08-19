from django.conf import settings
from django.contrib import admin
from django.contrib.auth.decorators import login_required
from django.urls import path, include, re_path
from django.views.generic import RedirectView
from django.views.static import serve

urlpatterns = [
    path('', RedirectView.as_view(url='/app/', permanent=False)),
    path('admin/', admin.site.urls),
    path('api/', include('core.urls')),
    path('app/', include('core.urls_app')),
    # Les justificatifs fiscaux sont des documents prives : ils ne sont servis
    # qu'a un utilisateur connecte, jamais en acces anonyme.
    re_path(
        r'^media/(?P<path>.*)$',
        login_required(serve),
        {'document_root': settings.MEDIA_ROOT},
        name='media',
    ),
]
