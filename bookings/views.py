from datetime import datetime, date, timedelta
from django.db import models
from django.core.exceptions import PermissionDenied, ValidationError as DjangoValidationError
from django.utils import timezone
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import Booking, BookingHistory
from .serializers import (
    BookingSerializer,
    BookingHistorySerializer,
    AvailableSlotSerializer,
    CancelByReferenceSerializer,
)
from .services.booking_service import BookingService
from accounts.models import User, HotelMembership
from tables.models import RestaurantTable
from tables.serializers import RestaurantTableSerializer


def _user_can_manage_booking(user, booking):
    if not user or not user.is_authenticated:
        return False
    if getattr(user, 'role', '') == User.Role.SUPER_ADMIN or user.is_superuser:
        return True
    if booking.customer == user:
        return True
    return HotelMembership.objects.filter(
        hotel=booking.hotel,
        user=user,
        role__in=[HotelMembership.MembershipRole.OWNER, HotelMembership.MembershipRole.ADMIN, HotelMembership.MembershipRole.STAFF],
        is_active=True
    ).exists()


def _user_is_staff_or_admin(user, hotel):
    if not user or not user.is_authenticated:
        return False
    if getattr(user, 'role', '') == User.Role.SUPER_ADMIN or user.is_superuser:
        return True
    return HotelMembership.objects.filter(
        hotel=hotel,
        user=user,
        role__in=[HotelMembership.MembershipRole.OWNER, HotelMembership.MembershipRole.ADMIN, HotelMembership.MembershipRole.STAFF],
        is_active=True
    ).exists()


class BookingViewSet(viewsets.ModelViewSet):
    """
    Complete reservation engine: real-time availability slots, atomic bookings with row locks,
    lifecycle transitions, customer portal, and guest/authenticated cancellations.
    """
    queryset = Booking.objects.select_related('hotel', 'restaurant', 'table', 'customer').prefetch_related('history').all().order_by('-booking_date', '-start_time')
    serializer_class = BookingSerializer
    filterset_fields = ['hotel', 'restaurant', 'table', 'booking_status', 'booking_date']
    search_fields = ['booking_reference', 'customer_name', 'customer_email', 'customer_phone']

    def get_permissions(self):
        if self.action in ['create', 'check_availability', 'available_slots', 'cancel_by_reference']:
            return [permissions.AllowAny()]
        return [permissions.IsAuthenticated()]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if not user or not user.is_authenticated:
            return qs.none() if self.action == 'list' else qs

        if getattr(user, 'role', '') == User.Role.SUPER_ADMIN or user.is_superuser:
            return qs

        if getattr(user, 'role', '') in [User.Role.HOTEL_OWNER, User.Role.HOTEL_ADMIN, User.Role.STAFF]:
            hotel_ids = user.hotel_memberships.filter(is_active=True).values_list('hotel_id', flat=True)
            return qs.filter(hotel_id__in=hotel_ids)

        if getattr(user, 'role', '') == User.Role.CUSTOMER:
            return qs.filter(customer=user)

        return qs

    @action(detail=False, methods=['get'])
    def available_slots(self, request):
        """
        Calculates 30-minute booking slots across the restaurant operating schedule.
        Params: restaurant (id), date (YYYY-MM-DD), guests (int), duration_minutes (optional, default 90).
        """
        restaurant_id = request.query_params.get('restaurant')
        date_str = request.query_params.get('date')
        guests = int(request.query_params.get('guests', 2))
        duration = int(request.query_params.get('duration_minutes', 90))

        if not restaurant_id or not date_str:
            return Response(
                {'error': 'Parameters required: restaurant (id) and date (YYYY-MM-DD).'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            booking_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            return Response({'error': 'Invalid date format. Use YYYY-MM-DD.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            slots = BookingService.get_available_slots(
                restaurant_id=restaurant_id,
                booking_date=booking_date,
                guest_count=guests,
                duration_minutes=duration
            )
            serializer = AvailableSlotSerializer(slots, many=True)
            return Response({
                'restaurant_id': int(restaurant_id),
                'date': date_str,
                'guest_count': guests,
                'duration_minutes': duration,
                'total_slots': len(slots),
                'slots': serializer.data
            })
        except DjangoValidationError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['get'])
    def check_availability(self, request):
        """Check specific table availability for date, start_time, and end_time."""
        
        restaurant_id = request.query_params.get('restaurant')
        booking_date = request.query_params.get('date')
        start_time = request.query_params.get('start_time')
        end_time = request.query_params.get('end_time')
        guests = int(request.query_params.get('guests', 2))
        zone_name = request.query_params.get('zone')

        if not all([restaurant_id, booking_date, start_time, end_time]):
            return Response(
                {'error': 'Parameters required: restaurant, date, start_time, end_time'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 1. Base candidate tables - enforce public visibility and min/max capacity boundaries
        from restaurants.models import Restaurant
        try:
            restaurant = Restaurant.objects.get(id=restaurant_id)
            buffer_mins = restaurant.turnover_buffer_minutes
        except Restaurant.DoesNotExist:
            buffer_mins = 15

        candidates = list(RestaurantTable.objects.filter(
            restaurant_id=restaurant_id,
            restaurant__is_active=True,
            restaurant__hotel__status='APPROVED',
            restaurant__hotel__is_active=True,
            is_active=True,
            capacity__gte=guests,
            min_capacity__lte=guests,
            operational_status__in=[
                RestaurantTable.OperationalStatus.AVAILABLE,
                RestaurantTable.OperationalStatus.OCCUPIED,
                RestaurantTable.OperationalStatus.AWAITING_CLEANING,
            ]
        ).order_by('capacity', 'table_number'))

        if zone_name:
            candidates = [t for t in candidates if t.zone_name.strip().lower() == zone_name.strip().lower()]

        # 2. Find tables booked during overlapping interval considering turnover cleaning buffer
        try:
            b_date_obj = datetime.strptime(booking_date, '%Y-%m-%d').date()
            s_time_obj = datetime.strptime(start_time, '%H:%M:%S' if len(start_time) == 8 else '%H:%M').time()
            e_time_obj = datetime.strptime(end_time, '%H:%M:%S' if len(end_time) == 8 else '%H:%M').time()
        except ValueError:
            return Response({'error': 'Invalid date or time format.'}, status=status.HTTP_400_BAD_REQUEST)

        new_start_dt = datetime.combine(b_date_obj, s_time_obj)
        new_end_dt = datetime.combine(b_date_obj, e_time_obj)
        buffer_delta = timedelta(minutes=buffer_mins)

        day_bookings = list(Booking.objects.filter(
            restaurant_id=restaurant_id,
            booking_date=b_date_obj,
            booking_status__in=['PENDING', 'CONFIRMED', 'CHECKED_IN']
        ).values('table_id', 'start_time', 'end_time'))

        booked_table_ids = set()
        for b in day_bookings:
            b_start_dt = datetime.combine(b_date_obj, b['start_time'])
            b_end_dt = datetime.combine(b_date_obj, b['end_time'])
            if new_start_dt < (b_end_dt + buffer_delta) and (new_end_dt + buffer_delta) > b_start_dt:
                booked_table_ids.add(b['table_id'])

        available_tables = [t for t in candidates if t.id not in booked_table_ids]
        serializer = RestaurantTableSerializer(available_tables, many=True)
        return Response({
            'date': booking_date,
            'start_time': start_time,
            'end_time': end_time,
            'guests': guests,
            'available_count': len(available_tables),
            'tables': serializer.data
        })

    @action(detail=False, methods=['get'], permission_classes=[permissions.IsAuthenticated])
    def my_bookings(self, request):
        """Returns upcoming and past reservations for the authenticated customer."""
        today = timezone.localdate()
        user_bookings = Booking.objects.select_related('hotel', 'restaurant', 'table').filter(
            customer=request.user
        )

        upcoming = user_bookings.filter(
            models.Q(booking_date__gt=today) |
            models.Q(booking_date=today, booking_status__in=['CONFIRMED', 'PENDING', 'CHECKED_IN'])
        ).order_by('booking_date', 'start_time')

        past = user_bookings.filter(
            models.Q(booking_date__lt=today) |
            models.Q(booking_status__in=['COMPLETED', 'CANCELLED', 'NO_SHOW'])
        ).order_by('-booking_date', '-start_time')

        return Response({
            'upcoming': BookingSerializer(upcoming, many=True).data,
            'past': BookingSerializer(past, many=True).data,
            'total_bookings': user_bookings.count()
        })

    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def cancel(self, request, pk=None):
        """Authenticated cancellation: by customer owner or hotel staff/admin."""
        booking = self.get_object()
        if not _user_can_manage_booking(request.user, booking):
            raise PermissionDenied("You do not have permission to cancel this booking.")

        reason = request.data.get('reason', 'Cancelled by customer')
        try:
            BookingService.cancel_reservation(booking, cancelled_by=request.user, reason=reason)
            return Response({
                'status': 'Booking cancelled',
                'booking_reference': booking.booking_reference,
                'booking_status': booking.booking_status
            })
        except DjangoValidationError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['post'], permission_classes=[permissions.AllowAny])
    def cancel_by_reference(self, request):
        """Public cancellation for guest bookings using booking reference code and email."""
        serializer = CancelByReferenceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        ref = serializer.validated_data['booking_reference'].strip().upper()
        email = serializer.validated_data['customer_email'].strip().lower()
        reason = serializer.validated_data.get('reason', 'Cancelled by guest')

        try:
            booking = Booking.objects.get(booking_reference__iexact=ref, customer_email__iexact=email)
        except Booking.DoesNotExist:
            return Response(
                {'error': 'No matching booking found for this reference code and email address.'},
                status=status.HTTP_404_NOT_FOUND
            )

        try:
            user = request.user if request.user.is_authenticated else None
            BookingService.cancel_reservation(booking, cancelled_by=user, reason=reason)
            return Response({
                'status': 'Reservation cancelled successfully',
                'booking_reference': booking.booking_reference,
                'booking_status': booking.booking_status
            })
        except DjangoValidationError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def confirm(self, request, pk=None):
        """Staff: Confirm a pending reservation."""
        booking = self.get_object()
        if not _user_is_staff_or_admin(request.user, booking.hotel):
            raise PermissionDenied("Staff or admin privileges required.")

        old_status = booking.booking_status
        booking.booking_status = Booking.BookingStatus.CONFIRMED
        booking.save(update_fields=['booking_status', 'updated_at'])

        BookingHistory.objects.create(
            booking=booking,
            changed_by=request.user,
            previous_status=old_status,
            new_status=booking.booking_status,
            reason='Confirmed by staff'
        )
        return Response({'status': 'Reservation confirmed', 'booking_status': booking.booking_status})

    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def check_in(self, request, pk=None):
        """Staff: Guest arrived; marks booking CHECKED_IN and table OCCUPIED."""
        booking = self.get_object()
        if not _user_is_staff_or_admin(request.user, booking.hotel):
            raise PermissionDenied("Staff or admin privileges required.")

        BookingService.check_in_reservation(booking, staff_user=request.user)
        return Response({
            'status': 'Checked in successfully',
            'booking_status': booking.booking_status,
            'table_status': booking.table.operational_status
        })

    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def complete(self, request, pk=None):
        """Staff: Dining completed; marks booking COMPLETED and table AWAITING_CLEANING."""
        booking = self.get_object()
        if not _user_is_staff_or_admin(request.user, booking.hotel):
            raise PermissionDenied("Staff or admin privileges required.")

        BookingService.complete_reservation(booking, staff_user=request.user)
        return Response({
            'status': 'Dining completed; turnover requested',
            'booking_status': booking.booking_status,
            'table_status': booking.table.operational_status
        })

    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def no_show(self, request, pk=None):
        """Staff: Guest failed to arrive; marks booking NO_SHOW and releases table."""
        booking = self.get_object()
        if not _user_is_staff_or_admin(request.user, booking.hotel):
            raise PermissionDenied("Staff or admin privileges required.")

        reason = request.data.get('reason', 'Guest did not arrive')
        BookingService.no_show_reservation(booking, staff_user=request.user, reason=reason)
        return Response({
            'status': 'Marked as no-show',
            'booking_status': booking.booking_status,
            'table_status': booking.table.operational_status
        })

    @action(detail=True, methods=['get'], permission_classes=[permissions.IsAuthenticated])
    def history(self, request, pk=None):
        """Returns the chronological audit trail of state changes for this booking."""
        booking = self.get_object()
        if not _user_can_manage_booking(request.user, booking):
            raise PermissionDenied("You do not have permission to view history for this booking.")

        history_qs = booking.history.all().order_by('created_at')
        serializer = BookingHistorySerializer(history_qs, many=True)
        return Response(serializer.data)


class BookingHistoryViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Audited history of booking changes across the platform.
    Scoped by user role: customers see their own, staff see their hotel's, super admins see all.
    """
    serializer_class = BookingHistorySerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ['booking', 'booking__hotel', 'booking__customer']

    def get_queryset(self):
        user = self.request.user
        base_qs = BookingHistory.objects.select_related('booking__hotel', 'booking__customer', 'changed_by').all().order_by('-created_at')

        if getattr(user, 'role', '') == User.Role.SUPER_ADMIN or user.is_superuser:
            return base_qs

        if getattr(user, 'role', '') in [User.Role.HOTEL_OWNER, User.Role.HOTEL_ADMIN, User.Role.STAFF]:
            hotel_ids = user.hotel_memberships.filter(is_active=True).values_list('hotel_id', flat=True)
            return base_qs.filter(booking__hotel_id__in=hotel_ids)

        if getattr(user, 'role', '') == User.Role.CUSTOMER:
            return base_qs.filter(booking__customer=user)

        return base_qs.none()
