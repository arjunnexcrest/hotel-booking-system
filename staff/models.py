from django.db import models
from django.conf import settings
from core.models import TimeStampedModel


class Staff(TimeStampedModel):
    """
    Staff member record linked to a specific hotel.
    """
    class StaffRole(models.TextChoices):
        WAITER = 'WAITER', 'Waiter'
        CLEANER = 'CLEANER', 'Cleaner'
        HOST = 'HOST', 'Host / Receptionist'
        MANAGER = 'MANAGER', 'Floor Manager'

    hotel = models.ForeignKey(
        'hotels.Hotel',
        on_delete=models.CASCADE,
        related_name='staff_members'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='staff_profile'
    )
    employee_id = models.CharField(max_length=50, blank=True)
    role = models.CharField(
        max_length=30,
        choices=StaffRole.choices,
        default=StaffRole.WAITER,
    )
    phone = models.CharField(max_length=20, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'staff'
        unique_together = ('hotel', 'user')

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} ({self.get_role_display()} at {self.hotel.name})"


class StaffAssignment(TimeStampedModel):
    """
    Daily shift assignments mapping staff to restaurants/tables.
    """
    staff = models.ForeignKey(
        Staff,
        on_delete=models.CASCADE,
        related_name='assignments'
    )
    restaurant = models.ForeignKey(
        'restaurants.Restaurant',
        on_delete=models.CASCADE,
        related_name='staff_assignments'
    )
    table = models.ForeignKey(
        'tables.RestaurantTable',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='staff_assignments'
    )
    assignment_date = models.DateField()
    shift_start = models.TimeField()
    shift_end = models.TimeField()
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'staff_assignments'
        indexes = [
            models.Index(fields=['staff', 'assignment_date']),
            models.Index(fields=['table', 'assignment_date']),
        ]

    def __str__(self):
        return f"{self.staff} assigned to {self.restaurant.name} on {self.assignment_date}"


class CleaningTask(TimeStampedModel):
    """
    Cleaning task created automatically by AI detection or manually by hotel staff.
    """
    class TaskStatus(models.TextChoices):
        PENDING = 'PENDING', 'Pending Assignment'
        IN_PROGRESS = 'IN_PROGRESS', 'Cleaning In Progress'
        COMPLETED = 'COMPLETED', 'Completed by Staff'
        VERIFIED_CLEAN = 'VERIFIED_CLEAN', 'Verified Clean'
        FAILED_VERIFICATION = 'FAILED_VERIFICATION', 'Verification Failed'

    class Priority(models.TextChoices):
        LOW = 'LOW', 'Low'
        MEDIUM = 'MEDIUM', 'Medium'
        HIGH = 'HIGH', 'High'
        URGENT = 'URGENT', 'Urgent'

    hotel = models.ForeignKey(
        'hotels.Hotel',
        on_delete=models.CASCADE,
        related_name='cleaning_tasks'
    )
    restaurant = models.ForeignKey(
        'restaurants.Restaurant',
        on_delete=models.CASCADE,
        related_name='cleaning_tasks'
    )
    table = models.ForeignKey(
        'tables.RestaurantTable',
        on_delete=models.CASCADE,
        related_name='cleaning_tasks'
    )
    assigned_to = models.ForeignKey(
        Staff,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_cleaning_tasks'
    )
    status = models.CharField(
        max_length=30,
        choices=TaskStatus.choices,
        default=TaskStatus.PENDING,
    )
    priority = models.CharField(
        max_length=20,
        choices=Priority.choices,
        default=Priority.MEDIUM,
    )
    notes = models.TextField(blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    verified_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'cleaning_tasks'
        indexes = [
            models.Index(fields=['table', 'status']),
            models.Index(fields=['hotel', 'status']),
        ]

    def __str__(self):
        return f"Cleaning Task: Table {self.table.table_number} [{self.get_status_display()}]"


class CleaningTaskAssignment(TimeStampedModel):
    """
    Assignment tracking to support task reassignment history.
    """
    class AssignmentStatus(models.TextChoices):
        ASSIGNED = 'ASSIGNED', 'Assigned'
        REASSIGNED = 'REASSIGNED', 'Reassigned'
        COMPLETED = 'COMPLETED', 'Completed'

    task = models.ForeignKey(
        CleaningTask,
        on_delete=models.CASCADE,
        related_name='assignment_history'
    )
    staff = models.ForeignKey(Staff, on_delete=models.CASCADE)
    status = models.CharField(
        max_length=20,
        choices=AssignmentStatus.choices,
        default=AssignmentStatus.ASSIGNED,
    )
    notes = models.TextField(blank=True)

    class Meta:
        db_table = 'cleaning_task_assignments'

    def __str__(self):
        return f"Task {self.task.id} -> {self.staff} ({self.status})"
