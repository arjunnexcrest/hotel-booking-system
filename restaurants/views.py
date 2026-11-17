from rest_framework import viewsets, permissions
from .models import Restaurant, RestaurantImage, OperatingHours, SpecialClosure
from .serializers import (
    RestaurantSerializer,
    RestaurantImageSerializer,
    OperatingHoursSerializer,
    SpecialClosureSerializer,
)


class RestaurantViewSet(viewsets.ModelViewSet):
    queryset = Restaurant.objects.prefetch_related('images', 'operating_hours').all().order_by('-created_at')
    serializer_class = RestaurantSerializer
    filterset_fields = ['hotel', 'is_active', 'cuisine_type']
    search_fields = ['name', 'cuisine_type', 'description']

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [permissions.AllowAny()]
        return [permissions.IsAuthenticated()]


class OperatingHoursViewSet(viewsets.ModelViewSet):
    queryset = OperatingHours.objects.all().order_by('day_of_week')
    serializer_class = OperatingHoursSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    filterset_fields = ['restaurant', 'day_of_week', 'is_closed']


class SpecialClosureViewSet(viewsets.ModelViewSet):
    queryset = SpecialClosure.objects.all().order_by('-closure_date')
    serializer_class = SpecialClosureSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    filterset_fields = ['restaurant', 'closure_date']
