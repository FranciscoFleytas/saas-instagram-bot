from django.urls import path
from .views import (
    # Vistas Frontend
    dashboard_view,
    bot_control_view,
    leads_view,
    extraction_view,
    # Vistas API y Funcionalidad
    get_system_logs,
    AccountConfigView,
    trigger_bot_interaction,
    trigger_bot_scraping,
    trigger_bot_outreach,
    LeadListView
)

urlpatterns = [
    # --- Vistas Frontend (HTML) ---
    path('', dashboard_view, name='home'), # Ruta raíz redirige al dashboard
    path('dashboard/', dashboard_view, name='dashboard'),
    path('bot-control/', bot_control_view, name='bot-control'),
    path('leads/', leads_view, name='leads'),
    path('extraction/', extraction_view, name='extraction'),

    # --- API Endpoints & Configuración ---
    path('api/account/<uuid:id>/config/', AccountConfigView.as_view(), name='account-config'),
    
    # Triggers (Acciones de Bot)
    path('api/account/<uuid:pk>/start-bot/', trigger_bot_interaction, name='start-bot'),
    path('api/account/<uuid:pk>/start-scraping/', trigger_bot_scraping, name='start-scraping'),
    path('api/account/<uuid:pk>/start-outreach/', trigger_bot_outreach, name='start-outreach'),

    # Data (Tablas y Logs)
    path('api/account/<uuid:pk>/leads/', LeadListView.as_view(), name='list-leads'),
    path('api/logs/', get_system_logs, name='api_logs')
]