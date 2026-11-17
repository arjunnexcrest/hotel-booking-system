from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import HotelViewSet, HotelImageViewSet, HotelDocumentViewSet

router = DefaultRouter()
router.register('hotels', HotelViewSet, basename='hotel')
router.register('images', HotelImageViewSet, basename='hotel-image')
router.register('documents', HotelDocumentViewSet, basename='hotel-document')

urlpatterns = [
    path('', include(router.urls)),
]
