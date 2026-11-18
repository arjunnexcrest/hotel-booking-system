import django_filters
from bookings.models import Booking


class BookingFilter(django_filters.FilterSet):
    date_from = django_filters.DateFilter(field_name='booking_date', lookup_expr='gte')
    date_to = django_filters.DateFilter(field_name='booking_date', lookup_expr='lte')

    class Meta:
        model = Booking
        fields = ['hotel', 'restaurant', 'table', 'booking_status', 'booking_date', 'date_from', 'date_to']
