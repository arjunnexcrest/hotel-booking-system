from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    StaffViewSet,
    StaffAssignmentViewSet,
    CleaningTaskViewSet,
    CleaningTaskAssignmentViewSet,
)

router = DefaultRouter()
router.register('members', StaffViewSet, basename='staff-member')
router.register('assignments', StaffAssignmentViewSet, basename='staff-assignment')
router.register('cleaning-tasks', CleaningTaskViewSet, basename='cleaning-task')
router.register('cleaning-assignments', CleaningTaskAssignmentViewSet, basename='cleaning-assignment')

urlpatterns = [
    path('', include(router.urls)),
]
