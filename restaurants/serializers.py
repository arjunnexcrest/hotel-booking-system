from rest_framework import serializers
from .models import Restaurant, RestaurantImage, OperatingHours, SpecialClosure


class RestaurantImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = RestaurantImage
        fields = ['id', 'restaurant', 'image', 'caption', 'is_primary', 'created_at']
        read_only_fields = ['id', 'created_at']


class OperatingHoursSerializer(serializers.ModelSerializer):
    day_name = serializers.CharField(source='get_day_of_week_display', read_only=True)

    class Meta:
        model = OperatingHours
        fields = [
            'id',
            'restaurant',
            'day_of_week',
            'day_name',
            'opening_time',
            'closing_time',
            'is_closed',
        ]
        read_only_fields = ['id']


class SpecialClosureSerializer(serializers.ModelSerializer):
    class Meta:
        model = SpecialClosure
        fields = [
            'id',
            'restaurant',
            'closure_date',
            'reason',
            'start_time',
            'end_time',
            'is_all_day',
        ]
        read_only_fields = ['id']


class RestaurantSerializer(serializers.ModelSerializer):
    images = RestaurantImageSerializer(many=True, read_only=True)
    operating_hours = OperatingHoursSerializer(many=True, read_only=True)
    hotel_name = serializers.CharField(source='hotel.name', read_only=True)

    class Meta:
        model = Restaurant
        fields = [
            'id',
            'hotel',
            'hotel_name',
            'name',
            'slug',
            'description',
            'cuisine_type',
            'is_active',
            'images',
            'operating_hours',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
