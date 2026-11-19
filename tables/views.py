from django.db import models
from django.core.exceptions import PermissionDenied
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import RestaurantTable, TableZone, TableEvent
from .serializers import (
    RestaurantTableSerializer,
    TableZoneSerializer,
    TableEventSerializer,
    TableBulkCreateSerializer,
    TableBulkStatusUpdateSerializer,
)
from hotels.models import Hotel
from accounts.models import User, HotelMembership


def _user_can_manage_table(user, table):
    if not user or not user.is_authenticated:
        return False
    if getattr(user, 'role', '') == User.Role.SUPER_ADMIN or user.is_superuser:
        return True
    hotel = table.restaurant.hotel
    if hotel.owner == user:
        return True
    return HotelMembership.objects.filter(
        hotel=hotel,
        user=user,
        role__in=[HotelMembership.MembershipRole.OWNER, HotelMembership.MembershipRole.ADMIN, HotelMembership.MembershipRole.STAFF],
        is_active=True
    ).exists()


class RestaurantTableViewSet(viewsets.ModelViewSet):
    """
    Dining tables with live status updates, AI-monitoring zones, and strict public visibility rules.
    """
    serializer_class = RestaurantTableSerializer
    filterset_fields = ['restaurant', 'operational_status', 'table_type', 'is_active', 'capacity']
    search_fields = ['table_number', 'zone_name', 'description']

    def get_queryset(self):
        user = self.request.user
        base_qs = RestaurantTable.objects.prefetch_related('monitoring_zones').select_related('restaurant__hotel')

        # Public visitors and customers only see active tables of active restaurants in approved & active hotels
        if not user or not user.is_authenticated or getattr(user, 'role', '') == User.Role.CUSTOMER:
            return base_qs.filter(
                is_active=True,
                restaurant__is_active=True,
                restaurant__hotel__status=Hotel.Status.APPROVED,
                restaurant__hotel__is_active=True
            ).order_by('table_number')

        # Super admin sees all tables
        if getattr(user, 'role', '') == User.Role.SUPER_ADMIN or user.is_superuser:
            return base_qs.all().order_by('table_number')

        # Hotel owners/staff see tables belonging to their hotels + public tables
        return base_qs.filter(
            models.Q(restaurant__hotel__owner=user) |
            models.Q(restaurant__hotel__memberships__user=user, restaurant__hotel__memberships__is_active=True) |
            models.Q(
                is_active=True,
                restaurant__is_active=True,
                restaurant__hotel__status=Hotel.Status.APPROVED,
                restaurant__hotel__is_active=True
            )
        ).distinct().order_by('table_number')

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [permissions.AllowAny()]
        return [permissions.IsAuthenticated()]

    def perform_create(self, serializer):
        restaurant = serializer.validated_data.get('restaurant')
        user = self.request.user
        hotel = restaurant.hotel

        has_access = (
            getattr(user, 'role', '') == User.Role.SUPER_ADMIN
            or user.is_superuser
            or hotel.owner == user
            or HotelMembership.objects.filter(
                hotel=hotel,
                user=user,
                role__in=[HotelMembership.MembershipRole.OWNER, HotelMembership.MembershipRole.ADMIN],
                is_active=True
            ).exists()
        )
        if not has_access:
            raise PermissionDenied("You do not have permission to add tables to this hotel's restaurant.")

        serializer.save()

    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def update_status(self, request, pk=None):
        table = self.get_object()
        if not _user_can_manage_table(request.user, table):
            raise PermissionDenied("You do not have permission to update table operational status for this property.")

        new_status = request.data.get('operational_status')
        reason = request.data.get('reason', 'Manual status update')
        if not new_status or new_status not in RestaurantTable.OperationalStatus.values:
            return Response(
                {'error': f"Invalid operational_status. Choose from {RestaurantTable.OperationalStatus.values}"},
                status=status.HTTP_400_BAD_REQUEST
            )

        old_status = table.operational_status
        table.operational_status = new_status
        table.save(update_fields=['operational_status', 'updated_at'])

        event = TableEvent.objects.create(
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
            'operational_status': table.operational_status,
            'event_id': event.id
        })

    @action(detail=False, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def bulk_create(self, request):
        """Batch generate dining tables for a restaurant."""
        serializer = TableBulkCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        restaurant = data['restaurant']
        user = request.user
        hotel = restaurant.hotel

        has_access = (
            getattr(user, 'role', '') == User.Role.SUPER_ADMIN
            or user.is_superuser
            or hotel.owner == user
            or HotelMembership.objects.filter(
                hotel=hotel,
                user=user,
                role__in=[HotelMembership.MembershipRole.OWNER, HotelMembership.MembershipRole.ADMIN],
                is_active=True
            ).exists()
        )
        if not has_access:
            raise PermissionDenied("You do not have permission to manage tables for this hotel.")

        created_tables = []
        prefix = data['prefix']
        start_num = data['start_number']
        count = data['count']

        for i in range(count):
            num_str = f"{prefix}{start_num + i}"
            # Check or skip existing table numbers
            if RestaurantTable.objects.filter(restaurant=restaurant, table_number=num_str).exists():
                continue

            tbl = RestaurantTable.objects.create(
                restaurant=restaurant,
                table_number=num_str,
                capacity=data['capacity'],
                min_capacity=data['min_capacity'],
                table_type=data['table_type'],
                shape=data['shape'],
                zone_name=data['zone_name'],
                operational_status=RestaurantTable.OperationalStatus.AVAILABLE,
                is_active=True,
            )
            created_tables.append(tbl)

        out_serializer = RestaurantTableSerializer(created_tables, many=True)
        return Response({
            'status': 'Tables batch created',
            'created_count': len(created_tables),
            'tables': out_serializer.data
        }, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def bulk_status_update(self, request):
        """Batch update operational status for multiple tables (e.g. bulk turnover cleaning)."""
        serializer = TableBulkStatusUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        target_status = data['operational_status']
        reason = data['reason']
        table_ids = data['table_ids']

        tables = RestaurantTable.objects.filter(id__in=table_ids).select_related('restaurant__hotel')
        updated_count = 0
        events_to_create = []

        for table in tables:
            if not _user_can_manage_table(request.user, table):
                continue
            old_status = table.operational_status
            table.operational_status = target_status
            table.save(update_fields=['operational_status', 'updated_at'])
            updated_count += 1

            events_to_create.append(TableEvent(
                table=table,
                from_status=old_status,
                to_status=target_status,
                triggered_by=TableEvent.Trigger.STAFF,
                actor=request.user,
                reason=reason
            ))

        if events_to_create:
            TableEvent.objects.bulk_create(events_to_create)

        return Response({
            'status': 'Batch status update complete',
            'updated_count': updated_count,
            'target_status': target_status
        })


class TableZoneViewSet(viewsets.ModelViewSet):
    serializer_class = TableZoneSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ['table']

    def get_queryset(self):
        user = self.request.user
        base_qs = TableZone.objects.select_related('table__restaurant__hotel')
        if getattr(user, 'role', '') == User.Role.SUPER_ADMIN or user.is_superuser:
            return base_qs.all()
        return base_qs.filter(
            models.Q(table__restaurant__hotel__owner=user) |
            models.Q(table__restaurant__hotel__memberships__user=user, table__restaurant__hotel__memberships__is_active=True)
        ).distinct()


class TableEventViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = TableEventSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        base_qs = TableEvent.objects.select_related('table__restaurant__hotel', 'actor').order_by('-created_at')
        if getattr(user, 'role', '') == User.Role.SUPER_ADMIN or user.is_superuser:
            return base_qs.all()
        return base_qs.filter(
            models.Q(table__restaurant__hotel__owner=user) |
            models.Q(table__restaurant__hotel__memberships__user=user, table__restaurant__hotel__memberships__is_active=True)
        ).distinct()
