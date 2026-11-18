from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from bookings.models import Booking, BookingHistory
from tables.models import RestaurantTable
from restaurants.models import OperatingHours, SpecialClosure


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
        # Check special closures
        if SpecialClosure.objects.filter(restaurant=restaurant, closure_date=booking_date, is_all_day=True).exists():
            raise ValidationError(f"{restaurant.name} is closed on {booking_date}.")

        day_of_week = booking_date.weekday() # 0 = Monday
        hours = OperatingHours.objects.filter(restaurant=restaurant, day_of_week=day_of_week).first()
        if hours:
            if hours.is_closed:
                raise ValidationError(f"{restaurant.name} is closed on this day of the week.")
            if start_time < hours.opening_time or end_time > hours.closing_time:
                raise ValidationError(
                    f"Reservation must be within restaurant operating hours ({hours.opening_time} - {hours.closing_time})."
                )

    @classmethod
    def create_reservation(cls, customer, hotel, restaurant, table_id, booking_date, start_time, end_time, guest_count, customer_info=None, special_requests='', created_by=None):
        """
        Atomic reservation creation with row-level locking on the table to guarantee zero double bookings.
        """
        if start_time >= end_time:
            raise ValidationError("End time must be after start time.")

        cls.validate_operating_hours(restaurant, booking_date, start_time, end_time)

        with transaction.atomic():
            # Lock the table row for the duration of this transaction
            table = RestaurantTable.objects.select_for_update().get(id=table_id)

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

            customer_name = customer_info.get('name') if customer_info else (customer.get_full_name() or customer.username)
            customer_email = customer_info.get('email') if customer_info else customer.email
            customer_phone = customer_info.get('phone', '') if customer_info else (customer.phone_number or '')

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
                reason='Reservation successfully placed and locked.'
            )

            return booking

    @classmethod
    def cancel_reservation(cls, booking, cancelled_by, reason=''):
        """
        Cancels an existing reservation and logs history.
        """
        if booking.booking_status in [Booking.BookingStatus.CANCELLED, Booking.BookingStatus.COMPLETED]:
            raise ValidationError(f"Cannot cancel a booking that is already {booking.booking_status}.")

        old_status = booking.booking_status
        booking.booking_status = Booking.BookingStatus.CANCELLED
        booking.cancellation_reason = reason
        booking.cancelled_at = timezone.now()
        booking.save()

        BookingHistory.objects.create(
            booking=booking,
            changed_by=cancelled_by,
            previous_status=old_status,
            new_status=booking.booking_status,
            reason=reason or 'Customer cancellation'
        )
        return booking
