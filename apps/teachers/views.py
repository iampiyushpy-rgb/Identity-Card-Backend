from django.contrib.auth import get_user_model
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import Teacher
from .serializers import TeacherSerializer, validate_teacher_username
from core.permissions import IsSchoolOrTeacher, IsSchoolAdmin

User = get_user_model()

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
        user = teacher.user

        raw_username = request.data.get('username')
        raw_password = request.data.get('new_password')

        new_username = raw_username.strip() if isinstance(raw_username, str) else None
        new_password = raw_password.strip() if isinstance(raw_password, str) else ''

        if raw_username is not None and not new_username:
            return Response({"username": ["Username cannot be empty."]}, status=status.HTTP_400_BAD_REQUEST)

        username_changed = bool(new_username and new_username != user.username)
        password_provided = bool(new_password)

        if not username_changed and not password_provided:
            return Response(
                {"error": "Please provide a new username or a new password to update."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if username_changed:
            user.username = validate_teacher_username(new_username, exclude_user_id=user.id)

        if password_provided:
            if len(new_password) < 6:
                return Response(
                    {"new_password": ["Password must be at least 6 characters long."]},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            user.set_password(new_password)
            user.raw_password = new_password

        user.save()
        return Response({
            "message": f"Login credentials updated for {user.get_full_name() or user.username} (@{user.username}).",
            "username": user.username,
        })

    @action(detail=False, methods=['get'])
    def me(self, request):
        user = request.user
        if hasattr(user, 'teacher_profile'):
            serializer = self.get_serializer(user.teacher_profile)
            return Response(serializer.data)
        return Response({"error": "Teacher profile not found."}, status=status.HTTP_404_NOT_FOUND)
