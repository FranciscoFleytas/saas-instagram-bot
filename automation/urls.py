from django.urls import include, path

urlpatterns = [
    path("api/", include("automation.api_urls")),
]
