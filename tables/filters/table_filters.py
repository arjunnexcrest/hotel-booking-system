import django_filters
from tables.models import RestaurantTable


class TableFilter(django_filters.FilterSet):
    min_capacity = django_filters.NumberFilter(field_name='capacity', lookup_expr='gte')
    max_capacity = django_filters.NumberFilter(field_name='capacity', lookup_expr='lte')

    class Meta:
        model = RestaurantTable
        fields = ['restaurant', 'operational_status', 'table_type', 'is_active', 'min_capacity', 'max_capacity']
