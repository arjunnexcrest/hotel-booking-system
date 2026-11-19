from django.contrib import admin
from .models import Camera, CameraTableZone, AIEvent, ServiceAlert, MonitoringOutage


class CameraTableZoneInline(admin.TabularInline):
    model = CameraTableZone
    extra = 1


@admin.register(Camera)
class CameraAdmin(admin.ModelAdmin):
    list_display = ('camera_name', 'camera_code', 'hotel', 'restaurant', 'connection_status', 'is_active', 'last_heartbeat_at')
    list_filter = ('connection_status', 'is_active', 'hotel', 'restaurant')
    search_fields = ('camera_name', 'camera_code', 'ip_address')
    inlines = [CameraTableZoneInline]


@admin.register(AIEvent)
class AIEventAdmin(admin.ModelAdmin):
    list_display = ('source_event_id', 'event_type', 'table', 'confidence_score', 'validation_status', 'created_at')
    list_filter = ('event_type', 'validation_status', 'hotel')
    search_fields = ('source_event_id', 'model_name')
    readonly_fields = ('source_event_id', 'created_at')


@admin.register(ServiceAlert)
class ServiceAlertAdmin(admin.ModelAdmin):
    list_display = ('alert_type', 'table', 'hotel', 'priority', 'status', 'created_at')
    list_filter = ('alert_type', 'priority', 'status', 'hotel')
    search_fields = ('table__table_number', 'message')


@admin.register(MonitoringOutage)
class MonitoringOutageAdmin(admin.ModelAdmin):
    list_display = ('camera', 'outage_type', 'started_at', 'resolved_at')
    list_filter = ('outage_type', 'camera')
