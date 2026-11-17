from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import RestaurantViewSet, OperatingHoursViewSet, SpecialClosureViewSet

router = DefaultRouter()
router.register('restaurants', RestaurantViewSet, basename='restaurant')
router.register('operating-hours', OperatingHoursViewSet, basename='operating-hour')
router.register('special-closures', SpecialClosureViewSet, basename='special-closure')

urlpatterns = [
    path('', include(router.urls)),
]
