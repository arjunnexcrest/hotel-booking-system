from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import Hotel, HotelImage, HotelDocument, HotelApproval
from .serializers import (
    HotelSerializer,
    HotelImageSerializer,
    HotelDocumentSerializer,
    HotelApprovalSerializer,
)


class HotelViewSet(viewsets.ModelViewSet):
    queryset = Hotel.objects.prefetch_related('images', 'documents').all().order_by('-created_at')
    serializer_class = HotelSerializer
    lookup_field = 'slug'
    filterset_fields = ['status', 'is_active', 'city', 'state']
    search_fields = ['name', 'description', 'city', 'address']

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [permissions.AllowAny()]
        return [permissions.IsAuthenticated()]

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)

    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAdminUser])
    def approve(self, request, slug=None):
        hotel = self.get_object()
        hotel.status = Hotel.Status.APPROVED
        hotel.save()
        approval = HotelApproval.objects.create(
            hotel=hotel,
            reviewed_by=request.user,
            decision=HotelApproval.Decision.APPROVED,
            reason=request.data.get('reason', 'Approved by super admin')
        )
        return Response({'status': 'Hotel approved', 'approval_id': approval.id})

    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAdminUser])
    def reject(self, request, slug=None):
        hotel = self.get_object()
        reason = request.data.get('reason', '')
        if not reason:
            return Response({'error': 'Rejection reason is required'}, status=status.HTTP_400_BAD_REQUEST)
        hotel.status = Hotel.Status.REJECTED
        hotel.save()
        approval = HotelApproval.objects.create(
            hotel=hotel,
            reviewed_by=request.user,
            decision=HotelApproval.Decision.REJECTED,
            reason=reason
        )
        return Response({'status': 'Hotel rejected', 'approval_id': approval.id})


class HotelImageViewSet(viewsets.ModelViewSet):
    queryset = HotelImage.objects.all()
    serializer_class = HotelImageSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    filterset_fields = ['hotel']


class HotelDocumentViewSet(viewsets.ModelViewSet):
    queryset = HotelDocument.objects.all()
    serializer_class = HotelDocumentSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ['hotel', 'status', 'document_type']
