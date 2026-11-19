from django.contrib import admin
from .models import Staff, StaffAssignment, CleaningTask, CleaningTaskAssignment


class CleaningTaskAssignmentInline(admin.TabularInline):
    model = CleaningTaskAssignment
    extra = 1


@admin.register(Staff)
class StaffAdmin(admin.ModelAdmin):
    list_display = ('user', 'hotel', 'role', 'employee_id', 'is_active')
    list_filter = ('role', 'is_active', 'hotel')
    search_fields = ('user__username', 'user__email', 'employee_id')


@admin.register(StaffAssignment)
class StaffAssignmentAdmin(admin.ModelAdmin):
    list_display = ('staff', 'restaurant', 'table', 'assignment_date', 'shift_start', 'shift_end', 'is_active')
    list_filter = ('assignment_date', 'is_active', 'restaurant')
    search_fields = ('staff__user__username', 'restaurant__name')


@admin.register(CleaningTask)
class CleaningTaskAdmin(admin.ModelAdmin):
    list_display = ('table', 'restaurant', 'assigned_to', 'priority', 'status', 'created_at')
    list_filter = ('status', 'priority', 'hotel', 'restaurant')
    search_fields = ('table__table_number', 'notes')
    inlines = [CleaningTaskAssignmentInline]
