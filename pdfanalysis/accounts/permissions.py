from rest_framework.permissions import BasePermission


class IsOwnerOrAdmin(BasePermission):
    def has_object_permission(self, request, view, obj):
        owner = getattr(obj, "owner", None)
        return bool(request.user and request.user.is_authenticated) and (
            request.user.is_staff or owner == request.user
        )
