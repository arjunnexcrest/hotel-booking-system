from django.db import models
from django.conf import settings
from core.models import TimeStampedModel


class Camera(TimeStampedModel):
    """
    CCTV/IP Camera device configured in a restaurant.
    """
    class ConnectionStatus(models.TextChoices):
        CONNECTED = 'CONNECTED', 'Connected'
        DISCONNECTED = 'DISCONNECTED', 'Disconnected'
        ERROR = 'ERROR', 'Error'

    hotel = models.ForeignKey(
        'hotels.Hotel',
        on_delete=models.CASCADE,
        related_name='cameras'
    )
    restaurant = models.ForeignKey(
        'restaurants.Restaurant',
        on_delete=models.CASCADE,
        related_name='cameras'
    )
    camera_name = models.CharField(max_length=150)
    camera_code = models.CharField(max_length=50, unique=True)
    location_description = models.CharField(max_length=255, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    stream_url = models.CharField(max_length=500, blank=True)
    connection_status = models.CharField(
        max_length=20,
        choices=ConnectionStatus.choices,
        default=ConnectionStatus.CONNECTED,
    )
    is_active = models.BooleanField(default=True)
    last_heartbeat_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'cameras'

    def __str__(self):
        return f"{self.camera_name} ({self.camera_code}) - {self.restaurant.name}"


class CameraTableZone(TimeStampedModel):
    """
    Mapping between a camera feed and a table's physical monitoring zone.
    """
    camera = models.ForeignKey(
        Camera,
        on_delete=models.CASCADE,
        related_name='monitored_zones'
    )
    table_zone = models.ForeignKey(
        'tables.TableZone',
        on_delete=models.CASCADE,
        related_name='camera_associations'
    )
    confidence_threshold = models.FloatField(default=0.75)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'camera_table_zones'
        unique_together = ('camera', 'table_zone')

    def __str__(self):
        return f"{self.camera.camera_name} -> {self.table_zone.zone_identifier}"


class AIEvent(TimeStampedModel):
    """
    Raw observation event received from the computer vision pipeline.
    Must be validated by business rules before table states are updated.
    """
    class EventType(models.TextChoices):
        OCCUPANCY_DETECTED = 'OCCUPANCY_DETECTED', 'Occupancy Detected'
        OCCUPANCY_RELEASED = 'OCCUPANCY_RELEASED', 'Occupancy Released / Customer Departure'
        WAITER_DETECTED = 'WAITER_DETECTED', 'Waiter Present'
        WAITER_MISSING = 'WAITER_MISSING', 'Waiter Missing / Service Threshold Exceeded'
        CLEANLINESS_CLEAN = 'CLEANLINESS_CLEAN', 'Table Clean'
        CLEANLINESS_DIRTY = 'CLEANLINESS_DIRTY', 'Table Dirty / Not Ready'
        CLEANLINESS_UNCERTAIN = 'CLEANLINESS_UNCERTAIN', 'Cleanliness Uncertain'

    class ValidationStatus(models.TextChoices):
        PENDING = 'PENDING', 'Pending Validation'
        VALIDATED = 'VALIDATED', 'Validated & Applied'
        REJECTED = 'REJECTED', 'Rejected by Rule'
        IGNORED = 'IGNORED', 'Ignored / Low Confidence'

    hotel = models.ForeignKey(
        'hotels.Hotel',
        on_delete=models.CASCADE,
        related_name='ai_events'
    )
    restaurant = models.ForeignKey(
        'restaurants.Restaurant',
        on_delete=models.CASCADE,
        related_name='ai_events'
    )
    table = models.ForeignKey(
        'tables.RestaurantTable',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='ai_events'
    )
    camera = models.ForeignKey(
        Camera,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='ai_events'
    )
    source_event_id = models.CharField(max_length=100, unique=True)
    event_type = models.CharField(max_length=50, choices=EventType.choices)
    confidence_score = models.FloatField()
    model_name = models.CharField(max_length=100, default='yolo-table-monitor')
    model_version = models.CharField(max_length=50, default='v1.0')
    validation_status = models.CharField(
        max_length=20,
        choices=ValidationStatus.choices,
        default=ValidationStatus.PENDING,
    )
    raw_payload = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = 'ai_events'
        indexes = [
            models.Index(fields=['table', 'event_type']),
            models.Index(fields=['hotel', 'created_at']),
            models.Index(fields=['source_event_id']),
        ]

    def __str__(self):
        return f"{self.event_type} on Table {self.table.table_number if self.table else 'N/A'} ({self.confidence_score:.2f})"


class ServiceAlert(TimeStampedModel):
    """
    Operational alerts triggered by service delays, uncleaned tables, or hardware issues.
    """
    class AlertType(models.TextChoices):
        MISSING_WAITER = 'MISSING_WAITER', 'Waiter Attention Required'
        CLEANING_REQUIRED = 'CLEANING_REQUIRED', 'Table Cleaning Required'
        CLEANING_VERIFICATION_FAILED = 'CLEANING_VERIFICATION_FAILED', 'Cleanliness Verification Failed'
        CAMERA_DISCONNECTED = 'CAMERA_DISCONNECTED', 'Camera Disconnected'
        AI_SERVICE_OUTAGE = 'AI_SERVICE_OUTAGE', 'AI Service Outage'
        MAINTENANCE_REQUIRED = 'MAINTENANCE_REQUIRED', 'Table Maintenance Required'

    class Priority(models.TextChoices):
        LOW = 'LOW', 'Low'
        MEDIUM = 'MEDIUM', 'Medium'
        HIGH = 'HIGH', 'High'
        CRITICAL = 'CRITICAL', 'Critical'

    class AlertStatus(models.TextChoices):
        NEW = 'NEW', 'New'
        ACKNOWLEDGED = 'ACKNOWLEDGED', 'Acknowledged'
        IN_PROGRESS = 'IN_PROGRESS', 'In Progress'
        RESOLVED = 'RESOLVED', 'Resolved'
        DISMISSED = 'DISMISSED', 'Dismissed'

    hotel = models.ForeignKey(
        'hotels.Hotel',
        on_delete=models.CASCADE,
        related_name='service_alerts'
    )
    restaurant = models.ForeignKey(
        'restaurants.Restaurant',
        on_delete=models.CASCADE,
        related_name='service_alerts'
    )
    table = models.ForeignKey(
        'tables.RestaurantTable',
        on_delete=models.CASCADE,
        related_name='service_alerts'
    )
    ai_event = models.ForeignKey(
        AIEvent,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='service_alerts'
    )
    alert_type = models.CharField(max_length=50, choices=AlertType.choices)
    priority = models.CharField(max_length=20, choices=Priority.choices, default=Priority.MEDIUM)
    status = models.CharField(max_length=20, choices=AlertStatus.choices, default=AlertStatus.NEW)
    message = models.TextField()

    acknowledged_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='acknowledged_alerts'
    )
    acknowledged_at = models.DateTimeField(null=True, blank=True)

    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='resolved_alerts'
    )
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'service_alerts'
        indexes = [
            models.Index(fields=['hotel', 'status']),
            models.Index(fields=['table', 'alert_type']),
        ]

    def __str__(self):
        return f"[{self.get_priority_display()}] {self.get_alert_type_display()} - Table {self.table.table_number}"


class MonitoringOutage(TimeStampedModel):
    """
    Log of camera disconnections, model errors, or pipeline outages.
    """
    camera = models.ForeignKey(Camera, on_delete=models.CASCADE, related_name='outages')
    outage_type = models.CharField(max_length=50)
    started_at = models.DateTimeField()
    resolved_at = models.DateTimeField(null=True, blank=True)
    description = models.TextField(blank=True)

    class Meta:
        db_table = 'monitoring_outages'

    def __str__(self):
        return f"Outage for {self.camera.camera_name} ({self.outage_type})"
