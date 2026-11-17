from rest_framework import serializers
from .models import Booking, BookingHistory


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


class BookingSerializer(serializers.ModelSerializer):
    hotel_name = serializers.CharField(source='hotel.name', read_only=True)
    restaurant_name = serializers.CharField(source='restaurant.name', read_only=True)
    table_number = serializers.CharField(source='table.table_number', read_only=True)
    history = BookingHistorySerializer(many=True, read_only=True)

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
            'booking_date',
            'start_time',
            'end_time',
            'guest_count',
            'special_requests',
            'booking_status',
            'cancellation_reason',
            'cancelled_at',
            'history',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'booking_reference', 'created_at', 'updated_at']

    def validate(self, data):
        start_time = data.get('start_time')
        end_time = data.get('end_time')
        table = data.get('table')
        booking_date = data.get('booking_date')
        guest_count = data.get('guest_count', 1)

        if start_time and end_time and start_time >= end_time:
            raise serializers.ValidationError({"end_time": "End time must be after start time."})

        if table and guest_count > table.capacity:
            raise serializers.ValidationError({
                "guest_count": f"Guest count ({guest_count}) exceeds table capacity ({table.capacity})."
            })

        # Check overlapping bookings on the same table for [start_time, end_time)
        if table and booking_date and start_time and end_time:
            conflicting_statuses = [
                Booking.BookingStatus.PENDING,
                Booking.BookingStatus.CONFIRMED,
                Booking.BookingStatus.CHECKED_IN,
            ]
            overlapping = Booking.objects.filter(
                table=table,
                booking_date=booking_date,
                booking_status__in=conflicting_statuses,
                start_time__lt=end_time,
                end_time__gt=start_time,
            )
            if self.instance:
                overlapping = overlapping.exclude(pk=self.instance.pk)

            if overlapping.exists():
                raise serializers.ValidationError(
                    "This table already has a conflicting reservation for the selected time slot."
                )

        return data
