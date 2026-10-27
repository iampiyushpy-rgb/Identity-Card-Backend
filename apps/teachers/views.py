from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import Teacher
from .serializers import TeacherSerializer
from core.permissions import IsSchoolOrTeacher, IsSchoolAdmin

class TeacherViewSet(viewsets.ModelViewSet):
    serializer_class = TeacherSerializer

    def get_permissions(self):
        if self.action in ['list', 'retrieve', 'me']:
            return [IsSchoolOrTeacher()]
        return [IsSchoolAdmin()]

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser or user.role == 'admin':
            school_id = self.request.query_params.get('school_id')
            if school_id:
                return Teacher.objects.filter(school_id=school_id)
            return Teacher.objects.all()
        elif user.role == 'school' and user.school:
            return Teacher.objects.filter(school=user.school)
        elif user.role == 'teacher' and hasattr(user, 'teacher_profile'):
            return Teacher.objects.filter(id=user.teacher_profile.id)
        return Teacher.objects.none()

    @action(detail=True, methods=['post'], permission_classes=[IsSchoolAdmin])
    def reset_password(self, request, pk=None):
        teacher = self.get_object()
        new_password = request.data.get('new_password')
        if not new_password:
            return Response({"error": "new_password is required"}, status=status.HTTP_400_BAD_REQUEST)
        
        teacher.user.set_password(new_password)
        teacher.user.save()
        return Response({"message": f"Password reset successfully for teacher: {teacher.user.username}"})

    @action(detail=False, methods=['get'])
    def me(self, request):
        user = request.user
        if hasattr(user, 'teacher_profile'):
            serializer = self.get_serializer(user.teacher_profile)
            return Response(serializer.data)
        return Response({"error": "Teacher profile not found."}, status=status.HTTP_404_NOT_FOUND)
