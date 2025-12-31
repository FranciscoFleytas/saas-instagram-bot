from django.urls import path
from .views import dashboard_view, AccountConfigView, trigger_bot_interaction

urlpatterns = [
    # La Interfaz Gráfica
    path('dashboard/', dashboard_view, name='dashboard-ui'),

    # Las APIs (Cerebro)
    path('api/account/<uuid:id>/config/', AccountConfigView.as_view(), name='account-config'),
    path('api/account/<uuid:pk>/start-bot/', trigger_bot_interaction, name='start-bot'),
]