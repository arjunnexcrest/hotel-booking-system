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
        from .services.ai_service import AIService
        from hotels.models import Hotel
        from restaurants.models import Restaurant
        from tables.models import RestaurantTable
        from .models import Camera

        data = request.data
        source_id = data.get('source_event_id')
        if not source_id:
            return Response({'error': 'source_event_id is required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            hotel = Hotel.objects.get(id=data.get('hotel'))
            restaurant = Restaurant.objects.get(id=data.get('restaurant'))
        except (Hotel.DoesNotExist, Restaurant.DoesNotExist) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

        table = None
        if data.get('table'):
            table = RestaurantTable.objects.filter(id=data.get('table')).first()

        camera = None
        if data.get('camera'):
            camera = Camera.objects.filter(id=data.get('camera')).first()

        event, is_new = AIService.process_incoming_event(
            hotel=hotel,
            restaurant=restaurant,
            table=table,
            camera=camera,
            source_event_id=source_id,
            event_type=data.get('event_type'),
            confidence_score=float(data.get('confidence_score', 0.8)),
            model_name=data.get('model_name', 'yolo-table-monitor'),
            model_version=data.get('model_version', 'v1.0'),
            raw_payload=data.get('raw_payload', {})
        )

        serializer = self.get_serializer(event)
        status_code = status.HTTP_201_CREATED if is_new else status.HTTP_200_OK
        return Response(serializer.data, status=status_code)


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
