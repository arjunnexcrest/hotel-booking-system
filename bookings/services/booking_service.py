from datetime import datetime, date, time, timedelta
from django.db import transaction, models
from django.core.exceptions import ValidationError
from django.utils import timezone

from bookings.models import Booking, BookingHistory
from tables.models import RestaurantTable, TableEvent
from restaurants.models import Restaurant, OperatingHours, SpecialClosure
from hotels.models import Hotel
from audit.models import AuditLog
from notifications.models import Notification


def _log_audit(actor, hotel, action, entity_type, entity_id, reason='', old_val=None, new_val=None):
    try:
        AuditLog.objects.create(
            actor=actor if actor and actor.is_authenticated else None,
            actor_type=AuditLog.ActorType.USER,
            hotel=hotel,
            action=action,
            entity_type=entity_type,
            entity_id=str(entity_id),
            reason=reason,
            old_values=old_val or {},
            new_values=new_val or {},
        )
    except Exception:
        pass


def _send_notification(recipient, hotel, title, message, notif_type):
    try:
        if recipient and recipient.is_authenticated:
            Notification.objects.create(
                recipient=recipient,
                hotel=hotel,
                title=title,
                message=message,
                notification_type=notif_type,
            )
    except Exception:
        pass


class BookingService:
    @staticmethod
    def check_table_conflict(table_id, booking_date, start_time, end_time, buffer_minutes=0, exclude_booking_id=None):
        """
        Evaluates overlapping reservations using buffer-aware time intervals.
        Between reservation A and reservation B:
        Conflict exists if:
            new_start < (existing_end + buffer) AND (new_end + buffer) > existing_start
        """
        active_statuses = [
            Booking.BookingStatus.PENDING,
            Booking.BookingStatus.CONFIRMED,
            Booking.BookingStatus.CHECKED_IN,
        ]

        existing_bookings = Booking.objects.filter(
            table_id=table_id,
            booking_date=booking_date,
            booking_status__in=active_statuses,
        )
        if exclude_booking_id:
            existing_bookings = existing_bookings.exclude(id=exclude_booking_id)

        new_start_dt = datetime.combine(booking_date, start_time)
        new_end_dt = datetime.combine(booking_date, end_time)
        buffer_delta = timedelta(minutes=buffer_minutes)

        for b in existing_bookings:
            b_start_dt = datetime.combine(booking_date, b.start_time)
            b_end_dt = datetime.combine(booking_date, b.end_time)

            # Check overlap considering turnover cleaning buffer
            if new_start_dt < (b_end_dt + buffer_delta) and (new_end_dt + buffer_delta) > b_start_dt:
                return True

        return False

    @staticmethod
    def check_customer_conflict(customer, customer_email, booking_date, start_time, end_time, exclude_booking_id=None):
        """
        Prevents a customer from holding simultaneous overlapping reservations across tables.
        """
        active_statuses = [
            Booking.BookingStatus.PENDING,
            Booking.BookingStatus.CONFIRMED,
            Booking.BookingStatus.CHECKED_IN,
        ]
        q = models.Q()
        if customer and customer.is_authenticated:
            q |= models.Q(customer=customer)
        if customer_email:
            q |= models.Q(customer_email__iexact=customer_email.strip())

        if not q:
            return False

        existing = Booking.objects.filter(
            q,
            booking_date=booking_date,
            booking_status__in=active_statuses,
            start_time__lt=end_time,
            end_time__gt=start_time,
        )
        if exclude_booking_id:
            existing = existing.exclude(id=exclude_booking_id)

        return existing.exists()

    @staticmethod
    def validate_capacity(table, guest_count):
        """
        Enforces both maximum capacity and minimum capacity boundaries.
        """
        if guest_count < 1:
            raise ValidationError("Party size must be at least 1 guest.")
        if guest_count > table.capacity:
            raise ValidationError(
                f"Party size ({guest_count}) exceeds capacity of Table {table.table_number} ({table.capacity} guests)."
            )
        if guest_count < table.min_capacity:
            raise ValidationError(
                f"Table {table.table_number} requires a minimum party size of {table.min_capacity} guests."
            )

    @staticmethod
    def validate_reservation_time(restaurant, booking_date, start_time, end_time):
        """
        Rigorous time validations:
        1. End time must be after start time.
        2. Hotel must be approved and active; restaurant must be active.
        3. Reservation cannot be in the past; same-day bookings must meet min_advance_minutes.
        4. Advance horizon <= max_advance_days.
        5. Duration is within [min_reservation_duration, max_reservation_duration].
        6. Within operating hours and not on closure dates.
        7. Kitchen cutoff: start_time <= closing_time - min_reservation_duration.
        """
        if start_time >= end_time:
            raise ValidationError("End time must be after start time.")

        # 1. Hotel approval & restaurant active
        if restaurant.hotel.status != Hotel.Status.APPROVED or not restaurant.hotel.is_active:
            raise ValidationError(f"Reservations are unavailable: '{restaurant.hotel.name}' is currently not approved or inactive.")

        if not restaurant.is_active:
            raise ValidationError(f"'{restaurant.name}' is currently inactive.")

        # 2. Advance & Past Time Validation
        now_dt = timezone.localtime()
        today = now_dt.date()

        if booking_date < today:
            raise ValidationError("Cannot make reservations in the past.")

        max_allowed_date = today + timedelta(days=restaurant.max_advance_days)
        if booking_date > max_allowed_date:
            raise ValidationError(f"Reservations can only be booked up to {restaurant.max_advance_days} days in advance.")

        # Same-day advance notice
        if booking_date == today:
            tz = timezone.get_current_timezone()
            start_dt = timezone.make_aware(datetime.combine(booking_date, start_time), tz)
            min_notice_dt = now_dt + timedelta(minutes=restaurant.min_advance_minutes)
            if start_dt < min_notice_dt:
                raise ValidationError(f"Reservations must be made at least {restaurant.min_advance_minutes} minutes in advance.")

        # 3. Duration Limits
        duration_mins = (datetime.combine(booking_date, end_time) - datetime.combine(booking_date, start_time)).total_seconds() / 60
        if duration_mins < restaurant.min_reservation_duration:
            raise ValidationError(
                f"Reservation duration ({int(duration_mins)} mins) is below the minimum allowed ({restaurant.min_reservation_duration} mins)."
            )
        if duration_mins > restaurant.max_reservation_duration:
            raise ValidationError(
                f"Reservation duration ({int(duration_mins)} mins) exceeds the maximum allowed ({restaurant.max_reservation_duration} mins)."
            )

        # 4. Special Closures
        closure = SpecialClosure.objects.filter(restaurant=restaurant, closure_date=booking_date).first()
        if closure:
            if closure.is_all_day:
                raise ValidationError(f"{restaurant.name} is closed on {booking_date} ({closure.reason}).")
            if closure.start_time and closure.end_time:
                if start_time < closure.end_time and end_time > closure.start_time:
                    raise ValidationError(f"{restaurant.name} is closed between {closure.start_time} and {closure.end_time} ({closure.reason}).")

        # 5. Operating Hours
        day_of_week = booking_date.weekday()
        hours = OperatingHours.objects.filter(restaurant=restaurant, day_of_week=day_of_week).first()
        if not hours or hours.is_closed:
            day_name = hours.get_day_of_week_display() if hours else booking_date.strftime('%A')
            raise ValidationError(f"{restaurant.name} is closed on {day_name}.")

        if start_time < hours.opening_time or end_time > hours.closing_time:
            raise ValidationError(
                f"Reservation must be within restaurant operating hours ({hours.opening_time} - {hours.closing_time})."
            )

        # 6. Kitchen Cutoff
        kitchen_cutoff_dt = datetime.combine(booking_date, hours.closing_time) - timedelta(minutes=restaurant.min_reservation_duration)
        if start_time > kitchen_cutoff_dt.time():
            raise ValidationError(
                f"Latest seating is at {kitchen_cutoff_dt.strftime('%H:%M')} to allow for minimum dining duration before closing."
            )

    @classmethod
    def get_available_slots(cls, restaurant_id, booking_date, guest_count=2, duration_minutes=90):
        """
        Calculates 30-minute reservation slots during restaurant operating hours on a given date,
        factoring in table turnover buffers.
        """
        try:
            restaurant = Restaurant.objects.select_related('hotel').get(id=restaurant_id)
        except Restaurant.DoesNotExist:
            raise ValidationError("Restaurant not found.")

        if restaurant.hotel.status != Hotel.Status.APPROVED or not restaurant.hotel.is_active:
            return []
        if not restaurant.is_active:
            return []

        closure = SpecialClosure.objects.filter(restaurant=restaurant, closure_date=booking_date).first()
        if closure and closure.is_all_day:
            return []

        day_of_week = booking_date.weekday()
        hours = OperatingHours.objects.filter(restaurant=restaurant, day_of_week=day_of_week).first()
        if not hours or hours.is_closed:
            return []

        # Candidate active tables fitting capacity boundaries
        candidate_tables = list(RestaurantTable.objects.filter(
            restaurant=restaurant,
            is_active=True,
            capacity__gte=guest_count,
            min_capacity__lte=guest_count,
            operational_status__in=[
                RestaurantTable.OperationalStatus.AVAILABLE,
                RestaurantTable.OperationalStatus.OCCUPIED,
                RestaurantTable.OperationalStatus.AWAITING_CLEANING,
            ]
        ))
        if not candidate_tables:
            return []

        slots = []
        open_dt = datetime.combine(booking_date, hours.opening_time)
        close_dt = datetime.combine(booking_date, hours.closing_time)
        slot_duration = timedelta(minutes=duration_minutes)

        curr_dt = open_dt
        now_dt = timezone.localtime()
        buffer_mins = restaurant.turnover_buffer_minutes

        # Prefetch day's bookings
        day_bookings = list(Booking.objects.filter(
            restaurant=restaurant,
            booking_date=booking_date,
            booking_status__in=[Booking.BookingStatus.PENDING, Booking.BookingStatus.CONFIRMED, Booking.BookingStatus.CHECKED_IN]
        ).values('table_id', 'start_time', 'end_time'))

        while curr_dt + slot_duration <= close_dt:
            slot_start = curr_dt.time()
            slot_end = (curr_dt + slot_duration).time()

            # Skip past or non-advance slots if booking for today
            if booking_date == now_dt.date():
                tz = timezone.get_current_timezone()
                slot_aware = timezone.make_aware(curr_dt, tz)
                if slot_aware < now_dt + timedelta(minutes=restaurant.min_advance_minutes):
                    curr_dt += timedelta(minutes=30)
                    continue

            # Check closure time overlap
            if closure and closure.start_time and closure.end_time:
                if slot_start < closure.end_time and slot_end > closure.start_time:
                    curr_dt += timedelta(minutes=30)
                    continue

            # Count unreserved tables considering turnover buffer
            slot_start_dt = curr_dt
            slot_end_dt = curr_dt + slot_duration
            buffer_delta = timedelta(minutes=buffer_mins)

            booked_tables_in_slot = set()
            for b in day_bookings:
                b_start_dt = datetime.combine(booking_date, b['start_time'])
                b_end_dt = datetime.combine(booking_date, b['end_time'])
                if slot_start_dt < (b_end_dt + buffer_delta) and (slot_end_dt + buffer_delta) > b_start_dt:
                    booked_tables_in_slot.add(b['table_id'])

            available_tables_count = sum(
                1 for t in candidate_tables if t.id not in booked_tables_in_slot
            )

            if available_tables_count > 0:
                is_peak = (19 <= curr_dt.hour < 21) or (12 <= curr_dt.hour < 14)
                slots.append({
                    'time': slot_start.strftime('%H:%M:%S'),
                    'time_display': curr_dt.strftime('%I:%M %p'),
                    'end_time': slot_end.strftime('%H:%M:%S'),
                    'end_time_display': (curr_dt + slot_duration).strftime('%I:%M %p'),
                    'available_tables': available_tables_count,
                    'is_peak': is_peak,
                })

            curr_dt += timedelta(minutes=30)

        return slots

    @classmethod
    def find_best_available_table(cls, restaurant, booking_date, start_time, end_time, guest_count, zone_name=None):
        """
        Smart table auto-assignment: finds an unreserved table fitting min_capacity <= guests <= capacity,
        ordering by tightest fit first (capacity - guest_count ascending).
        """
        buffer_mins = restaurant.turnover_buffer_minutes
        qs = RestaurantTable.objects.filter(
            restaurant=restaurant,
            is_active=True,
            capacity__gte=guest_count,
            min_capacity__lte=guest_count,
            operational_status__in=[
                RestaurantTable.OperationalStatus.AVAILABLE,
                RestaurantTable.OperationalStatus.OCCUPIED,
                RestaurantTable.OperationalStatus.AWAITING_CLEANING,
            ],
        )
        if zone_name:
            qs = qs.filter(zone_name__iexact=zone_name.strip())

        candidates = list(qs.order_by('capacity', 'table_number'))

        for table in candidates:
            if not cls.check_table_conflict(table.id, booking_date, start_time, end_time, buffer_minutes=buffer_mins):
                return table

        return None

    @classmethod
    def create_reservation(cls, customer, hotel, restaurant, table_id, booking_date, start_time, end_time, guest_count, customer_info=None, special_requests='', created_by=None, zone_name=None):
        """
        Atomic reservation creation with row-level locking (select_for_update),
        buffer-aware collision checks, customer anti-spam collision checks, and capacity validations.
        """
        cls.validate_reservation_time(restaurant, booking_date, start_time, end_time)

        customer_name = customer_info.get('name') if customer_info else (customer.get_full_name() or customer.username if customer else 'Guest')
        customer_email = customer_info.get('email') if customer_info else (customer.email if customer else '')
        customer_phone = customer_info.get('phone', '') if customer_info else (getattr(customer, 'phone_number', '') or '')

        if not customer_name:
            raise ValidationError("Customer name is required.")
        if not customer_email:
            raise ValidationError("Customer email is required.")

        # Check customer concurrent overlapping booking
        if cls.check_customer_conflict(customer, customer_email, booking_date, start_time, end_time):
            raise ValidationError("You already have an active reservation for an overlapping time slot.")

        buffer_mins = restaurant.turnover_buffer_minutes

        with transaction.atomic():
            if not table_id:
                table = cls.find_best_available_table(restaurant, booking_date, start_time, end_time, guest_count, zone_name)
                if not table:
                    raise ValidationError("No tables are currently available for this party size and time slot (taking turnover buffers into account).")
                table = RestaurantTable.objects.select_for_update().get(id=table.id)
            else:
                try:
                    table = RestaurantTable.objects.select_for_update().get(id=table_id, restaurant=restaurant)
                except RestaurantTable.DoesNotExist:
                    raise ValidationError("Specified table does not exist in this restaurant.")

            if not table.is_active or table.operational_status in [RestaurantTable.OperationalStatus.MAINTENANCE, RestaurantTable.OperationalStatus.TEMPORARILY_BLOCKED]:
                raise ValidationError(f"Table {table.table_number} is currently out of service or inactive.")

            # Validate capacity boundaries
            cls.validate_capacity(table, guest_count)

            # Check table conflict with turnover cleaning buffer
            if cls.check_table_conflict(table.id, booking_date, start_time, end_time, buffer_minutes=buffer_mins):
                raise ValidationError(
                    f"Table {table.table_number} already has a conflicting reservation or is in turnover cleaning during this time slot."
                )

            booking = Booking.objects.create(
                customer=customer if customer and customer.is_authenticated else None,
                customer_name=customer_name,
                customer_email=customer_email,
                customer_phone=customer_phone,
                hotel=hotel,
                restaurant=restaurant,
                table=table,
                booking_date=booking_date,
                start_time=start_time,
                end_time=end_time,
                guest_count=guest_count,
                special_requests=special_requests,
                booking_status=Booking.BookingStatus.CONFIRMED,
            )

            BookingHistory.objects.create(
                booking=booking,
                changed_by=created_by or (customer if customer and customer.is_authenticated else None),
                previous_status='',
                new_status=booking.booking_status,
                reason='Reservation successfully created and confirmed.'
            )

            _log_audit(
                actor=created_by or (customer if customer and customer.is_authenticated else None),
                hotel=hotel,
                action=AuditLog.Action.CREATE,
                entity_type='Booking',
                entity_id=booking.id,
                reason=f"Booking created ({booking.booking_reference}) for {customer_name}"
            )

            _send_notification(
                recipient=customer if customer and customer.is_authenticated else None,
                hotel=hotel,
                title=f"Booking Confirmed: {booking.booking_reference}",
                message=f"Your table reservation at {restaurant.name} on {booking_date} at {start_time} is confirmed.",
                notif_type=Notification.NotificationType.BOOKING_CONFIRMATION
            )

            return booking

    @classmethod
    def cancel_reservation(cls, booking, cancelled_by, reason=''):
        """Cancels an existing reservation and logs history and notifications."""
        if booking.booking_status in [Booking.BookingStatus.CANCELLED, Booking.BookingStatus.COMPLETED]:
            raise ValidationError(f"Cannot cancel a booking that is already {booking.get_booking_status_display().lower()}.")

        old_status = booking.booking_status
        booking.booking_status = Booking.BookingStatus.CANCELLED
        booking.cancellation_reason = reason or 'Cancelled by user'
        booking.cancelled_at = timezone.now()
        booking.save(update_fields=['booking_status', 'cancellation_reason', 'cancelled_at', 'updated_at'])

        BookingHistory.objects.create(
            booking=booking,
            changed_by=cancelled_by if cancelled_by and cancelled_by.is_authenticated else None,
            previous_status=old_status,
            new_status=booking.booking_status,
            reason=reason or 'Reservation cancelled.'
        )

        _log_audit(
            actor=cancelled_by if cancelled_by and cancelled_by.is_authenticated else None,
            hotel=booking.hotel,
            action=AuditLog.Action.STATUS_CHANGE,
            entity_type='Booking',
            entity_id=booking.id,
            reason=f"Booking cancelled: {reason}",
            old_val={'status': old_status},
            new_val={'status': booking.booking_status}
        )

        _send_notification(
            recipient=booking.customer,
            hotel=booking.hotel,
            title=f"Booking Cancelled: {booking.booking_reference}",
            message=f"Your reservation for {booking.booking_date} at {booking.restaurant.name} has been cancelled. Reason: {reason or 'Customer cancellation'}",
            notif_type=Notification.NotificationType.BOOKING_CANCELLATION
        )

        return booking

    @classmethod
    def check_in_reservation(cls, booking, staff_user):
        """Guests arrived: marks booking as CHECKED_IN and table as OCCUPIED."""
        old_status = booking.booking_status
        booking.booking_status = Booking.BookingStatus.CHECKED_IN
        booking.save(update_fields=['booking_status', 'updated_at'])

        table = booking.table
        old_table_status = table.operational_status
        table.operational_status = RestaurantTable.OperationalStatus.OCCUPIED
        table.save(update_fields=['operational_status', 'updated_at'])

        TableEvent.objects.create(
            table=table,
            from_status=old_table_status,
            to_status=table.operational_status,
            triggered_by=TableEvent.Trigger.BOOKING_FLOW,
            actor=staff_user,
            reason=f"Customer checked in for booking {booking.booking_reference}"
        )

        BookingHistory.objects.create(
            booking=booking,
            changed_by=staff_user,
            previous_status=old_status,
            new_status=booking.booking_status,
            reason="Customer arrived and checked in."
        )
        return booking

    @classmethod
    def complete_reservation(cls, booking, staff_user):
        """Dining finished: marks booking as COMPLETED and table as AWAITING_CLEANING for turnaround."""
        old_status = booking.booking_status
        booking.booking_status = Booking.BookingStatus.COMPLETED
        booking.save(update_fields=['booking_status', 'updated_at'])

        table = booking.table
        old_table_status = table.operational_status
        table.operational_status = RestaurantTable.OperationalStatus.AWAITING_CLEANING
        table.save(update_fields=['operational_status', 'updated_at'])

        TableEvent.objects.create(
            table=table,
            from_status=old_table_status,
            to_status=table.operational_status,
            triggered_by=TableEvent.Trigger.BOOKING_FLOW,
            actor=staff_user,
            reason=f"Dining completed for booking {booking.booking_reference}; turnover cleaning requested."
        )

        BookingHistory.objects.create(
            booking=booking,
            changed_by=staff_user,
            previous_status=old_status,
            new_status=booking.booking_status,
            reason="Dining finished; table marked for turnover cleaning."
        )
        return booking

    @classmethod
    def no_show_reservation(cls, booking, staff_user, reason='Guest did not arrive'):
        """Customer failed to show up: marks booking as NO_SHOW and ensures table is AVAILABLE."""
        old_status = booking.booking_status
        booking.booking_status = Booking.BookingStatus.NO_SHOW
        booking.save(update_fields=['booking_status', 'updated_at'])

        table = booking.table
        if table.operational_status == RestaurantTable.OperationalStatus.OCCUPIED:
            old_table_status = table.operational_status
            table.operational_status = RestaurantTable.OperationalStatus.AVAILABLE
            table.save(update_fields=['operational_status', 'updated_at'])

            TableEvent.objects.create(
                table=table,
                from_status=old_table_status,
                to_status=table.operational_status,
                triggered_by=TableEvent.Trigger.BOOKING_FLOW,
                actor=staff_user,
                reason=f"No-show for booking {booking.booking_reference}; table released."
            )

        BookingHistory.objects.create(
            booking=booking,
            changed_by=staff_user,
            previous_status=old_status,
            new_status=booking.booking_status,
            reason=f"Marked as no-show: {reason}"
        )
        return booking
