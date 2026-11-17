from django.contrib import admin
from .models import RestaurantTable, TableZone, TableEvent


class TableZoneInline(admin.TabularInline):
    model = TableZone
    extra = 1


@admin.register(RestaurantTable)
class RestaurantTableAdmin(admin.ModelAdmin):
    list_display = (
        'table_number',
        'restaurant',
        'capacity',
        'table_type',
        'zone_name',
        'operational_status',
        'is_active',
    )
    list_filter = ('operational_status', 'table_type', 'is_active', 'restaurant')
    search_fields = ('table_number', 'restaurant__name', 'zone_name')
    inlines = [TableZoneInline]


@admin.register(TableZone)
class TableZoneAdmin(admin.ModelAdmin):
    list_display = ('zone_identifier', 'table')
    search_fields = ('zone_identifier', 'table__table_number')


@admin.register(TableEvent)
class TableEventAdmin(admin.ModelAdmin):
    list_display = ('table', 'from_status', 'to_status', 'triggered_by', 'actor', 'created_at')
    list_filter = ('triggered_by', 'to_status', 'created_at')
    search_fields = ('table__table_number', 'reason')
