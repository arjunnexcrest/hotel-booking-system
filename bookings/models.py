import uuid
from django.db import models
from django.conf import settings
from core.models import TimeStampedModel


def generate_booking_reference():
    return f"BK-{uuid.uuid4().hex[:8].upper()}"


class Booking(TimeStampedModel):
    """
    Customer table reservation.
    Time range is evaluated as [start_time, end_time) to prevent overlapping bookings.
    """
    class BookingStatus(models.TextChoices):
        PENDING = 'PENDING', 'Pending Confirmation'
        CONFIRMED = 'CONFIRMED', 'Confirmed'
        REJECTED = 'REJECTED', 'Rejected'
        CANCELLED = 'CANCELLED', 'Cancelled'
        CHECKED_IN = 'CHECKED_IN', 'Checked In'
        COMPLETED = 'COMPLETED', 'Completed'
        NO_SHOW = 'NO_SHOW', 'No Show'

    booking_reference = models.CharField(
        max_length=32,
        unique=True,
        default=generate_booking_reference,
        editable=False,
    )
    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='bookings'
    )
    customer_name = models.CharField(max_length=150)
    customer_email = models.EmailField()
    customer_phone = models.CharField(max_length=30)

    hotel = models.ForeignKey(
        'hotels.Hotel',
        on_delete=models.CASCADE,
        related_name='bookings'
    )
    restaurant = models.ForeignKey(
        'restaurants.Restaurant',
        on_delete=models.CASCADE,
        related_name='bookings'
    )
    table = models.ForeignKey(
        'tables.RestaurantTable',
        on_delete=models.CASCADE,
        related_name='bookings'
    )

    booking_date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    guest_count = models.PositiveIntegerField(default=2)
    special_requests = models.TextField(blank=True)

    booking_status = models.CharField(
        max_length=30,
        choices=BookingStatus.choices,
        default=BookingStatus.PENDING,
    )
    cancellation_reason = models.TextField(blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'bookings'
        indexes = [
            models.Index(fields=['table', 'booking_date', 'booking_status']),
            models.Index(fields=['hotel', 'booking_date']),
            models.Index(fields=['booking_reference']),
            models.Index(fields=['customer', 'booking_date']),
        ]

    def __str__(self):
        return f"{self.booking_reference} - {self.table} on {self.booking_date} ({self.get_booking_status_display()})"


class BookingHistory(TimeStampedModel):
    """
    Audit log of booking lifecycle transitions.
    """
    booking = models.ForeignKey(
        Booking,
        on_delete=models.CASCADE,
        related_name='history'
    )
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='booking_status_changes'
    )
    previous_status = models.CharField(max_length=30)
    new_status = models.CharField(max_length=30)
    reason = models.TextField(blank=True)

    class Meta:
        db_table = 'booking_history'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.booking.booking_reference}: {self.previous_status} -> {self.new_status}"
