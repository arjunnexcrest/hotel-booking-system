from rest_framework import serializers
from django.core.exceptions import ValidationError as DjangoValidationError

from .models import Booking, BookingHistory
from tables.models import RestaurantTable
from restaurants.models import Restaurant
from hotels.models import Hotel
from .services.booking_service import BookingService


class BookingHistorySerializer(serializers.ModelSerializer):
    changed_by_username = serializers.CharField(source='changed_by.username', read_only=True)

    class Meta:
        model = BookingHistory
        fields = [
            'id',
            'booking',
            'changed_by',
            'changed_by_username',
            'previous_status',
            'new_status',
            'reason',
            'created_at',
        ]
        read_only_fields = ['id', 'created_at']


class AvailableSlotSerializer(serializers.Serializer):
    time = serializers.CharField()
    time_display = serializers.CharField()
    end_time = serializers.CharField()
    end_time_display = serializers.CharField()
    available_tables = serializers.IntegerField()
    is_peak = serializers.BooleanField()


class CancelByReferenceSerializer(serializers.Serializer):
    booking_reference = serializers.CharField(max_length=32, required=True)
    customer_email = serializers.EmailField(required=True)
    reason = serializers.CharField(max_length=255, required=False, default='Cancelled by guest')


class BookingSerializer(serializers.ModelSerializer):
    hotel_name = serializers.CharField(source='hotel.name', read_only=True)
    restaurant_name = serializers.CharField(source='restaurant.name', read_only=True)
    table_number = serializers.CharField(source='table.table_number', read_only=True)
    table_zone = serializers.CharField(source='table.zone_name', read_only=True)
    booking_status_display = serializers.CharField(source='get_booking_status_display', read_only=True)
    history = BookingHistorySerializer(many=True, read_only=True)

    table = serializers.PrimaryKeyRelatedField(
        queryset=RestaurantTable.objects.all(),
        required=False,
        allow_null=True
    )
    zone_name = serializers.CharField(required=False, write_only=True, allow_blank=True)

    class Meta:
        model = Booking
        fields = [
            'id',
            'booking_reference',
            'customer',
            'customer_name',
            'customer_email',
            'customer_phone',
            'hotel',
            'hotel_name',
            'restaurant',
            'restaurant_name',
            'table',
            'table_number',
            'table_zone',
            'zone_name',
            'booking_date',
            'start_time',
            'end_time',
            'guest_count',
            'special_requests',
            'booking_status',
            'booking_status_display',
            'cancellation_reason',
            'cancelled_at',
            'history',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'booking_reference', 'booking_status', 'cancelled_at', 'created_at', 'updated_at']

    def validate(self, data):
        start_time = data.get('start_time')
        end_time = data.get('end_time')
        table = data.get('table')
        restaurant = data.get('restaurant')
        hotel = data.get('hotel')
        booking_date = data.get('booking_date')
        guest_count = data.get('guest_count', 1)

        if start_time and end_time and start_time >= end_time:
            raise serializers.ValidationError({"end_time": "End time must be after start time."})

        # Infer and enforce restaurant & hotel relationships
        if table:
            if not restaurant:
                restaurant = table.restaurant
                data['restaurant'] = restaurant
            if not hotel:
                hotel = restaurant.hotel
                data['hotel'] = hotel
        elif restaurant:
            if not hotel:
                hotel = restaurant.hotel
                data['hotel'] = hotel

        # Public visibility & operational rules: Hotel must be approved and active
        if hotel and (hotel.status != Hotel.Status.APPROVED or not hotel.is_active):
            raise serializers.ValidationError({
                "hotel": f"Reservations unavailable: Hotel '{hotel.name}' is currently {hotel.get_status_display().lower()} or inactive."
            })

        # Restaurant must be active
        if restaurant and not restaurant.is_active:
            raise serializers.ValidationError({
                "restaurant": f"Reservations unavailable: Restaurant '{restaurant.name}' is currently inactive."
            })

        # Validate time, advance notice, duration, operating hours & kitchen cutoff
        if restaurant and booking_date and start_time and end_time:
            try:
                BookingService.validate_reservation_time(restaurant, booking_date, start_time, end_time)
            except DjangoValidationError as e:
                raise serializers.ValidationError({"time": str(e)})

        # Customer anti-spam / simultaneous overlapping booking check
        request = self.context.get('request')
        user = request.user if request and request.user.is_authenticated else None
        customer_email = data.get('customer_email') or (user.email if user else None)
        if booking_date and start_time and end_time and (user or customer_email):
            if BookingService.check_customer_conflict(
                customer=user,
                customer_email=customer_email,
                booking_date=booking_date,
                start_time=start_time,
                end_time=end_time,
                exclude_booking_id=self.instance.id if self.instance else None
            ):
                raise serializers.ValidationError({"customer": "You already have an active reservation for an overlapping time slot."})

        # If explicit table specified, check operational status, capacity boundaries, and buffer-aware conflict
        if table:
            if not table.is_active or table.operational_status in [RestaurantTable.OperationalStatus.MAINTENANCE, RestaurantTable.OperationalStatus.TEMPORARILY_BLOCKED]:
                raise serializers.ValidationError({
                    "table": f"Table {table.table_number} is currently out of service or inactive."
                })

            try:
                BookingService.validate_capacity(table, guest_count)
            except DjangoValidationError as e:
                raise serializers.ValidationError({"guest_count": str(e)})

            if booking_date and start_time and end_time:
                buffer_mins = restaurant.turnover_buffer_minutes if restaurant else 0
                conflicting = BookingService.check_table_conflict(
                    table.id,
                    booking_date,
                    start_time,
                    end_time,
                    buffer_minutes=buffer_mins,
                    exclude_booking_id=self.instance.id if self.instance else None
                )
                if conflicting:
                    raise serializers.ValidationError({
                        "table": f"Table {table.table_number} already has a conflicting reservation or is in turnover cleaning during this time slot."
                    })

        return data

    def create(self, validated_data):
        zone_name = validated_data.pop('zone_name', None)
        table = validated_data.pop('table', None)
        request = self.context.get('request')
        user = request.user if request and request.user.is_authenticated else None

        customer_info = {
            'name': validated_data.get('customer_name'),
            'email': validated_data.get('customer_email'),
            'phone': validated_data.get('customer_phone', ''),
        }

        try:
            return BookingService.create_reservation(
                customer=user,
                hotel=validated_data['hotel'],
                restaurant=validated_data['restaurant'],
                table_id=table.id if table else None,
                booking_date=validated_data['booking_date'],
                start_time=validated_data['start_time'],
                end_time=validated_data['end_time'],
                guest_count=validated_data['guest_count'],
                customer_info=customer_info,
                special_requests=validated_data.get('special_requests', ''),
                created_by=user,
                zone_name=zone_name,
            )
        except DjangoValidationError as err:
            raise serializers.ValidationError({"detail": str(err)})
