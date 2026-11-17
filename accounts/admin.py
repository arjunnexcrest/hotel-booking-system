from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, HotelMembership, PasswordResetToken


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ('username', 'email', 'first_name', 'last_name', 'role', 'is_verified', 'is_staff')
    list_filter = ('role', 'is_verified', 'is_staff', 'is_active')
    search_fields = ('username', 'email', 'first_name', 'last_name', 'phone_number')
    fieldsets = BaseUserAdmin.fieldsets + (
        ('Custom Profile', {'fields': ('role', 'phone_number', 'avatar', 'is_verified')}),
    )


@admin.register(HotelMembership)
class HotelMembershipAdmin(admin.ModelAdmin):
    list_display = ('user', 'hotel', 'role', 'is_active', 'created_at')
    list_filter = ('role', 'is_active', 'hotel')
    search_fields = ('user__email', 'user__username', 'hotel__name')


@admin.register(PasswordResetToken)
class PasswordResetTokenAdmin(admin.ModelAdmin):
    list_display = ('user', 'is_used', 'expires_at', 'created_at')
    list_filter = ('is_used',)
    search_fields = ('user__email',)
