import uuid
from datetime import timedelta
from django.utils import timezone
from rest_framework import viewsets, permissions, status
from rest_framework.views import APIView
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import get_user_model
from .models import HotelMembership, PasswordResetToken
from .serializers import (
    UserSerializer,
    UserDetailSerializer,
    UserRegistrationSerializer,
    HotelMembershipSerializer,
    CustomTokenObtainPairSerializer,
    ChangePasswordSerializer,
    PasswordResetRequestSerializer,
    PasswordResetConfirmSerializer,
)
from core.permissions import IsSuperAdmin

User = get_user_model()


class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer


class LogoutView(APIView):
    """
    Blacklists the given refresh token on logout (FR-005).
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        try:
            refresh_token = request.data.get('refresh')
            if refresh_token:
                token = RefreshToken(refresh_token)
                token.blacklist()
            return Response({'status': 'Logged out successfully'}, status=status.HTTP_200_OK)
        except Exception:
            return Response({'status': 'Logged out'}, status=status.HTTP_200_OK)


class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.prefetch_related('hotel_memberships__hotel').all().order_by('-date_joined')
    serializer_class = UserSerializer

    def get_permissions(self):
        if self.action in ['create', 'register', 'password_reset', 'password_reset_confirm']:
            return [permissions.AllowAny()]
        if self.action in ['list', 'destroy']:
            return [IsSuperAdmin()]
        return [permissions.IsAuthenticated()]

    def get_serializer_class(self):
        if self.action == 'create':
            return UserRegistrationSerializer
        if self.action == 'me' and self.request.method == 'GET':
            return UserDetailSerializer
        if self.action == 'change_password':
            return ChangePasswordSerializer
        if self.action == 'password_reset':
            return PasswordResetRequestSerializer
        if self.action == 'password_reset_confirm':
            return PasswordResetConfirmSerializer
        return UserSerializer

    @action(detail=False, methods=['get', 'patch'], permission_classes=[permissions.IsAuthenticated])
    def me(self, request):
        if request.method == 'GET':
            serializer = UserDetailSerializer(request.user)
            return Response(serializer.data)
        elif request.method == 'PATCH':
            serializer = UserSerializer(request.user, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return Response(UserDetailSerializer(request.user).data)

    @action(detail=False, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def change_password(self, request):
        serializer = ChangePasswordSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        user = request.user
        user.set_password(serializer.validated_data['new_password'])
        user.save()
        return Response({'status': 'Password changed successfully.'}, status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'], permission_classes=[permissions.AllowAny])
    def password_reset(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data['email']
        user = User.objects.get(email__iexact=email)

        # Generate reset token valid for 1 hour
        token_str = uuid.uuid4().hex
        expires_at = timezone.now() + timedelta(hours=1)
        PasswordResetToken.objects.create(
            user=user,
            token=token_str,
            expires_at=expires_at,
        )

        # In production this would send an email; for dev, token is logged/returned
        return Response({
            'status': 'Password reset token generated.',
            'message': 'Check your email for reset instructions.',
            'reset_token': token_str  # returned for testing / dev convenience
        }, status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'], permission_classes=[permissions.AllowAny])
    def password_reset_confirm(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        reset_token_obj = serializer.validated_data['reset_token_obj']
        user = reset_token_obj.user

        user.set_password(serializer.validated_data['new_password'])
        user.save()

        reset_token_obj.is_used = True
        reset_token_obj.save()

        return Response({'status': 'Password has been reset successfully.'}, status=status.HTTP_200_OK)


class HotelMembershipViewSet(viewsets.ModelViewSet):
    queryset = HotelMembership.objects.select_related('user', 'hotel').all()
    serializer_class = HotelMembershipSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ['hotel', 'role', 'is_active']
    search_fields = ['user__email', 'hotel__name']
