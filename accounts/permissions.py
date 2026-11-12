from rest_framework.permissions import BasePermission

from accounts.models import UserRole


class IsAdminRole(BasePermission):
    message = "Admin access required."

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.role in {UserRole.SUPER_ADMIN, UserRole.STAFF})


class IsSuperAdmin(BasePermission):
    message = "Super-admin access required."

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.role == UserRole.SUPER_ADMIN)


class IsMemberRole(BasePermission):
    message = "Member access required."

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.role == UserRole.MEMBER)
