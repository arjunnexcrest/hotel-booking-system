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
    def check_table_conflict(table_id, booking_date, start_time, end_time, exclude_booking_id=None):
        """
        Evaluates overlapping reservations using half-open time intervals [start_time, end_time).
        A booking ending at 7:00 PM does not conflict with one starting at 7:00 PM.
        """
        active_statuses = [
            Booking.BookingStatus.PENDING,
            Booking.BookingStatus.CONFIRMED,
            Booking.BookingStatus.CHECKED_IN,
        ]

        query = Booking.objects.filter(
            table_id=table_id,
            booking_date=booking_date,
            booking_status__in=active_statuses,
            start_time__lt=end_time,
            end_time__gt=start_time,
        )

        if exclude_booking_id:
            query = query.exclude(id=exclude_booking_id)

        return query.exists()

    @staticmethod
    def validate_operating_hours(restaurant, booking_date, start_time, end_time):
        """
        Validates that the reservation falls within restaurant operating hours and not on closure dates.
        """
        # Ensure parent hotel is approved and active
        if restaurant.hotel.status != Hotel.Status.APPROVED or not restaurant.hotel.is_active:
            raise ValidationError(f"Reservations are unavailable: '{restaurant.hotel.name}' is currently not approved or inactive.")

        if not restaurant.is_active:
            raise ValidationError(f"'{restaurant.name}' is currently inactive.")

        # Check special closures
        closure = SpecialClosure.objects.filter(restaurant=restaurant, closure_date=booking_date).first()
        if closure:
            if closure.is_all_day:
                raise ValidationError(f"{restaurant.name} is closed on {booking_date} ({closure.reason}).")
            if closure.start_time and closure.end_time:
                # If reservation overlaps with closure interval
                if start_time < closure.end_time and end_time > closure.start_time:
                    raise ValidationError(f"{restaurant.name} is closed between {closure.start_time} and {closure.end_time} ({closure.reason}).")

        day_of_week = booking_date.weekday() # 0 = Monday
        hours = OperatingHours.objects.filter(restaurant=restaurant, day_of_week=day_of_week).first()
        if hours:
            if hours.is_closed:
                raise ValidationError(f"{restaurant.name} is closed on this day of the week ({hours.get_day_of_week_display()}).")
            if start_time < hours.opening_time or end_time > hours.closing_time:
                raise ValidationError(
                    f"Reservation must be within restaurant operating hours ({hours.opening_time} - {hours.closing_time})."
                )

    @classmethod
    def get_available_slots(cls, restaurant_id, booking_date, guest_count=2, duration_minutes=90):
        """
        Calculates 30-minute reservation slots during restaurant operating hours on a given date.
        Returns slots with available table count and recommendation flags.
        """
        try:
            restaurant = Restaurant.objects.select_related('hotel').get(id=restaurant_id)
        except Restaurant.DoesNotExist:
            raise ValidationError("Restaurant not found.")

        # Check hotel approval and active status
        if restaurant.hotel.status != Hotel.Status.APPROVED or not restaurant.hotel.is_active:
            return []
        if not restaurant.is_active:
            return []

        # Check special closure
        closure = SpecialClosure.objects.filter(restaurant=restaurant, closure_date=booking_date).first()
        if closure and closure.is_all_day:
            return []

        day_of_week = booking_date.weekday()
        hours = OperatingHours.objects.filter(restaurant=restaurant, day_of_week=day_of_week).first()
        if not hours or hours.is_closed:
            return []

        # Candidate active tables with capacity
        candidate_tables = list(RestaurantTable.objects.filter(
            restaurant=restaurant,
            is_active=True,
            capacity__gte=guest_count,
            operational_status__in=[
                RestaurantTable.OperationalStatus.AVAILABLE,
                RestaurantTable.OperationalStatus.OCCUPIED,
                RestaurantTable.OperationalStatus.AWAITING_CLEANING,
            ]
        ))
        if not candidate_tables:
            return []

        # Generate slots every 30 minutes from opening_time up to closing_time - duration
        slots = []
        open_dt = datetime.combine(booking_date, hours.opening_time)
        close_dt = datetime.combine(booking_date, hours.closing_time)
        slot_duration = timedelta(minutes=duration_minutes)

        curr_dt = open_dt
        now_dt = timezone.localtime()

        active_statuses = [
            Booking.BookingStatus.PENDING,
            Booking.BookingStatus.CONFIRMED,
            Booking.BookingStatus.CHECKED_IN,
        ]

        # Prefetch day's bookings
        day_bookings = list(Booking.objects.filter(
            restaurant=restaurant,
            booking_date=booking_date,
            booking_status__in=active_statuses
        ).values('table_id', 'start_time', 'end_time'))

        while curr_dt + slot_duration <= close_dt:
            slot_start = curr_dt.time()
            slot_end = (curr_dt + slot_duration).time()

            # Skip past slots if booking for today (compare naive local datetimes safely)
            if booking_date == now_dt.date() and curr_dt < now_dt.replace(tzinfo=None):
                curr_dt += timedelta(minutes=30)
                continue

            # Check closure time overlap if any
            if closure and closure.start_time and closure.end_time:
                if slot_start < closure.end_time and slot_end > closure.start_time:
                    curr_dt += timedelta(minutes=30)
                    continue

            # Count unreserved tables for this slot
            booked_tables_in_slot = {
                b['table_id'] for b in day_bookings
                if b['start_time'] < slot_end and b['end_time'] > slot_start
            }

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
        Smart table auto-assignment: finds an unreserved table with capacity >= guest_count,
        minimizing excess seats (optimal fit), optionally within a preferred zone.
        """
        qs = RestaurantTable.objects.filter(
            restaurant=restaurant,
            is_active=True,
            capacity__gte=guest_count,
            operational_status__in=[
                RestaurantTable.OperationalStatus.AVAILABLE,
                RestaurantTable.OperationalStatus.OCCUPIED,
                RestaurantTable.OperationalStatus.AWAITING_CLEANING,
            ],
        )
        if zone_name:
            qs = qs.filter(zone_name__iexact=zone_name.strip())

        # Order by capacity ascending to pick the tightest matching table
        candidates = list(qs.order_by('capacity', 'table_number'))

        active_statuses = [
            Booking.BookingStatus.PENDING,
            Booking.BookingStatus.CONFIRMED,
            Booking.BookingStatus.CHECKED_IN,
        ]

        conflicting_table_ids = set(Booking.objects.filter(
            restaurant=restaurant,
            booking_date=booking_date,
            booking_status__in=active_statuses,
            start_time__lt=end_time,
            end_time__gt=start_time,
        ).values_list('table_id', flat=True))

        for table in candidates:
            if table.id not in conflicting_table_ids:
                return table

        return None

    @classmethod
    def create_reservation(cls, customer, hotel, restaurant, table_id, booking_date, start_time, end_time, guest_count, customer_info=None, special_requests='', created_by=None, zone_name=None):
        """
        Atomic reservation creation with row-level locking (select_for_update) on the table.
        Auto-assigns best available table if table_id is None.
        """
        if start_time >= end_time:
            raise ValidationError("End time must be after start time.")

        cls.validate_operating_hours(restaurant, booking_date, start_time, end_time)

        with transaction.atomic():
            if not table_id:
                # Auto-assign table
                table = cls.find_best_available_table(restaurant, booking_date, start_time, end_time, guest_count, zone_name)
                if not table:
                    raise ValidationError("No tables are currently available for this party size and time slot.")
                table = RestaurantTable.objects.select_for_update().get(id=table.id)
            else:
                try:
                    table = RestaurantTable.objects.select_for_update().get(id=table_id, restaurant=restaurant)
                except RestaurantTable.DoesNotExist:
                    raise ValidationError("Specified table does not exist in this restaurant.")

            if not table.is_active:
                raise ValidationError(f"Table {table.table_number} is currently inactive.")

            if guest_count > table.capacity:
                raise ValidationError(
                    f"Party size ({guest_count}) exceeds capacity of Table {table.table_number} ({table.capacity})."
                )

            if cls.check_table_conflict(table.id, booking_date, start_time, end_time):
                raise ValidationError(
                    f"Table {table.table_number} already has a conflicting reservation for this time slot."
                )

            customer_name = customer_info.get('name') if customer_info else (customer.get_full_name() or customer.username if customer else 'Guest')
            customer_email = customer_info.get('email') if customer_info else (customer.email if customer else '')
            customer_phone = customer_info.get('phone', '') if customer_info else (getattr(customer, 'phone_number', '') or '')

            if not customer_name:
                raise ValidationError("Customer name is required.")
            if not customer_email:
                raise ValidationError("Customer email is required.")

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

            # Audit & History
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

            # Notifications
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
        """
        Cancels an existing reservation and logs history and notifications.
        """
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

        # Update table operational condition
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
