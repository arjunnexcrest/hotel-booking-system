from rest_framework import serializers
from .models import Notification, NotificationDelivery


class NotificationDeliverySerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationDelivery
        fields = [
            'id',
            'notification',
            'channel',
            'status',
            'attempt_count',
            'error_message',
            'sent_at',
        ]
        read_only_fields = ['id', 'sent_at']


class NotificationSerializer(serializers.ModelSerializer):
    deliveries = NotificationDeliverySerializer(many=True, read_only=True)

    class Meta:
        model = Notification
        fields = [
            'id',
            'recipient',
            'hotel',
            'title',
            'message',
            'notification_type',
            'is_read',
            'read_at',
            'deliveries',
            'created_at',
        ]
        read_only_fields = ['id', 'created_at']
