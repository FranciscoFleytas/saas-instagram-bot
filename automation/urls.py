from django.urls import path
from .views import (
    dashboard_view, AccountConfigView, 
    trigger_bot_interaction, trigger_bot_scraping, trigger_bot_outreach,
    LeadListView
)

urlpatterns = [
    path('dashboard/', dashboard_view, name='dashboard-ui'),
    
    # Configuración
    path('api/account/<uuid:id>/config/', AccountConfigView.as_view(), name='account-config'),
    
    # Triggers (Botones)
    path('api/account/<uuid:pk>/start-bot/', trigger_bot_interaction, name='start-bot'),
    path('api/account/<uuid:pk>/start-scraping/', trigger_bot_scraping, name='start-scraping'),
    path('api/account/<uuid:pk>/start-outreach/', trigger_bot_outreach, name='start-outreach'),

    # Data (Tablas)
    path('api/account/<uuid:pk>/leads/', LeadListView.as_view(), name='list-leads'),
]