"""
URL configuration for saas_core project.
"""
from django.contrib import admin
from django.urls import path, include  # <--- Agregamos 'include' aquí

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # Conectamos las rutas de la app 'automation'
    # Dejamos el string vacío '' para que las rutas 'api/...' funcionen directo
    path('', include('automation.urls')), 
]