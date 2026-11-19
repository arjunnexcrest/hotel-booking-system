from rest_framework import serializers
from .models import Staff, StaffAssignment, CleaningTask, CleaningTaskAssignment


class CleaningTaskAssignmentSerializer(serializers.ModelSerializer):
    staff_name = serializers.CharField(source='staff.user.get_full_name', read_only=True)

    class Meta:
        model = CleaningTaskAssignment
        fields = ['id', 'task', 'staff', 'staff_name', 'status', 'notes', 'created_at']
        read_only_fields = ['id', 'created_at']


class CleaningTaskSerializer(serializers.ModelSerializer):
    table_number = serializers.CharField(source='table.table_number', read_only=True)
    assigned_to_name = serializers.CharField(source='assigned_to.user.get_full_name', read_only=True)
    assignment_history = CleaningTaskAssignmentSerializer(many=True, read_only=True)

    class Meta:
        model = CleaningTask
        fields = [
            'id',
            'hotel',
            'restaurant',
            'table',
            'table_number',
            'assigned_to',
            'assigned_to_name',
            'status',
            'priority',
            'notes',
            'started_at',
            'completed_at',
            'verified_at',
            'assignment_history',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class StaffAssignmentSerializer(serializers.ModelSerializer):
    staff_name = serializers.CharField(source='staff.user.get_full_name', read_only=True)
    table_number = serializers.CharField(source='table.table_number', read_only=True)

    class Meta:
        model = StaffAssignment
        fields = [
            'id',
            'staff',
            'staff_name',
            'restaurant',
            'table',
            'table_number',
            'assignment_date',
            'shift_start',
            'shift_end',
            'is_active',
            'created_at',
        ]
        read_only_fields = ['id', 'created_at']


class StaffSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(source='user.email', read_only=True)
    full_name = serializers.CharField(source='user.get_full_name', read_only=True)
    hotel_name = serializers.CharField(source='hotel.name', read_only=True)

    class Meta:
        model = Staff
        fields = [
            'id',
            'hotel',
            'hotel_name',
            'user',
            'email',
            'full_name',
            'employee_id',
            'role',
            'phone',
            'is_active',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
