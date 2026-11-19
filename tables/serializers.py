from rest_framework import serializers
from .models import RestaurantTable, TableZone, TableEvent
from restaurants.models import Restaurant


class TableZoneSerializer(serializers.ModelSerializer):
    class Meta:
        model = TableZone
        fields = ['id', 'table', 'zone_identifier', 'polygon_coordinates', 'created_at']
        read_only_fields = ['id', 'created_at']


class TableEventSerializer(serializers.ModelSerializer):
    actor_username = serializers.CharField(source='actor.username', read_only=True)
    from_status_display = serializers.CharField(source='get_from_status_display', read_only=True)
    to_status_display = serializers.CharField(source='get_to_status_display', read_only=True)

    class Meta:
        model = TableEvent
        fields = [
            'id',
            'table',
            'from_status',
            'from_status_display',
            'to_status',
            'to_status_display',
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
    operational_status_display = serializers.CharField(source='get_operational_status_display', read_only=True)
    table_type_display = serializers.CharField(source='get_table_type_display', read_only=True)
    shape_display = serializers.CharField(source='get_shape_display', read_only=True)

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
            'table_type_display',
            'shape',
            'shape_display',
            'pos_x',
            'pos_y',
            'zone_name',
            'description',
            'operational_status',
            'operational_status_display',
            'is_active',
            'qr_code_url',
            'monitoring_zones',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def validate(self, data):
        cap = data.get('capacity', getattr(self.instance, 'capacity', 2))
        min_cap = data.get('min_capacity', getattr(self.instance, 'min_capacity', 1))
        if min_cap > cap:
            raise serializers.ValidationError({"min_capacity": "Minimum capacity cannot exceed table maximum capacity."})
        return data


class TableBulkCreateSerializer(serializers.Serializer):
    restaurant = serializers.PrimaryKeyRelatedField(queryset=Restaurant.objects.all())
    prefix = serializers.CharField(max_length=20, default='T-')
    start_number = serializers.IntegerField(default=1, min_value=1)
    count = serializers.IntegerField(default=10, min_value=1, max_value=100)
    capacity = serializers.IntegerField(default=4, min_value=1)
    min_capacity = serializers.IntegerField(default=1, min_value=1)
    table_type = serializers.ChoiceField(choices=RestaurantTable.TableType.choices, default=RestaurantTable.TableType.STANDARD)
    shape = serializers.ChoiceField(choices=RestaurantTable.TableShape.choices, default=RestaurantTable.TableShape.RECTANGULAR)
    zone_name = serializers.CharField(max_length=100, default='Main Dining')

    def validate(self, data):
        if data['min_capacity'] > data['capacity']:
            raise serializers.ValidationError({"min_capacity": "Minimum capacity cannot exceed maximum capacity."})
        return data


class TableBulkStatusUpdateSerializer(serializers.Serializer):
    table_ids = serializers.ListField(
        child=serializers.IntegerField(),
        allow_empty=False
    )
    operational_status = serializers.ChoiceField(choices=RestaurantTable.OperationalStatus.choices)
    reason = serializers.CharField(max_length=255, default='Bulk status update')
