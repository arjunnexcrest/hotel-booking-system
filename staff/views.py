from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils import timezone
from .models import Staff, StaffAssignment, CleaningTask, CleaningTaskAssignment
from .serializers import (
    StaffSerializer,
    StaffAssignmentSerializer,
    CleaningTaskSerializer,
    CleaningTaskAssignmentSerializer,
)


class StaffViewSet(viewsets.ModelViewSet):
    queryset = Staff.objects.select_related('user', 'hotel').all()
    serializer_class = StaffSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ['hotel', 'role', 'is_active']
    search_fields = ['user__username', 'user__email', 'employee_id']


class StaffAssignmentViewSet(viewsets.ModelViewSet):
    queryset = StaffAssignment.objects.select_related('staff__user', 'restaurant', 'table').all()
    serializer_class = StaffAssignmentSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ['restaurant', 'table', 'assignment_date', 'is_active']


class CleaningTaskViewSet(viewsets.ModelViewSet):
    queryset = CleaningTask.objects.select_related('hotel', 'restaurant', 'table', 'assigned_to__user').prefetch_related('assignment_history').all().order_by('-created_at')
    serializer_class = CleaningTaskSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ['hotel', 'restaurant', 'table', 'status', 'priority']

    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        task = self.get_object()
        task.status = CleaningTask.TaskStatus.COMPLETED
        task.completed_at = timezone.now()
        task.save()
        return Response({'status': 'Cleaning task completed'})

    @action(detail=True, methods=['post'])
    def start(self, request, pk=None):
        task = self.get_object()
        task.status = CleaningTask.TaskStatus.IN_PROGRESS
        task.started_at = timezone.now()
        task.save()
        return Response({'status': 'Cleaning task started'})


class CleaningTaskAssignmentViewSet(viewsets.ModelViewSet):
    queryset = CleaningTaskAssignment.objects.select_related('task', 'staff__user').all()
    serializer_class = CleaningTaskAssignmentSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ['task', 'staff', 'status']
