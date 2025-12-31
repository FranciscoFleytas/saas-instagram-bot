from rest_framework import serializers
from .models import IGAccount

class IGAccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = IGAccount
        fields = ['id', 'username', 'ai_persona', 'ai_focus']
        read_only_fields = ['id', 'username']