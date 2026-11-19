from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    HotelViewSet,
    HotelImageViewSet,
    HotelDocumentViewSet,
    HotelApprovalViewSet,
)

router = DefaultRouter()
router.register('hotels', HotelViewSet, basename='hotel')
router.register('images', HotelImageViewSet, basename='hotel-image')
router.register('documents', HotelDocumentViewSet, basename='hotel-document')
router.register('approvals', HotelApprovalViewSet, basename='hotel-approval')

urlpatterns = [
    path('', include(router.urls)),
]
