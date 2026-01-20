from django.urls import path, include
from rest_framework.routers import DefaultRouter
# Import des vues (refactorisées utilisant PDFGenerator et templates Django)
from .views import (
    ImmeubleViewSet,
    BailViewSet,
    generer_quittance_pdf,
    generer_avis_echeance_pdf,
    generer_regularisation_pdf,
    generer_solde_tout_compte_pdf,
    generer_revision_loyer_pdf,
    creer_tarification_from_revision,
    dashboard_patrimoine,
)

router = DefaultRouter()
router.register(r'immeubles', ImmeubleViewSet)
router.register(r'baux', BailViewSet)

urlpatterns = [
    # PDF Generation
    path('quittance/<int:pk>/', generer_quittance_pdf, name='quittance_pdf'),
    path('avis_echeance/<int:pk>/', generer_avis_echeance_pdf, name='avis_echeance_pdf'),
    path('regularisation/<int:pk>/', generer_regularisation_pdf, name='regularisation_pdf'),
    path('solde_tout_compte/<int:pk>/', generer_solde_tout_compte_pdf, name='solde_tout_compte_pdf'),
    path('revision_loyer/<int:pk>/', generer_revision_loyer_pdf, name='revision_loyer_pdf'),
    path('creer_tarification_revision/<int:pk>/', creer_tarification_from_revision, name='creer_tarification_from_revision'),

    # Dashboard Patrimoine
    path('patrimoine/dashboard/', dashboard_patrimoine, name='dashboard_patrimoine'),

    # API
    path('', include(router.urls)),
]