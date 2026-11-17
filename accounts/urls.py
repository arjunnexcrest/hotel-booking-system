from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import UserViewSet, HotelMembershipViewSet

router = DefaultRouter()
router.register('users', UserViewSet, basename='user')
router.register('memberships', HotelMembershipViewSet, basename='hotel-membership')

urlpatterns = [
    path('', include(router.urls)),
]
