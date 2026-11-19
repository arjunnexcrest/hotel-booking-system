from datetime import datetime
from django.db import models
from django.core.exceptions import PermissionDenied
from django.utils import timezone
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import Restaurant, RestaurantImage, OperatingHours, SpecialClosure
from .serializers import (
    RestaurantSerializer,
    RestaurantImageSerializer,
    OperatingHoursSerializer,
    OperatingHoursBulkItemSerializer,
    SpecialClosureSerializer,
)
from hotels.models import Hotel
from accounts.models import User, HotelMembership


def _user_can_manage_hotel(user, hotel):
    if not user or not user.is_authenticated:
        return False
    if getattr(user, 'role', '') == User.Role.SUPER_ADMIN or user.is_superuser:
        return True
    if hotel.owner == user:
        return True
    return HotelMembership.objects.filter(
        hotel=hotel,
        user=user,
        role__in=[HotelMembership.MembershipRole.OWNER, HotelMembership.MembershipRole.ADMIN],
        is_active=True
    ).exists()


class RestaurantViewSet(viewsets.ModelViewSet):
    """
    Restaurant profiles with strict public visibility rules based on hotel approval,
    2D floor plan rendering, statistics, and schedule management.
    """
    serializer_class = RestaurantSerializer
    filterset_fields = ['hotel', 'is_active', 'cuisine_type', 'dress_code', 'price_tier']
    search_fields = ['name', 'cuisine_type', 'description']

    def get_queryset(self):
        user = self.request.user
        base_qs = Restaurant.objects.prefetch_related('images', 'operating_hours').select_related('hotel')

        # Public visitors and customers only see active restaurants of approved & active hotels
        if not user or not user.is_authenticated or getattr(user, 'role', '') == User.Role.CUSTOMER:
            return base_qs.filter(
                is_active=True,
                hotel__status=Hotel.Status.APPROVED,
                hotel__is_active=True
            ).order_by('-created_at')

        # Super admin sees all restaurants
        if getattr(user, 'role', '') == User.Role.SUPER_ADMIN or user.is_superuser:
            return base_qs.all().order_by('-created_at')

        # Hotel owners/admins/staff see their own restaurants + public active restaurants of approved hotels
        return base_qs.filter(
            models.Q(hotel__owner=user) |
            models.Q(hotel__memberships__user=user, hotel__memberships__is_active=True) |
            models.Q(is_active=True, hotel__status=Hotel.Status.APPROVED, hotel__is_active=True)
        ).distinct().order_by('-created_at')

    def get_permissions(self):
        if self.action in ['list', 'retrieve', 'floor_plan', 'stats', 'is_open']:
            return [permissions.AllowAny()]
        return [permissions.IsAuthenticated()]

    def perform_create(self, serializer):
        hotel = serializer.validated_data.get('hotel')
        user = self.request.user

        if not _user_can_manage_hotel(user, hotel):
            raise PermissionDenied("You do not have permission to create a restaurant for this hotel.")

        if hotel.status == Hotel.Status.SUSPENDED:
            raise PermissionDenied("Cannot add a restaurant to a suspended hotel.")

        serializer.save()

    def perform_update(self, serializer):
        restaurant = self.get_object()
        user = self.request.user

        if not _user_can_manage_hotel(user, restaurant.hotel):
            raise PermissionDenied("You do not have permission to modify this restaurant.")

        serializer.save()

    def perform_destroy(self, instance):
        user = self.request.user

        if not _user_can_manage_hotel(user, instance.hotel):
            raise PermissionDenied("You do not have permission to delete this restaurant.")

        instance.delete()

    @action(detail=True, methods=['get'])
    def floor_plan(self, request, pk=None):
        """
        Returns all active tables for this restaurant grouped by zone,
        including 2D layout coordinates (pos_x, pos_y), shape, and live operational status.
        """
        restaurant = self.get_object()
        tables = restaurant.tables.filter(is_active=True).order_by('table_number')

        zones = {}
        for table in tables:
            z_name = table.zone_name.strip() or 'Main Hall'
            if z_name not in zones:
                zones[z_name] = []
            zones[z_name].append({
                'id': table.id,
                'table_number': table.table_number,
                'capacity': table.capacity,
                'min_capacity': table.min_capacity,
                'table_type': table.table_type,
                'shape': table.shape,
                'pos_x': table.pos_x,
                'pos_y': table.pos_y,
                'operational_status': table.operational_status,
                'operational_status_display': table.get_operational_status_display(),
            })

        return Response({
            'restaurant_id': restaurant.id,
            'restaurant_name': restaurant.name,
            'total_tables': tables.count(),
            'zones': zones,
        })

    @action(detail=True, methods=['get'])
    def stats(self, request, pk=None):
        """Live operational table counts and capacity overview for restaurant terminal."""
        restaurant = self.get_object()
        tables = restaurant.tables.filter(is_active=True)

        counts = {
            'total_tables': tables.count(),
            'total_capacity': sum(t.capacity for t in tables),
            'available': tables.filter(operational_status='AVAILABLE').count(),
            'occupied': tables.filter(operational_status='OCCUPIED').count(),
            'awaiting_cleaning': tables.filter(operational_status='AWAITING_CLEANING').count(),
            'cleaning_in_progress': tables.filter(operational_status='CLEANING_IN_PROGRESS').count(),
            'service_required': tables.filter(operational_status='SERVICE_REQUIRED').count(),
            'maintenance': tables.filter(operational_status='MAINTENANCE').count(),
            'temporarily_blocked': tables.filter(operational_status='TEMPORARILY_BLOCKED').count(),
        }
        return Response(counts)

    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def bulk_operating_hours(self, request, pk=None):
        """Batch set or update the full weekly operating schedule (0=Monday to 6=Sunday)."""
        restaurant = self.get_object()
        if not _user_can_manage_hotel(request.user, restaurant.hotel):
            raise PermissionDenied("You do not have permission to manage schedules for this restaurant.")

        schedules = request.data
        if not isinstance(schedules, list):
            return Response({'error': 'Expected a list of schedule objects.'}, status=status.HTTP_400_BAD_REQUEST)

        serializer = OperatingHoursBulkItemSerializer(data=schedules, many=True)
        serializer.is_valid(raise_exception=True)

        created_or_updated = []
        for item in serializer.validated_data:
            obj, _ = OperatingHours.objects.update_or_create(
                restaurant=restaurant,
                day_of_week=item['day_of_week'],
                defaults={
                    'opening_time': item.get('opening_time', '09:00:00'),
                    'closing_time': item.get('closing_time', '22:00:00'),
                    'is_closed': item.get('is_closed', False),
                }
            )
            created_or_updated.append(obj)

        out_serializer = OperatingHoursSerializer(created_or_updated, many=True)
        return Response({'status': 'Weekly hours updated', 'schedules': out_serializer.data})

    @action(detail=True, methods=['get'])
    def is_open(self, request, pk=None):
        """
        Evaluate if this restaurant is open at a given datetime (defaulting to now).
        Takes into account hotel approval, restaurant active state, special closures, and weekly hours.
        """
        restaurant = self.get_object()

        dt_param = request.query_params.get('datetime')
        if dt_param:
            try:
                target_dt = datetime.fromisoformat(dt_param.replace('Z', '+00:00'))
            except ValueError:
                return Response({'error': 'Invalid datetime format. Use ISO format (YYYY-MM-DDTHH:MM:SS)'}, status=status.HTTP_400_BAD_REQUEST)
        else:
            target_dt = timezone.localtime()

        # 1. Base status checks
        if not restaurant.is_active:
            return Response({'is_open': False, 'reason': 'Restaurant is inactive.'})
        if restaurant.hotel.status != Hotel.Status.APPROVED or not restaurant.hotel.is_active:
            return Response({'is_open': False, 'reason': 'Hotel is not approved or inactive.'})

        target_date = target_dt.date()
        target_time = target_dt.time()
        target_day = target_dt.weekday()  # 0=Monday, 6=Sunday

        # 2. Check special closures
        closure = restaurant.special_closures.filter(closure_date=target_date).first()
        if closure:
            if closure.is_all_day:
                return Response({'is_open': False, 'reason': f"Special closure: {closure.reason}"})
            if closure.start_time and closure.end_time and closure.start_time <= target_time <= closure.end_time:
                return Response({'is_open': False, 'reason': f"Special closure ({closure.reason}): {closure.start_time} - {closure.end_time}"})

        # 3. Check weekly operating hours
        hours = restaurant.operating_hours.filter(day_of_week=target_day).first()
        if not hours or hours.is_closed:
            return Response({'is_open': False, 'reason': f"Closed on {target_dt.strftime('%A')}."})

        if hours.opening_time <= target_time <= hours.closing_time:
            return Response({
                'is_open': True,
                'opening_time': str(hours.opening_time),
                'closing_time': str(hours.closing_time),
                'day': target_dt.strftime('%A')
            })

        return Response({
            'is_open': False,
            'reason': f"Outside operating hours ({hours.opening_time} - {hours.closing_time})."
        })


class RestaurantImageViewSet(viewsets.ModelViewSet):
    queryset = RestaurantImage.objects.select_related('restaurant').all()
    serializer_class = RestaurantImageSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    filterset_fields = ['restaurant']

    def perform_create(self, serializer):
        restaurant = serializer.validated_data.get('restaurant')
        if not _user_can_manage_hotel(self.request.user, restaurant.hotel):
            raise PermissionDenied("You do not have permission to upload images for this restaurant.")
        serializer.save()


class OperatingHoursViewSet(viewsets.ModelViewSet):
    serializer_class = OperatingHoursSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    filterset_fields = ['restaurant', 'day_of_week', 'is_closed']

    def get_queryset(self):
        return OperatingHours.objects.select_related('restaurant__hotel').all().order_by('day_of_week')

    def perform_create(self, serializer):
        restaurant = serializer.validated_data.get('restaurant')
        if not _user_can_manage_hotel(self.request.user, restaurant.hotel):
            raise PermissionDenied("You do not have permission to manage operating hours for this restaurant.")
        serializer.save()


class SpecialClosureViewSet(viewsets.ModelViewSet):
    serializer_class = SpecialClosureSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    filterset_fields = ['restaurant', 'closure_date']

    def get_queryset(self):
        return SpecialClosure.objects.select_related('restaurant__hotel').all().order_by('-closure_date')

    def perform_create(self, serializer):
        restaurant = serializer.validated_data.get('restaurant')
        if not _user_can_manage_hotel(self.request.user, restaurant.hotel):
            raise PermissionDenied("You do not have permission to manage special closures for this restaurant.")
        serializer.save()
