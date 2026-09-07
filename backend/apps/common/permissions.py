from rest_framework import permissions
from apps.users.models import UserRole


class IsOwnerPermission(permissions.BasePermission):
    """
    Custom permission to only allow owners of an object to access or edit it.
    Requires model object to have `owner` or `user` attribute.
    """

    def has_object_permission(self, request, view, obj):
        if not request.user or not request.user.is_authenticated:
            return False

        if hasattr(obj, 'owner'):
            return obj.owner == request.user
        elif hasattr(obj, 'user'):
            return obj.user == request.user

        return False


class IsAdminOrStaffUser(permissions.BasePermission):
    """
    Permission check granting access only to superusers, staff, or users with role ADMIN/SUPERADMIN.
    """

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return (
            request.user.is_superuser or
            request.user.is_staff or
            getattr(request.user, 'role', '') in [UserRole.SUPERADMIN, UserRole.ADMIN]
        )


class IsModeratorOrAdminUser(permissions.BasePermission):
    """
    Permission check granting access to Moderators, Admins, and Staff.
    """

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return (
            request.user.is_superuser or
            request.user.is_staff or
            getattr(request.user, 'role', '') in [UserRole.SUPERADMIN, UserRole.ADMIN, UserRole.MODERATOR]
        )
