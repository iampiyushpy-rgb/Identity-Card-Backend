from rest_framework import permissions

class IsSuperAdmin(permissions.BasePermission):
    """Allows access only to Super Admins / Platform Admins."""
    def has_permission(self, request, view):
        return bool(
            request.user and 
            request.user.is_authenticated and 
            (request.user.role == 'admin' or request.user.is_superuser)
        )

class IsSchoolAdmin(permissions.BasePermission):
    """Allows access to School Admins or Super Admins."""
    def has_permission(self, request, view):
        return bool(
            request.user and 
            request.user.is_authenticated and 
            (request.user.role in ['school', 'admin'] or request.user.is_superuser)
        )

class IsTeacher(permissions.BasePermission):
    """Allows access to Teachers."""
    def has_permission(self, request, view):
        return bool(
            request.user and 
            request.user.is_authenticated and 
            request.user.role == 'teacher'
        )

class IsSchoolOrTeacher(permissions.BasePermission):
    """Allows access to School Admins, Teachers, and Super Admins."""
    def has_permission(self, request, view):
        return bool(
            request.user and 
            request.user.is_authenticated and 
            (request.user.role in ['school', 'teacher', 'admin'] or request.user.is_superuser)
        )
