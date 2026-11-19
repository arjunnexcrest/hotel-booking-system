from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    CameraViewSet,
    AIEventViewSet,
    ServiceAlertViewSet,
    MonitoringOutageViewSet,
)

router = DefaultRouter()
router.register('cameras', CameraViewSet, basename='camera')
router.register('events', AIEventViewSet, basename='ai-event')
router.register('alerts', ServiceAlertViewSet, basename='service-alert')
router.register('outages', MonitoringOutageViewSet, basename='monitoring-outage')

urlpatterns = [
    path('', include(router.urls)),
]
