from django.contrib import admin
from .models import Booking, BookingHistory


class BookingHistoryInline(admin.TabularInline):
    model = BookingHistory
    extra = 0
    readonly_fields = ('changed_by', 'previous_status', 'new_status', 'reason', 'created_at')


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = (
        'booking_reference',
        'customer_name',
        'hotel',
        'restaurant',
        'table',
        'booking_date',
        'start_time',
        'guest_count',
        'booking_status',
        'created_at',
    )
    list_filter = ('booking_status', 'booking_date', 'hotel', 'restaurant')
    search_fields = ('booking_reference', 'customer_name', 'customer_email', 'customer_phone')
    readonly_fields = ('booking_reference', 'created_at', 'updated_at')
    inlines = [BookingHistoryInline]
