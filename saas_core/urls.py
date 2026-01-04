from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    # Delega todo el tráfico a la app automation
    path("", include("automation.urls")),
]
