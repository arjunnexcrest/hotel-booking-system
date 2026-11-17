from rest_framework import serializers
from .models import Camera, CameraTableZone, AIEvent, ServiceAlert, MonitoringOutage


class CameraTableZoneSerializer(serializers.ModelSerializer):
    zone_identifier = serializers.CharField(source='table_zone.zone_identifier', read_only=True)

    class Meta:
        model = CameraTableZone
        fields = ['id', 'camera', 'table_zone', 'zone_identifier', 'confidence_threshold', 'is_active']


class CameraSerializer(serializers.ModelSerializer):
    monitored_zones = CameraTableZoneSerializer(many=True, read_only=True)

    class Meta:
        model = Camera
        fields = [
            'id',
            'hotel',
            'restaurant',
            'camera_name',
            'camera_code',
            'location_description',
            'ip_address',
            'stream_url',
            'connection_status',
            'is_active',
            'last_heartbeat_at',
            'monitored_zones',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
        extra_kwargs = {
            'stream_url': {'write_only': True}
        }


class AIEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = AIEvent
        fields = [
            'id',
            'hotel',
            'restaurant',
            'table',
            'camera',
            'source_event_id',
            'event_type',
            'confidence_score',
            'model_name',
            'model_version',
            'validation_status',
            'raw_payload',
            'created_at',
        ]
        read_only_fields = ['id', 'created_at']


class ServiceAlertSerializer(serializers.ModelSerializer):
    table_number = serializers.CharField(source='table.table_number', read_only=True)
    acknowledged_by_username = serializers.CharField(source='acknowledged_by.username', read_only=True)
    resolved_by_username = serializers.CharField(source='resolved_by.username', read_only=True)

    class Meta:
        model = ServiceAlert
        fields = [
            'id',
            'hotel',
            'restaurant',
            'table',
            'table_number',
            'ai_event',
            'alert_type',
            'priority',
            'status',
            'message',
            'acknowledged_by',
            'acknowledged_by_username',
            'acknowledged_at',
            'resolved_by',
            'resolved_by_username',
            'resolved_at',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class MonitoringOutageSerializer(serializers.ModelSerializer):
    class Meta:
        model = MonitoringOutage
        fields = ['id', 'camera', 'outage_type', 'started_at', 'resolved_at', 'description']
        read_only_fields = ['id']
