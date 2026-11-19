from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils import timezone
from .models import Notification, NotificationDelivery
from .serializers import NotificationSerializer, NotificationDeliverySerializer


class NotificationViewSet(viewsets.ModelViewSet):
    queryset = Notification.objects.all()
    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ['hotel', 'notification_type', 'is_read']

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False) or not self.request.user.is_authenticated:
            return Notification.objects.none()
        return Notification.objects.filter(recipient=self.request.user).prefetch_related('deliveries').order_by('-created_at')

    @action(detail=True, methods=['post'])
    def mark_as_read(self, request, pk=None):
        notification = self.get_object()
        notification.is_read = True
        notification.read_at = timezone.now()
        notification.save()
        return Response({'status': 'Marked as read'})

    @action(detail=False, methods=['post'])
    def mark_all_as_read(self, request):
        self.get_queryset().filter(is_read=False).update(is_read=True, read_at=timezone.now())
        return Response({'status': 'All notifications marked as read'})


class NotificationDeliveryViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = NotificationDelivery.objects.select_related('notification').all().order_by('-created_at')
    serializer_class = NotificationDeliverySerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ['channel', 'status']
