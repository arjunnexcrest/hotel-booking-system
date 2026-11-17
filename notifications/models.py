from django.db import models
from django.conf import settings
from core.models import TimeStampedModel


class Notification(TimeStampedModel):
    """
    User notification records for bookings, approvals, and AI service alerts.
    """
    class NotificationType(models.TextChoices):
        BOOKING_CONFIRMATION = 'BOOKING_CONFIRMATION', 'Booking Confirmation'
        BOOKING_CANCELLATION = 'BOOKING_CANCELLATION', 'Booking Cancellation'
        BOOKING_REMINDER = 'BOOKING_REMINDER', 'Booking Reminder'
        SERVICE_ALERT = 'SERVICE_ALERT', 'Service Alert'
        CLEANING_TASK = 'CLEANING_TASK', 'Cleaning Task Assignment'
        HOTEL_APPROVAL = 'HOTEL_APPROVAL', 'Hotel Approval Status'
        SYSTEM_ALERT = 'SYSTEM_ALERT', 'System Alert'

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notifications'
    )
    hotel = models.ForeignKey(
        'hotels.Hotel',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='notifications'
    )
    title = models.CharField(max_length=255)
    message = models.TextField()
    notification_type = models.CharField(
        max_length=50,
        choices=NotificationType.choices,
        default=NotificationType.SYSTEM_ALERT,
    )
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'notifications'
        indexes = [
            models.Index(fields=['recipient', 'is_read']),
        ]

    def __str__(self):
        return f"{self.title} -> {self.recipient.email}"


class NotificationDelivery(TimeStampedModel):
    """
    Per-channel delivery tracking and retry history.
    """
    class Channel(models.TextChoices):
        IN_APP = 'IN_APP', 'In-App Notification'
        EMAIL = 'EMAIL', 'Email'
        SMS = 'SMS', 'SMS'
        PUSH = 'PUSH', 'Push Notification'
        WHATSAPP = 'WHATSAPP', 'WhatsApp'

    class DeliveryStatus(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        SENT = 'SENT', 'Sent'
        DELIVERED = 'DELIVERED', 'Delivered'
        FAILED = 'FAILED', 'Failed'

    notification = models.ForeignKey(
        Notification,
        on_delete=models.CASCADE,
        related_name='deliveries'
    )
    channel = models.CharField(max_length=20, choices=Channel.choices)
    status = models.CharField(
        max_length=20,
        choices=DeliveryStatus.choices,
        default=DeliveryStatus.PENDING,
    )
    attempt_count = models.PositiveIntegerField(default=1)
    error_message = models.TextField(blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'notification_deliveries'

    def __str__(self):
        return f"{self.notification.id} via {self.channel} [{self.status}]"
