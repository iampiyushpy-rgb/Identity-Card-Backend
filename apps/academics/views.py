from rest_framework import viewsets, permissions
from .models import AcademicSession, ClassLevel, Section
from .serializers import AcademicSessionSerializer, ClassLevelSerializer, SectionSerializer
from core.permissions import IsSchoolOrTeacher, IsSchoolAdmin

class BaseSchoolIsolatedViewSet(viewsets.ModelViewSet):
    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [IsSchoolOrTeacher()]
        return [IsSchoolAdmin()]

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser or user.role == 'admin':
            school_id = self.request.query_params.get('school_id')
            if school_id:
                return self.model_class.objects.filter(school_id=school_id)
            return self.model_class.objects.all()
        elif user.school:
            return self.model_class.objects.filter(school=user.school)
        return self.model_class.objects.none()

    def perform_create(self, serializer):
        user = self.request.user
        if user.school and not (user.is_superuser or user.role == 'admin'):
            serializer.save(school=user.school)
        else:
            serializer.save()

class AcademicSessionViewSet(BaseSchoolIsolatedViewSet):
    model_class = AcademicSession
    serializer_class = AcademicSessionSerializer
    queryset = AcademicSession.objects.all()

class ClassLevelViewSet(BaseSchoolIsolatedViewSet):
    model_class = ClassLevel
    serializer_class = ClassLevelSerializer
    queryset = ClassLevel.objects.all()

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.role == 'teacher' and hasattr(user, 'teacher_profile'):
            assigned_class_ids = user.teacher_profile.assigned_sections.values_list('class_level_id', flat=True)
            return qs.filter(id__in=assigned_class_ids).distinct()
        return qs

class SectionViewSet(BaseSchoolIsolatedViewSet):
    model_class = Section
    serializer_class = SectionSerializer
    queryset = Section.objects.all()

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.role == 'teacher' and hasattr(user, 'teacher_profile'):
            assigned_section_ids = user.teacher_profile.assigned_sections.values_list('id', flat=True)
            qs = qs.filter(id__in=assigned_section_ids)
        class_id = self.request.query_params.get('class_id')
        if class_id:
            qs = qs.filter(class_level_id=class_id)
        return qs
