from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import RestaurantTableViewSet, TableZoneViewSet, TableEventViewSet

router = DefaultRouter()
router.register('tables', RestaurantTableViewSet, basename='table')
router.register('zones', TableZoneViewSet, basename='table-zone')
router.register('events', TableEventViewSet, basename='table-event')

urlpatterns = [
    path('', include(router.urls)),
]
