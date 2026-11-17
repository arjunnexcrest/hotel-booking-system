from rest_framework import serializers
from .models import Hotel, HotelImage, HotelDocument, HotelApproval


class HotelImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = HotelImage
        fields = ['id', 'hotel', 'image', 'caption', 'is_primary', 'created_at']
        read_only_fields = ['id', 'created_at']


class HotelDocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = HotelDocument
        fields = ['id', 'hotel', 'document_type', 'file', 'status', 'rejection_reason', 'created_at']
        read_only_fields = ['id', 'created_at']


class HotelApprovalSerializer(serializers.ModelSerializer):
    reviewed_by_username = serializers.CharField(source='reviewed_by.username', read_only=True)

    class Meta:
        model = HotelApproval
        fields = ['id', 'hotel', 'reviewed_by', 'reviewed_by_username', 'decision', 'reason', 'created_at']
        read_only_fields = ['id', 'reviewed_by', 'created_at']


class HotelSerializer(serializers.ModelSerializer):
    images = HotelImageSerializer(many=True, read_only=True)
    documents = HotelDocumentSerializer(many=True, read_only=True)
    owner_email = serializers.EmailField(source='owner.email', read_only=True)

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
            'status',
            'is_active',
            'images',
            'documents',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
