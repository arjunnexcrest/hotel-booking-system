from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import NotificationViewSet, NotificationDeliveryViewSet

router = DefaultRouter()
router.register('notifications', NotificationViewSet, basename='notification')
router.register('deliveries', NotificationDeliveryViewSet, basename='notification-delivery')

urlpatterns = [
    path('', include(router.urls)),
]
