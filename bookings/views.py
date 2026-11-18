from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils import timezone
from .models import Booking, BookingHistory
from .serializers import BookingSerializer, BookingHistorySerializer
from .services.booking_service import BookingService


class BookingViewSet(viewsets.ModelViewSet):
    queryset = Booking.objects.select_related('hotel', 'restaurant', 'table', 'customer').prefetch_related('history').all().order_by('-booking_date', '-start_time')
    serializer_class = BookingSerializer
    filterset_fields = ['hotel', 'restaurant', 'table', 'booking_status', 'booking_date']
    search_fields = ['booking_reference', 'customer_name', 'customer_email', 'customer_phone']

    def get_permissions(self):
        if self.action in ['create', 'check_availability']:
            return [permissions.AllowAny()]
        return [permissions.IsAuthenticated()]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if not user or not user.is_authenticated:
            return qs.none() if self.action == 'list' else qs

        if user.role == 'super_admin' or user.is_superuser:
            return qs

        if user.role in ['hotel_owner', 'hotel_admin', 'staff']:
            hotel_ids = user.hotel_memberships.filter(is_active=True).values_list('hotel_id', flat=True)
            return qs.filter(hotel_id__in=hotel_ids)

        if user.role == 'customer':
            return qs.filter(customer=user)

        return qs

    def perform_create(self, serializer):
        user = self.request.user if self.request.user.is_authenticated else None
        booking = serializer.save(customer=user)
        BookingHistory.objects.create(
            booking=booking,
            changed_by=user,
            previous_status='',
            new_status=booking.booking_status,
            reason='Initial booking creation'
        )

    @action(detail=False, methods=['get'], permission_classes=[permissions.AllowAny])
    def check_availability(self, request):
        restaurant_id = request.query_params.get('restaurant')
        booking_date = request.query_params.get('date')
        start_time = request.query_params.get('start_time')
        end_time = request.query_params.get('end_time')
        guests = int(request.query_params.get('guests', 2))

        if not all([restaurant_id, booking_date, start_time, end_time]):
            return Response(
                {'error': 'Parameters required: restaurant, date, start_time, end_time'},
                status=status.HTTP_400_BAD_REQUEST
            )

        from tables.models import RestaurantTable
        from tables.serializers import RestaurantTableSerializer

        # 1. Base candidate tables
        candidates = RestaurantTable.objects.filter(
            restaurant_id=restaurant_id,
            is_active=True,
            capacity__gte=guests,
            operational_status=RestaurantTable.OperationalStatus.AVAILABLE,
        )

        # 2. Find tables booked during overlapping interval [start_time, end_time)
        conflicting_booking_statuses = [
            Booking.BookingStatus.PENDING,
            Booking.BookingStatus.CONFIRMED,
            Booking.BookingStatus.CHECKED_IN,
        ]
        booked_table_ids = Booking.objects.filter(
            restaurant_id=restaurant_id,
            booking_date=booking_date,
            booking_status__in=conflicting_booking_statuses,
            start_time__lt=end_time,
            end_time__gt=start_time,
        ).values_list('table_id', flat=True)

        available_tables = candidates.exclude(id__in=booked_table_ids)
        serializer = RestaurantTableSerializer(available_tables, many=True)
        return Response({
            'date': booking_date,
            'start_time': start_time,
            'end_time': end_time,
            'guests': guests,
            'available_count': available_tables.count(),
            'tables': serializer.data
        })

    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def cancel(self, request, pk=None):
        booking = self.get_object()
        reason = request.data.get('reason', 'Cancelled by user')
        old_status = booking.booking_status
        booking.booking_status = Booking.BookingStatus.CANCELLED
        booking.cancellation_reason = reason
        booking.cancelled_at = timezone.now()
        booking.save()

        BookingHistory.objects.create(
            booking=booking,
            changed_by=request.user,
            previous_status=old_status,
            new_status=booking.booking_status,
            reason=reason
        )
        return Response({'status': 'Booking cancelled', 'booking_reference': booking.booking_reference})

    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def check_in(self, request, pk=None):
        booking = self.get_object()
        old_status = booking.booking_status
        booking.booking_status = Booking.BookingStatus.CHECKED_IN
        booking.save()

        BookingHistory.objects.create(
            booking=booking,
            changed_by=request.user,
            previous_status=old_status,
            new_status=booking.booking_status,
            reason='Customer checked in'
        )
        return Response({'status': 'Checked in successfully'})


class BookingHistoryViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = BookingHistory.objects.select_related('booking', 'changed_by').all().order_by('-created_at')
    serializer_class = BookingHistorySerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ['booking']
