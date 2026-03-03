from rest_framework.permissions import BasePermission

class IsEmployer(BasePermission):
    def has_permission(self, request, view):
        if not request.user:
            return False
        try:
            return request.user.profile.active_role == 'employer'
        except AttributeError:
            # Handle case where user might not have a profile created yet
            return False