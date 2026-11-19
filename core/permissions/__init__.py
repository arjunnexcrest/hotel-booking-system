from rest_framework.permissions import BasePermission, SAFE_METHODS


class IsSuperAdmin(BasePermission):
    """
    Allows access only to super administrators.
    """
    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            (request.user.role == 'super_admin' or request.user.is_superuser)
        )


class IsHotelOwner(BasePermission):
    """
    Allows access to hotel owners or super administrators.
    """
    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            request.user.role in ['hotel_owner', 'super_admin']
        )


class IsHotelAdmin(BasePermission):
    """
    Allows access to hotel administrators, owners, or super administrators.
    """
    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            request.user.role in ['hotel_admin', 'hotel_owner', 'super_admin']
        )


class IsStaffMember(BasePermission):
    """
    Allows access to hotel staff (waiters, cleaners, managers) and admins.
    """
    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            request.user.role in ['staff', 'hotel_admin', 'hotel_owner', 'super_admin']
        )


class IsCustomer(BasePermission):
    """
    Allows access to customers.
    """
    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            request.user.role == 'customer'
        )


class IsOwnerOrAdminOrReadOnly(BasePermission):
    """
    Read permissions for anyone; write permissions only to the owner or superadmin.
    """
    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        if not (request.user and request.user.is_authenticated):
            return False
        if request.user.role == 'super_admin' or request.user.is_superuser:
            return True
        if hasattr(obj, 'owner'):
            return obj.owner == request.user
        if hasattr(obj, 'user'):
            return obj.user == request.user
        return False


class HasHotelScopedAccess(BasePermission):
    """
    Enforces multi-tenant isolation (BR-002, BR-013).
    Verifies that the user has an active HotelMembership for the target hotel,
    or is a platform Super Administrator.
    """
    allowed_roles = ['owner', 'admin', 'manager', 'waiter', 'cleaner', 'staff']

    def has_object_permission(self, request, view, obj):
        if not (request.user and request.user.is_authenticated):
            return False

        if request.user.role == 'super_admin' or request.user.is_superuser:
            return True

        # Extract hotel instance from the object
        hotel = None
        if hasattr(obj, 'hotel'):
            hotel = obj.hotel
        elif hasattr(obj, 'restaurant') and hasattr(obj.restaurant, 'hotel'):
            hotel = obj.restaurant.hotel
        elif obj.__class__.__name__ == 'Hotel':
            hotel = obj

        if not hotel:
            return False

        # Check hotel membership
        return request.user.hotel_memberships.filter(
            hotel=hotel,
            is_active=True,
            role__in=self.allowed_roles
        ).exists()


class HotelScopedQuerySetMixin:
    """
    Mixin for ViewSets to enforce hotel-level data isolation automatically.
    - Superadmins see all records.
    - Hotel staff/admins only see records belonging to their active hotel memberships.
    - Customers only see public or own records.
    """
    hotel_field = 'hotel'

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user

        if not user or not user.is_authenticated:
            return qs

        if user.role == 'super_admin' or user.is_superuser:
            return qs

        if user.role in ['hotel_owner', 'hotel_admin', 'staff']:
            hotel_ids = user.hotel_memberships.filter(is_active=True).values_list('hotel_id', flat=True)
            filter_kwargs = {f"{self.hotel_field}__in": hotel_ids}
            return qs.filter(**filter_kwargs)

        if user.role == 'customer' and hasattr(qs.model, 'customer'):
            return qs.filter(customer=user)

        return qs
