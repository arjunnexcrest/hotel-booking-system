from rest_framework import serializers
from .models import Hotel, HotelImage, HotelDocument, HotelApproval


class HotelImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = HotelImage
        fields = ['id', 'hotel', 'image', 'caption', 'is_primary', 'created_at']
        read_only_fields = ['id', 'created_at']


class HotelDocumentSerializer(serializers.ModelSerializer):
    hotel_name = serializers.CharField(source='hotel.name', read_only=True)
    document_type_display = serializers.CharField(source='get_document_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = HotelDocument
        fields = [
            'id',
            'hotel',
            'hotel_name',
            'document_type',
            'document_type_display',
            'file',
            'status',
            'status_display',
            'rejection_reason',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'status', 'rejection_reason', 'created_at', 'updated_at']


class HotelApprovalSerializer(serializers.ModelSerializer):
    reviewed_by_username = serializers.CharField(source='reviewed_by.username', read_only=True)
    decision_display = serializers.CharField(source='get_decision_display', read_only=True)

    class Meta:
        model = HotelApproval
        fields = [
            'id',
            'hotel',
            'reviewed_by',
            'reviewed_by_username',
            'decision',
            'decision_display',
            'reason',
            'created_at',
        ]
        read_only_fields = ['id', 'reviewed_by', 'created_at']


class HotelApprovalStatusSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    approval_history = HotelApprovalSerializer(many=True, read_only=True)
    documents = HotelDocumentSerializer(many=True, read_only=True)
    total_documents = serializers.SerializerMethodField()
    approved_documents = serializers.SerializerMethodField()
    pending_documents = serializers.SerializerMethodField()
    rejected_documents = serializers.SerializerMethodField()
    is_ready_for_review = serializers.SerializerMethodField()

    class Meta:
        model = Hotel
        fields = [
            'id',
            'name',
            'slug',
            'status',
            'status_display',
            'is_active',
            'total_documents',
            'approved_documents',
            'pending_documents',
            'rejected_documents',
            'is_ready_for_review',
            'documents',
            'approval_history',
            'created_at',
            'updated_at',
        ]

    def get_total_documents(self, obj):
        return obj.documents.count()

    def get_approved_documents(self, obj):
        return obj.documents.filter(status=HotelDocument.VerificationStatus.APPROVED).count()

    def get_pending_documents(self, obj):
        return obj.documents.filter(status=HotelDocument.VerificationStatus.PENDING).count()

    def get_rejected_documents(self, obj):
        return obj.documents.filter(status=HotelDocument.VerificationStatus.REJECTED).count()

    def get_is_ready_for_review(self, obj):
        return obj.documents.exists()


class HotelSummarySerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    total_restaurants = serializers.SerializerMethodField()
    total_tables = serializers.SerializerMethodField()
    total_capacity = serializers.SerializerMethodField()
    active_bookings_today = serializers.SerializerMethodField()
    staff_count = serializers.SerializerMethodField()

    class Meta:
        model = Hotel
        fields = [
            'id',
            'name',
            'slug',
            'status',
            'status_display',
            'is_active',
            'total_restaurants',
            'total_tables',
            'total_capacity',
            'active_bookings_today',
            'staff_count',
            'created_at',
        ]

    def get_total_restaurants(self, obj):
        return obj.restaurants.filter(is_active=True).count()

    def get_total_tables(self, obj):
        from tables.models import RestaurantTable
        return RestaurantTable.objects.filter(restaurant__hotel=obj, is_active=True).count()

    def get_total_capacity(self, obj):
        from django.db.models import Sum
        from tables.models import RestaurantTable
        res = RestaurantTable.objects.filter(restaurant__hotel=obj, is_active=True).aggregate(Sum('capacity'))
        return res['capacity__sum'] or 0

    def get_active_bookings_today(self, obj):
        from django.utils import timezone
        from bookings.models import Booking
        today = timezone.localdate()
        return Booking.objects.filter(
            hotel=obj,
            booking_date=today,
            booking_status__in=['CONFIRMED', 'CHECKED_IN']
        ).count()

    def get_staff_count(self, obj):
        from accounts.models import HotelMembership
        return HotelMembership.objects.filter(
            hotel=obj,
            is_active=True,
            role__in=[HotelMembership.MembershipRole.STAFF, HotelMembership.MembershipRole.ADMIN]
        ).count()


class HotelSerializer(serializers.ModelSerializer):
    images = HotelImageSerializer(many=True, read_only=True)
    documents = HotelDocumentSerializer(many=True, read_only=True)
    owner_email = serializers.EmailField(source='owner.email', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    slug = serializers.SlugField(required=False, allow_blank=True)

    class Meta:
        model = Hotel
        fields = [
            'id',
            'name',
            'slug',
            'owner',
            'owner_email',
            'description',
            'hotel_type',
            'email',
            'phone',
            'address',
            'city',
            'state',
            'postal_code',
            'country',
            'latitude',
            'longitude',
            'star_rating',
            'amenities',
            'check_in_time',
            'check_out_time',
            'status',
            'status_display',
            'is_active',
            'images',
            'documents',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'owner', 'status', 'created_at', 'updated_at']
