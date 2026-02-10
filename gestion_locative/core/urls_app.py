from django.urls import path
from core import views_app

urlpatterns = [
    # Auth
    path('login/', views_app.login_view, name='app_login'),
    path('logout/', views_app.logout_view, name='app_logout'),

    # Dashboard
    path('', views_app.dashboard_view, name='app_dashboard'),

    # Depenses
    path('depenses/ajouter/', views_app.depense_quick_add_view, name='app_depense_quick_add'),

    # Immeubles - detail + tabs
    path('immeubles/<int:pk>/', views_app.immeuble_detail_view, name='app_immeuble_detail'),
    path('immeubles/<int:pk>/tab/<str:tab>/', views_app.immeuble_tab_view, name='app_immeuble_tab'),

    # Immeubles - CRUD
    path('immeubles/creer/', views_app.immeuble_create_view, name='app_immeuble_create'),
    path('immeubles/<int:pk>/modifier/', views_app.immeuble_edit_view, name='app_immeuble_edit'),
    path('immeubles/<int:pk>/supprimer/', views_app.immeuble_delete_view, name='app_immeuble_delete'),

    # Locaux - CRUD
    path('immeubles/<int:immeuble_pk>/locaux/creer/', views_app.local_create_view, name='app_local_create'),
    path('locaux/<int:pk>/modifier/', views_app.local_edit_view, name='app_local_edit'),
    path('locaux/<int:pk>/supprimer/', views_app.local_delete_view, name='app_local_delete'),

    # Baux - detail + tabs
    path('baux/<int:pk>/', views_app.bail_detail_view, name='app_bail_detail'),
    path('baux/<int:pk>/tab/<str:tab>/', views_app.bail_tab_view, name='app_bail_tab'),

    # Baux - CRUD
    path('locaux/<int:local_pk>/baux/creer/', views_app.bail_create_view, name='app_bail_create'),
    path('baux/<int:pk>/modifier/', views_app.bail_edit_view, name='app_bail_edit'),

    # Tarifications - CRUD
    path('baux/<int:bail_pk>/tarifications/creer/', views_app.tarification_create_view, name='app_tarification_create'),

    # Occupants - CRUD
    path('baux/<int:bail_pk>/occupants/creer/', views_app.occupant_create_view, name='app_occupant_create'),
    path('occupants/<int:pk>/modifier/', views_app.occupant_edit_view, name='app_occupant_edit'),
    path('occupants/<int:pk>/supprimer/', views_app.occupant_delete_view, name='app_occupant_delete'),

    # Estimations - CRUD
    path('immeubles/<int:immeuble_pk>/estimations/creer/', views_app.estimation_create_view, name='app_estimation_create'),
    path('estimations/<int:pk>/supprimer/', views_app.estimation_delete_view, name='app_estimation_delete'),

    # Credits - CRUD
    path('immeubles/<int:immeuble_pk>/credits/creer/', views_app.credit_create_view, name='app_credit_create'),
    path('credits/<int:pk>/modifier/', views_app.credit_edit_view, name='app_credit_edit'),
    path('credits/<int:pk>/supprimer/', views_app.credit_delete_view, name='app_credit_delete'),

    # Depenses - CRUD
    path('immeubles/<int:immeuble_pk>/depenses/creer/', views_app.depense_create_view, name='app_depense_create'),
    path('depenses/<int:pk>/modifier/', views_app.depense_edit_view, name='app_depense_edit'),
    path('depenses/<int:pk>/supprimer/', views_app.depense_delete_view, name='app_depense_delete'),

    # Cles de repartition - CRUD + detail
    path('immeubles/<int:immeuble_pk>/cles/creer/', views_app.cle_create_view, name='app_cle_create'),
    path('cles/<int:pk>/', views_app.cle_detail_view, name='app_cle_detail'),
    path('cles/<int:pk>/modifier/', views_app.cle_edit_view, name='app_cle_edit'),
    path('cles/<int:pk>/supprimer/', views_app.cle_delete_view, name='app_cle_delete'),

    # Quotes-parts - CRUD
    path('cles/<int:cle_pk>/quotesparts/creer/', views_app.quotepart_create_view, name='app_quotepart_create'),
    path('quotesparts/<int:pk>/modifier/', views_app.quotepart_edit_view, name='app_quotepart_edit'),
    path('quotesparts/<int:pk>/supprimer/', views_app.quotepart_delete_view, name='app_quotepart_delete'),

    # Consommations - CRUD
    path('immeubles/<int:immeuble_pk>/consommations/creer/', views_app.consommation_create_view, name='app_consommation_create'),
    path('consommations/<int:pk>/modifier/', views_app.consommation_edit_view, name='app_consommation_edit'),
    path('consommations/<int:pk>/supprimer/', views_app.consommation_delete_view, name='app_consommation_delete'),

    # Regularisations - CRUD
    path('baux/<int:bail_pk>/regularisations/creer/', views_app.regularisation_create_view, name='app_regularisation_create'),
    path('regularisations/<int:pk>/modifier/', views_app.regularisation_edit_view, name='app_regularisation_edit'),
    path('regularisations/<int:pk>/supprimer/', views_app.regularisation_delete_view, name='app_regularisation_delete'),

    # Ajustements - CRUD
    path('baux/<int:bail_pk>/ajustements/creer/', views_app.ajustement_create_view, name='app_ajustement_create'),
    path('ajustements/<int:pk>/modifier/', views_app.ajustement_edit_view, name='app_ajustement_edit'),
    path('ajustements/<int:pk>/supprimer/', views_app.ajustement_delete_view, name='app_ajustement_delete'),

    # Patrimoine
    path('patrimoine/', views_app.patrimoine_dashboard_view, name='app_patrimoine'),
    path('immeubles/<int:pk>/fiscal/', views_app.bilan_fiscal_view, name='app_bilan_fiscal'),
]
