from django.urls import path

from . import api_views

urlpatterns = [
    path("bots/", api_views.bots_list_create, name="api-bots"),
    path("bots/<uuid:bot_id>/", api_views.bots_patch, name="api-bots-patch"),
    path("campaigns/", api_views.campaigns_list_create, name="api-campaigns"),
    path("campaigns/<uuid:campaign_id>/", api_views.campaigns_detail, name="api-campaign-detail"),
    path("tasks/", api_views.tasks_list, name="api-tasks"),
]
