from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    # Redirige todo el tráfico a la app de automation
    path('', include('automation.urls')),
]