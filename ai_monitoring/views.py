from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils import timezone
from .models import Camera, CameraTableZone, AIEvent, ServiceAlert, MonitoringOutage
from .serializers import (
    CameraSerializer,
    CameraTableZoneSerializer,
    AIEventSerializer,
    ServiceAlertSerializer,
    MonitoringOutageSerializer,
)


class CameraViewSet(viewsets.ModelViewSet):
    queryset = Camera.objects.prefetch_related('monitored_zones').all()
    serializer_class = CameraSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ['hotel', 'restaurant', 'connection_status', 'is_active']
    search_fields = ['camera_name', 'camera_code']


class AIEventViewSet(viewsets.ModelViewSet):
    queryset = AIEvent.objects.select_related('hotel', 'restaurant', 'table', 'camera').all().order_by('-created_at')
    serializer_class = AIEventSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ['hotel', 'restaurant', 'table', 'event_type', 'validation_status']
    search_fields = ['source_event_id', 'model_name']

    def create(self, request, *args, **kwargs):
        source_id = request.data.get('source_event_id')
        if source_id and AIEvent.objects.filter(source_event_id=source_id).exists():
            return Response(
                {'detail': 'Event with this source_event_id has already been processed.'},
                status=status.HTTP_200_OK
            )
        return super().create(request, *args, **kwargs)


class ServiceAlertViewSet(viewsets.ModelViewSet):
    queryset = ServiceAlert.objects.select_related('hotel', 'restaurant', 'table', 'acknowledged_by', 'resolved_by').all().order_by('-created_at')
    serializer_class = ServiceAlertSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ['hotel', 'restaurant', 'table', 'alert_type', 'priority', 'status']

    @action(detail=True, methods=['post'])
    def acknowledge(self, request, pk=None):
        alert = self.get_object()
        alert.status = ServiceAlert.AlertStatus.ACKNOWLEDGED
        alert.acknowledged_by = request.user
        alert.acknowledged_at = timezone.now()
        alert.save()
        return Response({'status': 'Alert acknowledged'})

    @action(detail=True, methods=['post'])
    def resolve(self, request, pk=None):
        alert = self.get_object()
        alert.status = ServiceAlert.AlertStatus.RESOLVED
        alert.resolved_by = request.user
        alert.resolved_at = timezone.now()
        alert.save()
        return Response({'status': 'Alert resolved'})


class MonitoringOutageViewSet(viewsets.ModelViewSet):
    queryset = MonitoringOutage.objects.select_related('camera').all().order_by('-started_at')
    serializer_class = MonitoringOutageSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ['camera', 'outage_type']
