from django.contrib.auth.models import AbstractUser
from django.db import models
from core.models import TimeStampedModel


class User(AbstractUser):
    """
    Custom user model supporting multi-role platform access.
    """
    class Role(models.TextChoices):
        SUPER_ADMIN = 'super_admin', 'Super Administrator'
        HOTEL_OWNER = 'hotel_owner', 'Hotel Owner'
        HOTEL_ADMIN = 'hotel_admin', 'Hotel Administrator'
        STAFF = 'staff', 'Staff / Waiter / Cleaner'
        CUSTOMER = 'customer', 'Customer'

    email = models.EmailField(unique=True)
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.CUSTOMER,
    )
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True)
    is_verified = models.BooleanField(default=False)

    REQUIRED_FIELDS = ['email', 'first_name', 'last_name']

    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"


class HotelMembership(TimeStampedModel):
    """
    Tenant isolation & role mapping per hotel.
    Allows a user to hold specific permissions per hotel (e.g. manager in Hotel A, customer elsewhere).
    """
    class MembershipRole(models.TextChoices):
        OWNER = 'owner', 'Hotel Owner'
        ADMIN = 'admin', 'Hotel Administrator'
        MANAGER = 'manager', 'Manager'
        WAITER = 'waiter', 'Waiter'
        CLEANER = 'cleaner', 'Cleaner'
        STAFF = 'staff', 'General Staff'

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='hotel_memberships'
    )
    hotel = models.ForeignKey(
        'hotels.Hotel',
        on_delete=models.CASCADE,
        related_name='memberships'
    )
    role = models.CharField(
        max_length=20,
        choices=MembershipRole.choices,
        default=MembershipRole.STAFF,
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'hotel_memberships'
        unique_together = ('user', 'hotel', 'role')
        indexes = [
            models.Index(fields=['user', 'hotel']),
            models.Index(fields=['hotel', 'role']),
        ]

    def __str__(self):
        return f"{self.user.email} - {self.hotel.name} [{self.get_role_display()}]"


class PasswordResetToken(TimeStampedModel):
    """
    Password reset tokens for secure account recovery.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='password_resets')
    token = models.CharField(max_length=128, unique=True)
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)

    class Meta:
        db_table = 'password_resets'

    def __str__(self):
        return f"Reset token for {self.user.email}"
