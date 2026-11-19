from django.db import models
from django.core.exceptions import PermissionDenied
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser

from .models import Hotel, HotelImage, HotelDocument, HotelApproval
from .serializers import (
    HotelSerializer,
    HotelImageSerializer,
    HotelDocumentSerializer,
    HotelApprovalSerializer,
    HotelApprovalStatusSerializer,
    HotelSummarySerializer,
)
from core.permissions import IsSuperAdmin, IsOwnerOrAdminOrReadOnly
from accounts.models import HotelMembership, User
from audit.models import AuditLog
from notifications.models import Notification


def _create_audit_log(actor, hotel, action, entity_type, entity_id, reason='', old_val=None, new_val=None):
    try:
        AuditLog.objects.create(
            actor=actor if actor and actor.is_authenticated else None,
            actor_type=AuditLog.ActorType.USER,
            hotel=hotel,
            action=action,
            entity_type=entity_type,
            entity_id=str(entity_id),
            reason=reason,
            old_values=old_val or {},
            new_values=new_val or {},
        )
    except Exception:
        pass


def _notify_hotel_owner(hotel, title, message):
    try:
        if hotel and hotel.owner:
            Notification.objects.create(
                recipient=hotel.owner,
                hotel=hotel,
                title=title,
                message=message,
                notification_type=Notification.NotificationType.HOTEL_APPROVAL,
            )
    except Exception:
        pass


class HotelViewSet(viewsets.ModelViewSet):
    serializer_class = HotelSerializer
    lookup_field = 'slug'
    filterset_fields = ['status', 'is_active', 'city', 'state', 'star_rating']
    search_fields = ['name', 'description', 'city', 'address', 'amenities']

    def get_queryset(self):
        user = self.request.user
        base_qs = Hotel.objects.prefetch_related('images', 'documents', 'approval_history')

        if not user or not user.is_authenticated:
            return base_qs.filter(status=Hotel.Status.APPROVED, is_active=True).order_by('-created_at')

        if getattr(user, 'role', '') == User.Role.SUPER_ADMIN or user.is_superuser:
            return base_qs.all().order_by('-created_at')

        # Hotel owners/staff can see their own hotels in any status + public approved hotels
        return base_qs.filter(
            models.Q(owner=user) |
            models.Q(memberships__user=user, memberships__is_active=True) |
            models.Q(status=Hotel.Status.APPROVED, is_active=True)
        ).distinct().order_by('-created_at')

    def get_permissions(self):
        if self.action in ['list', 'retrieve', 'restaurants']:
            return [permissions.AllowAny()]
        if self.action in ['create', 'my_hotels']:
            return [permissions.IsAuthenticated()]
        if self.action in ['approve', 'reject', 'under_review', 'suspend', 'pending_approvals']:
            return [IsSuperAdmin()]
        if self.action in ['submit_for_approval', 'approval_status', 'summary']:
            return [permissions.IsAuthenticated()]
        return [IsOwnerOrAdminOrReadOnly()]

    def perform_create(self, serializer):
        user = self.request.user
        hotel = serializer.save(
            owner=user,
            status=Hotel.Status.PENDING_APPROVAL,
            is_active=True,
        )

        # Promote user to hotel_owner if they were just customer
        if user.role == User.Role.CUSTOMER:
            user.role = User.Role.HOTEL_OWNER
            user.save(update_fields=['role'])

        # Multi-tenant membership assignment
        HotelMembership.objects.get_or_create(
            user=user,
            hotel=hotel,
            role=HotelMembership.MembershipRole.OWNER,
            defaults={'is_active': True}
        )

        _create_audit_log(
            actor=user,
            hotel=hotel,
            action=AuditLog.Action.CREATE,
            entity_type='Hotel',
            entity_id=hotel.id,
            reason='Hotel registered by owner',
            new_val={'name': hotel.name, 'status': hotel.status}
        )

    @action(detail=False, methods=['get'])
    def my_hotels(self, request):
        """List all hotels owned by or managed by the requesting user."""
        hotels = Hotel.objects.prefetch_related('images', 'documents', 'approval_history').filter(
            models.Q(owner=request.user) |
            models.Q(memberships__user=request.user, memberships__is_active=True)
        ).distinct().order_by('-created_at')

        page = self.paginate_queryset(hotels)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(hotels, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def pending_approvals(self, request):
        """Super Admin: List hotels awaiting approval or under review."""
        pending_qs = Hotel.objects.prefetch_related('images', 'documents', 'approval_history').filter(
            status__in=[Hotel.Status.PENDING_APPROVAL, Hotel.Status.UNDER_REVIEW]
        ).order_by('-created_at')

        page = self.paginate_queryset(pending_qs)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(pending_qs, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def submit_for_approval(self, request, slug=None):
        """Hotel Owner: Submit draft or rejected hotel for super-admin verification."""
        hotel = self.get_object()

        # Check ownership/admin permissions
        is_owner = hotel.owner == request.user or HotelMembership.objects.filter(
            hotel=hotel, user=request.user, role__in=[HotelMembership.MembershipRole.OWNER, HotelMembership.MembershipRole.ADMIN], is_active=True
        ).exists()

        if not is_owner and not request.user.role == User.Role.SUPER_ADMIN:
            raise PermissionDenied("Only the hotel owner or administrator can submit for approval.")

        if not hotel.documents.exists():
            return Response(
                {
                    'error': 'At least one verification document (e.g. Business License, Identity Proof) must be uploaded before submitting for approval.'
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        old_status = hotel.status
        hotel.status = Hotel.Status.PENDING_APPROVAL
        hotel.save(update_fields=['status', 'updated_at'])

        approval = HotelApproval.objects.create(
            hotel=hotel,
            reviewed_by=None,
            decision=HotelApproval.Decision.UNDER_REVIEW,
            reason=request.data.get('notes', 'Submitted for review by owner')
        )

        _create_audit_log(
            actor=request.user,
            hotel=hotel,
            action=AuditLog.Action.STATUS_CHANGE,
            entity_type='Hotel',
            entity_id=hotel.id,
            reason='Submitted for super-admin approval',
            old_val={'status': old_status},
            new_val={'status': hotel.status}
        )

        return Response({
            'status': 'Hotel submitted for approval successfully',
            'hotel_status': hotel.status,
            'approval_id': approval.id
        })

    @action(detail=True, methods=['get'])
    def approval_status(self, request, slug=None):
        """Retrieve onboarding and approval status, document checklist, and approval audit logs."""
        hotel = self.get_object()
        serializer = HotelApprovalStatusSerializer(hotel)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def restaurants(self, request, slug=None):
        """List active restaurants for this hotel (filtered by public visibility rules)."""
        hotel = self.get_object()
        user = request.user
        qs = hotel.restaurants.prefetch_related('images', 'operating_hours')

        # Public visitors see active restaurants of active approved hotels
        if not user or not user.is_authenticated or getattr(user, 'role', '') == User.Role.CUSTOMER:
            qs = qs.filter(is_active=True)

        from restaurants.serializers import RestaurantSerializer
        serializer = RestaurantSerializer(qs, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def summary(self, request, slug=None):
        """Operational KPI overview for hotel dashboard."""
        hotel = self.get_object()
        serializer = HotelSummarySerializer(hotel)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def approve(self, request, slug=None):
        """Super Admin: Approve hotel registration."""
        hotel = self.get_object()
        old_status = hotel.status
        reason = request.data.get('reason', 'Approved by super admin')

        hotel.status = Hotel.Status.APPROVED
        hotel.is_active = True
        hotel.save(update_fields=['status', 'is_active', 'updated_at'])

        approval = HotelApproval.objects.create(
            hotel=hotel,
            reviewed_by=request.user,
            decision=HotelApproval.Decision.APPROVED,
            reason=reason
        )

        _create_audit_log(
            actor=request.user,
            hotel=hotel,
            action=AuditLog.Action.APPROVE,
            entity_type='Hotel',
            entity_id=hotel.id,
            reason=reason,
            old_val={'status': old_status},
            new_val={'status': hotel.status}
        )

        _notify_hotel_owner(
            hotel=hotel,
            title=f"Hotel Approved: {hotel.name}",
            message=f"Congratulations! Your hotel '{hotel.name}' has been approved and is now active on GrandTable."
        )

        return Response({
            'status': 'Hotel approved successfully',
            'hotel_status': hotel.status,
            'approval_id': approval.id
        })

    @action(detail=True, methods=['post'])
    def reject(self, request, slug=None):
        """Super Admin: Reject hotel registration with required reason."""
        hotel = self.get_object()
        reason = request.data.get('reason', '').strip()
        if not reason:
            return Response({'error': 'Rejection reason is required.'}, status=status.HTTP_400_BAD_REQUEST)

        old_status = hotel.status
        hotel.status = Hotel.Status.REJECTED
        hotel.save(update_fields=['status', 'updated_at'])

        approval = HotelApproval.objects.create(
            hotel=hotel,
            reviewed_by=request.user,
            decision=HotelApproval.Decision.REJECTED,
            reason=reason
        )

        _create_audit_log(
            actor=request.user,
            hotel=hotel,
            action=AuditLog.Action.REJECT,
            entity_type='Hotel',
            entity_id=hotel.id,
            reason=reason,
            old_val={'status': old_status},
            new_val={'status': hotel.status}
        )

        _notify_hotel_owner(
            hotel=hotel,
            title=f"Hotel Registration Rejected: {hotel.name}",
            message=f"Your hotel registration was rejected for the following reason: {reason}. Please address this and resubmit."
        )

        return Response({
            'status': 'Hotel rejected',
            'hotel_status': hotel.status,
            'approval_id': approval.id
        })

    @action(detail=True, methods=['post'])
    def under_review(self, request, slug=None):
        """Super Admin: Move hotel status to Under Review."""
        hotel = self.get_object()
        reason = request.data.get('reason', 'Verification in progress')

        old_status = hotel.status
        hotel.status = Hotel.Status.UNDER_REVIEW
        hotel.save(update_fields=['status', 'updated_at'])

        approval = HotelApproval.objects.create(
            hotel=hotel,
            reviewed_by=request.user,
            decision=HotelApproval.Decision.UNDER_REVIEW,
            reason=reason
        )

        _create_audit_log(
            actor=request.user,
            hotel=hotel,
            action=AuditLog.Action.STATUS_CHANGE,
            entity_type='Hotel',
            entity_id=hotel.id,
            reason=reason,
            old_val={'status': old_status},
            new_val={'status': hotel.status}
        )

        _notify_hotel_owner(
            hotel=hotel,
            title=f"Hotel Under Review: {hotel.name}",
            message=f"Your hotel registration documents are currently under review by our compliance team."
        )

        return Response({
            'status': 'Hotel moved to under review',
            'hotel_status': hotel.status,
            'approval_id': approval.id
        })

    @action(detail=True, methods=['post'])
    def suspend(self, request, slug=None):
        """Super Admin: Suspend an existing hotel."""
        hotel = self.get_object()
        reason = request.data.get('reason', '').strip()
        if not reason:
            return Response({'error': 'Suspension reason is required.'}, status=status.HTTP_400_BAD_REQUEST)

        old_status = hotel.status
        hotel.status = Hotel.Status.SUSPENDED
        hotel.is_active = False
        hotel.save(update_fields=['status', 'is_active', 'updated_at'])

        approval = HotelApproval.objects.create(
            hotel=hotel,
            reviewed_by=request.user,
            decision=HotelApproval.Decision.SUSPENDED,
            reason=reason
        )

        _create_audit_log(
            actor=request.user,
            hotel=hotel,
            action=AuditLog.Action.STATUS_CHANGE,
            entity_type='Hotel',
            entity_id=hotel.id,
            reason=reason,
            old_val={'status': old_status, 'is_active': True},
            new_val={'status': hotel.status, 'is_active': False}
        )

        _notify_hotel_owner(
            hotel=hotel,
            title=f"Hotel Suspended: {hotel.name}",
            message=f"Your hotel operations have been suspended: {reason}. Please contact platform support."
        )

        return Response({
            'status': 'Hotel suspended',
            'hotel_status': hotel.status,
            'approval_id': approval.id
        })


class HotelImageViewSet(viewsets.ModelViewSet):
    queryset = HotelImage.objects.all()
    serializer_class = HotelImageSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    filterset_fields = ['hotel']


class HotelDocumentViewSet(viewsets.ModelViewSet):
    serializer_class = HotelDocumentSerializer
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    filterset_fields = ['hotel', 'status', 'document_type']

    def get_queryset(self):
        user = self.request.user
        if not user or not user.is_authenticated:
            return HotelDocument.objects.none()

        if getattr(user, 'role', '') == User.Role.SUPER_ADMIN or user.is_superuser:
            return HotelDocument.objects.select_related('hotel').all().order_by('-created_at')

        # Hotel owners/staff see only documents for their hotels
        return HotelDocument.objects.select_related('hotel').filter(
            models.Q(hotel__owner=user) |
            models.Q(hotel__memberships__user=user, hotel__memberships__is_active=True)
        ).distinct().order_by('-created_at')

    def get_permissions(self):
        if self.action == 'document_types':
            return [permissions.AllowAny()]
        if self.action in ['verify', 'reject']:
            return [IsSuperAdmin()]
        return [permissions.IsAuthenticated()]

    def perform_create(self, serializer):
        user = self.request.user
        hotel = serializer.validated_data.get('hotel')

        # Check that user owns or manages the target hotel
        if getattr(user, 'role', '') != User.Role.SUPER_ADMIN and not user.is_superuser:
            has_access = (hotel.owner == user) or HotelMembership.objects.filter(
                hotel=hotel,
                user=user,
                role__in=[HotelMembership.MembershipRole.OWNER, HotelMembership.MembershipRole.ADMIN],
                is_active=True
            ).exists()
            if not has_access:
                raise PermissionDenied("You do not have permission to upload documents for this hotel.")

        document = serializer.save(status=HotelDocument.VerificationStatus.PENDING)

        _create_audit_log(
            actor=user,
            hotel=hotel,
            action=AuditLog.Action.CREATE,
            entity_type='HotelDocument',
            entity_id=document.id,
            reason=f"Document uploaded: {document.get_document_type_display()}",
            new_val={'document_type': document.document_type, 'status': document.status}
        )

    @action(detail=False, methods=['get'])
    def document_types(self, request):
        """List allowed document types for hotel verification."""
        types = [
            {'value': choice[0], 'label': choice[1]}
            for choice in HotelDocument.DocumentType.choices
        ]
        return Response(types)

    @action(detail=True, methods=['post'])
    def verify(self, request, pk=None):
        """Super Admin: Verify and approve a specific legal document."""
        document = self.get_object()
        old_status = document.status
        document.status = HotelDocument.VerificationStatus.APPROVED
        document.rejection_reason = ''
        document.save(update_fields=['status', 'rejection_reason', 'updated_at'])

        _create_audit_log(
            actor=request.user,
            hotel=document.hotel,
            action=AuditLog.Action.APPROVE,
            entity_type='HotelDocument',
            entity_id=document.id,
            reason=f"Document approved: {document.get_document_type_display()}",
            old_val={'status': old_status},
            new_val={'status': document.status}
        )

        return Response({
            'status': 'Document approved',
            'document_id': document.id,
            'verification_status': document.status
        })

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        """Super Admin: Reject a specific legal document with feedback."""
        document = self.get_object()
        reason = request.data.get('reason', '').strip()
        if not reason:
            return Response({'error': 'Rejection reason is required.'}, status=status.HTTP_400_BAD_REQUEST)

        old_status = document.status
        document.status = HotelDocument.VerificationStatus.REJECTED
        document.rejection_reason = reason
        document.save(update_fields=['status', 'rejection_reason', 'updated_at'])

        _create_audit_log(
            actor=request.user,
            hotel=document.hotel,
            action=AuditLog.Action.REJECT,
            entity_type='HotelDocument',
            entity_id=document.id,
            reason=f"Document rejected: {reason}",
            old_val={'status': old_status},
            new_val={'status': document.status}
        )

        _notify_hotel_owner(
            hotel=document.hotel,
            title=f"Document Rejected: {document.get_document_type_display()}",
            message=f"Your {document.get_document_type_display()} for hotel '{document.hotel.name}' was rejected: {reason}. Please re-upload a valid document."
        )

        return Response({
            'status': 'Document rejected',
            'document_id': document.id,
            'verification_status': document.status,
            'rejection_reason': document.rejection_reason
        })


class HotelApprovalViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Audited history of hotel approvals, rejections, reviews, and suspensions.
    """
    queryset = HotelApproval.objects.select_related('hotel', 'reviewed_by').all().order_by('-created_at')
    serializer_class = HotelApprovalSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ['hotel', 'decision', 'reviewed_by']

    def get_queryset(self):
        user = self.request.user
        if getattr(user, 'role', '') == User.Role.SUPER_ADMIN or user.is_superuser:
            return self.queryset

        # Hotel owners/staff see approval decisions for their hotels
        return self.queryset.filter(
            models.Q(hotel__owner=user) |
            models.Q(hotel__memberships__user=user, hotel__memberships__is_active=True)
        ).distinct()

