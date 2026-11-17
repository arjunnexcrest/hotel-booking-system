from rest_framework import serializers
from .models import AuditLog


class AuditLogSerializer(serializers.ModelSerializer):
    actor_name = serializers.CharField(source='actor.username', read_only=True)
    hotel_name = serializers.CharField(source='hotel.name', read_only=True)

    class Meta:
        model = AuditLog
        fields = [
            'id',
            'actor',
            'actor_name',
            'actor_type',
            'hotel',
            'hotel_name',
            'action',
            'entity_type',
            'entity_id',
            'old_values',
            'new_values',
            'reason',
            'ip_address',
            'user_agent',
            'request_id',
            'created_at',
        ]
        read_only_fields = ['id', 'created_at']
