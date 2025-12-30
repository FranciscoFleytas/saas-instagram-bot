from django.contrib import admin
from .models import Agency, IGAccount, Lead

@admin.register(Agency)
class AgencyAdmin(admin.ModelAdmin):
    list_display = ('name', 'plan_level', 'payment_status')

@admin.register(IGAccount)
class IGAccountAdmin(admin.ModelAdmin):
    list_display = ('username', 'agency', 'status')

@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
    list_display = ('ig_username', 'source_account', 'status', 'created_at')
    list_filter = ('status', 'source_account')
    search_fields = ('ig_username',)