from django.utils import timezone
from notifications.models import Notification, NotificationDelivery


class NotificationService:
    @staticmethod
    def send_notification(recipient, title, message, notification_type, hotel=None, channels=None):
        """
        Creates a notification record and initializes delivery tracking for each channel.
        """
        if channels is None:
            channels = [NotificationDelivery.Channel.IN_APP, NotificationDelivery.Channel.EMAIL]

        notification = Notification.objects.create(
            recipient=recipient,
            hotel=hotel,
            title=title,
            message=message,
            notification_type=notification_type,
        )

        deliveries = []
        for channel in channels:
            delivery = NotificationDelivery.objects.create(
                notification=notification,
                channel=channel,
                status=NotificationDelivery.DeliveryStatus.DELIVERED if channel == NotificationDelivery.Channel.IN_APP else NotificationDelivery.DeliveryStatus.SENT,
                sent_at=timezone.now(),
            )
            deliveries.append(delivery)

        return notification, deliveries
