from django.urls import path
# Import des vues (refactorisées utilisant PDFGenerator et templates Django)
from .views import (
    generer_quittance_pdf,
    generer_avis_echeance_pdf,
    generer_regularisation_pdf,
    generer_solde_tout_compte_pdf,
    generer_revision_loyer_pdf,
    creer_tarification_from_revision,
    dashboard_patrimoine,
    dashboard_immeuble_detail,
    bilan_fiscal_immeuble,
    assistant_credit,
)

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
    path('patrimoine/immeuble/<int:immeuble_id>/', dashboard_immeuble_detail, name='dashboard_immeuble_detail'),

    # Bilan Fiscal
    path('fiscal/immeuble/<int:immeuble_id>/', bilan_fiscal_immeuble, name='bilan_fiscal_immeuble'),

    # Assistant Crédit
    path('assistant-credit/', assistant_credit, name='assistant_credit'),
    path('assistant-credit/<int:immeuble_id>/', assistant_credit, name='assistant_credit_immeuble'),
]