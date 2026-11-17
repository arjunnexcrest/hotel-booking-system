from rest_framework import serializers
from .models import RestaurantTable, TableZone, TableEvent


class TableZoneSerializer(serializers.ModelSerializer):
    class Meta:
        model = TableZone
        fields = ['id', 'table', 'zone_identifier', 'polygon_coordinates', 'created_at']
        read_only_fields = ['id', 'created_at']


class TableEventSerializer(serializers.ModelSerializer):
    actor_username = serializers.CharField(source='actor.username', read_only=True)

    class Meta:
        model = TableEvent
        fields = [
            'id',
            'table',
            'from_status',
            'to_status',
            'triggered_by',
            'actor',
            'actor_username',
            'reason',
            'created_at',
        ]
        read_only_fields = ['id', 'created_at']


class RestaurantTableSerializer(serializers.ModelSerializer):
    monitoring_zones = TableZoneSerializer(many=True, read_only=True)
    restaurant_name = serializers.CharField(source='restaurant.name', read_only=True)

    class Meta:
        model = RestaurantTable
        fields = [
            'id',
            'restaurant',
            'restaurant_name',
            'table_number',
            'capacity',
            'min_capacity',
            'table_type',
            'zone_name',
            'description',
            'operational_status',
            'is_active',
            'qr_code_url',
            'monitoring_zones',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
