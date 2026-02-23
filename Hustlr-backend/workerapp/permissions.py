from rest_framework import permissions
from authapp.models import Profile

class IsWorker(permissions.BasePermission):
    def has_permission(self, request, view):
        if not request.user:
            return False
        
        # 2. Check if the profile role is 'worker'
        # Since you used a OneToOneField with related_name='profile', 
        # you can access it directly via request.user.profile
        try:
            return request.user.profile.active_role == 'worker'
        except AttributeError:
            # Handle case where user might not have a profile created yet
            return False