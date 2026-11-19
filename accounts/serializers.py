import uuid
from django.utils import timezone
from datetime import timedelta
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from .models import HotelMembership, PasswordResetToken

User = get_user_model()


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    Custom JWT serializer that supports login via either username or email,
    and includes user metadata in the login response.
    """
    def validate(self, attrs):
        username_or_email = attrs.get(self.username_field)
        if username_or_email and '@' in username_or_email:
            user_obj = User.objects.filter(email__iexact=username_or_email).first()
            if user_obj:
                attrs[self.username_field] = user_obj.username

        data = super().validate(attrs)
        data['user'] = {
            'id': self.user.id,
            'username': self.user.username,
            'email': self.user.email,
            'role': self.user.role,
            'first_name': self.user.first_name,
            'last_name': self.user.last_name,
        }
        return data


class HotelMembershipSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source='user.email', read_only=True)
    hotel_name = serializers.CharField(source='hotel.name', read_only=True)
    hotel_slug = serializers.CharField(source='hotel.slug', read_only=True)

    class Meta:
        model = HotelMembership
        fields = [
            'id',
            'user',
            'user_email',
            'hotel',
            'hotel_name',
            'hotel_slug',
            'role',
            'is_active',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            'id',
            'username',
            'email',
            'first_name',
            'last_name',
            'role',
            'phone_number',
            'avatar',
            'is_verified',
            'date_joined',
        ]
        read_only_fields = ['id', 'date_joined', 'is_verified']


class UserDetailSerializer(serializers.ModelSerializer):
    """
    Extended user profile serializer including hotel memberships.
    """
    hotel_memberships = HotelMembershipSerializer(many=True, read_only=True)

    class Meta:
        model = User
        fields = [
            'id',
            'username',
            'email',
            'first_name',
            'last_name',
            'role',
            'phone_number',
            'avatar',
            'is_verified',
            'hotel_memberships',
            'date_joined',
        ]
        read_only_fields = ['id', 'date_joined', 'is_verified', 'hotel_memberships']


class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = User
        fields = [
            'id',
            'username',
            'email',
            'password',
            'first_name',
            'last_name',
            'phone_number',
            'role',
        ]

    def validate_password(self, value):
        validate_password(value)
        return value

    def create(self, validated_data):
        password = validated_data.pop('password')
        user = User.objects.create_user(**validated_data)
        user.set_password(password)
        user.save()
        return user


class ChangePasswordSerializer(serializers.Serializer):
    """
    Serializer for password change by authenticated user (FR-003, FR-006).
    """
    old_password = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True)

    def validate_old_password(self, value):
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError("Current password is not correct.")
        return value

    def validate_new_password(self, value):
        validate_password(value, self.context['request'].user)
        return value


class PasswordResetRequestSerializer(serializers.Serializer):
    """
    Serializer to request a password reset token (FR-003).
    """
    email = serializers.EmailField(required=True)

    def validate_email(self, value):
        user = User.objects.filter(email__iexact=value).first()
        if not user:
            raise serializers.ValidationError("No account found with this email address.")
        return value


class PasswordResetConfirmSerializer(serializers.Serializer):
    """
    Serializer to set a new password using a reset token (FR-003).
    """
    token = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True)

    def validate(self, attrs):
        token_str = attrs.get('token')
        reset_token = PasswordResetToken.objects.filter(token=token_str, is_used=False).first()
        if not reset_token:
            raise serializers.ValidationError({"token": "Invalid or expired reset token."})
        if reset_token.expires_at < timezone.now():
            raise serializers.ValidationError({"token": "This reset token has expired."})

        validate_password(attrs.get('new_password'), reset_token.user)
        attrs['reset_token_obj'] = reset_token
        return attrs
