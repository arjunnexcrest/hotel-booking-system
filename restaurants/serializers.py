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
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def validate(self, data):
        is_closed = data.get('is_closed', False)
        opening_time = data.get('opening_time')
        closing_time = data.get('closing_time')

        if not is_closed and opening_time and closing_time:
            if opening_time >= closing_time:
                raise serializers.ValidationError({"closing_time": "Closing time must be after opening time."})
        return data


class OperatingHoursBulkItemSerializer(serializers.Serializer):
    day_of_week = serializers.IntegerField(min_value=0, max_value=6)
    opening_time = serializers.TimeField(required=False, default='09:00:00')
    closing_time = serializers.TimeField(required=False, default='22:00:00')
    is_closed = serializers.BooleanField(required=False, default=False)

    def validate(self, data):
        if not data.get('is_closed', False):
            opt = data.get('opening_time')
            clt = data.get('closing_time')
            if opt and clt and opt >= clt:
                raise serializers.ValidationError("Closing time must be after opening time.")
        return data


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
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def validate(self, data):
        if not data.get('is_all_day', True):
            st = data.get('start_time')
            et = data.get('end_time')
            if not st or not et:
                raise serializers.ValidationError("Start time and end time are required when not an all-day closure.")
            if st >= et:
                raise serializers.ValidationError({"end_time": "End time must be after start time."})
        return data


class RestaurantSerializer(serializers.ModelSerializer):
    images = RestaurantImageSerializer(many=True, read_only=True)
    operating_hours = OperatingHoursSerializer(many=True, read_only=True)
    hotel_name = serializers.CharField(source='hotel.name', read_only=True)
    dress_code_display = serializers.CharField(source='get_dress_code_display', read_only=True)
    price_tier_display = serializers.CharField(source='get_price_tier_display', read_only=True)
    slug = serializers.SlugField(required=False, allow_blank=True)
    table_count = serializers.SerializerMethodField()

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
            'dress_code',
            'dress_code_display',
            'price_tier',
            'price_tier_display',
            'phone_number',
            'email',
            'turnover_buffer_minutes',
            'min_reservation_duration',
            'max_reservation_duration',
            'min_advance_minutes',
            'max_advance_days',
            'is_active',
            'table_count',
            'images',
            'operating_hours',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
        validators = []

    def validate(self, data):
        hotel = data.get('hotel', getattr(self.instance, 'hotel', None))
        slug = data.get('slug')
        if not slug:
            from django.utils.text import slugify
            base_slug = slugify(data.get('name', 'restaurant')) or 'restaurant'
            slug = base_slug
            counter = 1
            while Restaurant.objects.filter(hotel=hotel, slug=slug).exclude(pk=getattr(self.instance, 'pk', None)).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            data['slug'] = slug
        elif Restaurant.objects.filter(hotel=hotel, slug=slug).exclude(pk=getattr(self.instance, 'pk', None)).exists():
            raise serializers.ValidationError({"slug": "A restaurant with this slug already exists for this hotel."})
        return data

    def get_table_count(self, obj):
        return obj.tables.filter(is_active=True).count()
