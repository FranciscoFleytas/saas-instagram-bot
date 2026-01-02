from rest_framework import serializers
from .models import IGAccount, Lead  # <--- ¡AQUÍ FALTABA IMPORTAR 'Lead'!

class IGAccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = IGAccount
        fields = ['id', 'username', 'ai_persona', 'ai_focus']
        read_only_fields = ['id', 'username']

class LeadSerializer(serializers.ModelSerializer):
    class Meta:
        model = Lead
        fields = ['id', 'ig_username', 'status', 'created_at']