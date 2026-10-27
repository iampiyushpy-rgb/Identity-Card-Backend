from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.contrib.auth import get_user_model
from django.db.models import Count, Sum
from .models import School
from .serializers import SchoolSerializer
from core.permissions import IsSuperAdmin, IsSchoolAdmin

User = get_user_model()

class SchoolViewSet(viewsets.ModelViewSet):
    serializer_class = SchoolSerializer

    def get_permissions(self):
        if self.action in ['list', 'create', 'destroy', 'toggle_status', 'reset_admin_password', 'stats']:
            return [IsSuperAdmin()]
        # update, partial_update, retrieve require at least School Admin
        return [IsSchoolAdmin()]

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser or user.role == 'admin':
            return School.objects.all().prefetch_related('users', 'students', 'teachers')
        elif user.school:
            return School.objects.filter(id=user.school.id)
        return School.objects.none()

    @action(detail=True, methods=['post'], permission_classes=[IsSuperAdmin])
    def toggle_status(self, request, pk=None):
        school = self.get_object()
        school.status = 'inactive' if school.status == 'active' else 'active'
        school.save()
        return Response({"status": school.status, "message": f"School status updated to {school.status}"})

    @action(detail=True, methods=['post'], permission_classes=[IsSuperAdmin])
    def reset_admin_password(self, request, pk=None):
        school = self.get_object()
        new_password = request.data.get('new_password')
        if not new_password:
            return Response({"error": "new_password is required"}, status=status.HTTP_400_BAD_REQUEST)

        admin_user = school.users.filter(role='school').first()
        if not admin_user:
            # Create school admin if none exists
            username = f"school_{school.code.lower()}"
            admin_user = User.objects.create_user(
                username=username,
                email=school.email or f"{username}@school.com",
                password=new_password,
                role='school',
                school=school,
                first_name=school.principal_name or school.name
            )
            return Response({"message": f"School Admin created with username: {username}"})

        admin_user.set_password(new_password)
        admin_user.save()
        return Response({"message": f"Password reset successfully for admin user: {admin_user.username}"})

    @action(detail=False, methods=['get'], permission_classes=[IsSuperAdmin])
    def stats(self, request):
        total_schools = School.objects.count()
        active_schools = School.objects.filter(status='active').count()
        
        from apps.students.models import Student
        from apps.payments.models import Payment
        from apps.teachers.models import Teacher
        
        total_students = Student.objects.count()
        total_teachers = Teacher.objects.count()
        total_revenue = Payment.objects.filter(status='completed').aggregate(total=Sum('amount'))['total'] or 0

        recent_schools = School.objects.all()[:5]
        return Response({
            "total_schools": total_schools,
            "active_schools": active_schools,
            "total_students": total_students,
            "total_teachers": total_teachers,
            "total_revenue": float(total_revenue),
            "recent_schools": SchoolSerializer(recent_schools, many=True).data
        })
