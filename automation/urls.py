from django.urls import path
from . import views

urlpatterns = [
    # Endpoint para Scraper
    path('api/start-scraping/', views.start_scraping_view, name='start_scraping'),
    
    # Endpoint para Outreach (DMs)
    path('api/start-outreach/', views.start_outreach_view, name='start_outreach'),
    
    # Endpoint para Comentarios (Engagement)
    path('api/start-comment/', views.start_comment_view, name='start_comment'),
]