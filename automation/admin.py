from django.contrib import admin
from .models import Agency, IGAccount, InteractionCampaign, InteractionTask


@admin.register(Agency)
class AgencyAdmin(admin.ModelAdmin):
    list_display = ('name', 'plan_level')


@admin.register(IGAccount)
class IGAccountAdmin(admin.ModelAdmin):
    list_display = ('username', 'agency', 'status')


@admin.register(InteractionCampaign)
class InteractionCampaignAdmin(admin.ModelAdmin):
    list_display = ('id', 'agency', 'action', 'status', 'created_at')


@admin.register(InteractionTask)
class InteractionTaskAdmin(admin.ModelAdmin):
    list_display = ('campaign', 'ig_account', 'action', 'status', 'attempts')
