from django.db import models
from django.conf import settings
from core.models import TimeStampedModel


class RestaurantTable(TimeStampedModel):
    """
    Physical dining table in a restaurant.
    operational_status records physical condition, distinct from booking status.
    """
    class OperationalStatus(models.TextChoices):
        AVAILABLE = 'AVAILABLE', 'Available'
        OCCUPIED = 'OCCUPIED', 'Occupied'
        AWAITING_CLEANING = 'AWAITING_CLEANING', 'Awaiting Cleaning'
        CLEANING_IN_PROGRESS = 'CLEANING_IN_PROGRESS', 'Cleaning In Progress'
        SERVICE_REQUIRED = 'SERVICE_REQUIRED', 'Service Required'
        MAINTENANCE = 'MAINTENANCE', 'Maintenance'
        TEMPORARILY_BLOCKED = 'TEMPORARILY_BLOCKED', 'Temporarily Blocked'

    class TableType(models.TextChoices):
        STANDARD = 'STANDARD', 'Standard Table'
        BOOTH = 'BOOTH', 'Booth'
        OUTDOOR = 'OUTDOOR', 'Outdoor Table'
        VIP = 'VIP', 'VIP Table'
        BAR = 'BAR', 'Bar Counter'

    class TableShape(models.TextChoices):
        RECTANGULAR = 'RECTANGULAR', 'Rectangular'
        CIRCULAR = 'CIRCULAR', 'Circular'
        SQUARE = 'SQUARE', 'Square'

    restaurant = models.ForeignKey(
        'restaurants.Restaurant',
        on_delete=models.CASCADE,
        related_name='tables'
    )
    table_number = models.CharField(max_length=50)
    capacity = models.PositiveIntegerField(default=2)
    min_capacity = models.PositiveIntegerField(default=1)
    table_type = models.CharField(
        max_length=30,
        choices=TableType.choices,
        default=TableType.STANDARD,
    )
    shape = models.CharField(
        max_length=20,
        choices=TableShape.choices,
        default=TableShape.RECTANGULAR,
    )
    zone_name = models.CharField(max_length=100, blank=True)
    pos_x = models.FloatField(default=0.0)
    pos_y = models.FloatField(default=0.0)
    description = models.TextField(blank=True)
    operational_status = models.CharField(
        max_length=30,
        choices=OperationalStatus.choices,
        default=OperationalStatus.AVAILABLE,
    )
    is_active = models.BooleanField(default=True)
    qr_code_url = models.CharField(max_length=500, blank=True)

    class Meta:
        db_table = 'restaurant_tables'
        unique_together = ('restaurant', 'table_number')
        indexes = [
            models.Index(fields=['restaurant', 'operational_status']),
            models.Index(fields=['restaurant', 'capacity']),
        ]

    def __str__(self):
        return f"{self.restaurant.name} - Table {self.table_number} [{self.get_operational_status_display()}]"


class TableZone(TimeStampedModel):
    """
    Physical polygon region in camera field-of-view mapped to a table.
    """
    table = models.ForeignKey(
        RestaurantTable,
        on_delete=models.CASCADE,
        related_name='monitoring_zones'
    )
    zone_identifier = models.CharField(max_length=100)
    polygon_coordinates = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = 'table_zones'

    def __str__(self):
        return f"Zone {self.zone_identifier} (Table {self.table.table_number})"


class TableEvent(TimeStampedModel):
    """
    Physical condition transitions logged when a table's operational state changes.
    """
    class Trigger(models.TextChoices):
        AI_DETECTION = 'AI_DETECTION', 'AI Detection'
        STAFF = 'STAFF', 'Staff Action'
        ADMIN = 'ADMIN', 'Admin Manual Override'
        BOOKING_FLOW = 'BOOKING_FLOW', 'Booking Flow'
        SYSTEM = 'SYSTEM', 'System Rule'

    table = models.ForeignKey(
        RestaurantTable,
        on_delete=models.CASCADE,
        related_name='status_events'
    )
    from_status = models.CharField(max_length=30)
    to_status = models.CharField(max_length=30)
    triggered_by = models.CharField(max_length=30, choices=Trigger.choices)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='triggered_table_events'
    )
    reason = models.TextField(blank=True)

    class Meta:
        db_table = 'table_events'
        indexes = [
            models.Index(fields=['table', 'created_at']),
        ]

    def __str__(self):
        return f"Table {self.table.table_number}: {self.from_status} -> {self.to_status} via {self.triggered_by}"
