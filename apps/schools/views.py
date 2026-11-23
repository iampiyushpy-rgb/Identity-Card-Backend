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
        if self.action in ['list', 'create', 'destroy', 'toggle_status', 'stats']:
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
