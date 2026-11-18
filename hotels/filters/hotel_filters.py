import django_filters
from hotels.models import Hotel


class HotelFilter(django_filters.FilterSet):
    name = django_filters.CharFilter(lookup_expr='icontains')
    city = django_filters.CharFilter(lookup_expr='iexact')
    state = django_filters.CharFilter(lookup_expr='iexact')

    class Meta:
        model = Hotel
        fields = ['status', 'is_active', 'city', 'state', 'name']
