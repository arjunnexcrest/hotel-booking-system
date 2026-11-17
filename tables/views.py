from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import RestaurantTable, TableZone, TableEvent
from .serializers import (
    RestaurantTableSerializer,
    TableZoneSerializer,
    TableEventSerializer,
)


class RestaurantTableViewSet(viewsets.ModelViewSet):
    queryset = RestaurantTable.objects.prefetch_related('monitoring_zones').all().order_by('table_number')
    serializer_class = RestaurantTableSerializer
    filterset_fields = ['restaurant', 'operational_status', 'table_type', 'is_active', 'capacity']
    search_fields = ['table_number', 'zone_name', 'description']

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [permissions.AllowAny()]
        return [permissions.IsAuthenticated()]

    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def update_status(self, request, pk=None):
        table = self.get_object()
        new_status = request.data.get('operational_status')
        reason = request.data.get('reason', 'Manual status update')
        if not new_status or new_status not in RestaurantTable.OperationalStatus.values:
            return Response({'error': 'Invalid operational_status'}, status=status.HTTP_400_BAD_REQUEST)

        old_status = table.operational_status
        table.operational_status = new_status
        table.save()

        TableEvent.objects.create(
            table=table,
            from_status=old_status,
            to_status=new_status,
            triggered_by=TableEvent.Trigger.ADMIN,
            actor=request.user,
            reason=reason
        )
        return Response({
            'status': 'Status updated',
            'table_id': table.id,
            'operational_status': table.operational_status
        })


class TableZoneViewSet(viewsets.ModelViewSet):
    queryset = TableZone.objects.all()
    serializer_class = TableZoneSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ['table']


class TableEventViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = TableEvent.objects.select_related('table', 'actor').all().order_by('-created_at')
    serializer_class = TableEventSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ['table', 'triggered_by', 'to_status']
