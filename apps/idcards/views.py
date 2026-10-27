from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import IDCardTemplate, IDCardBatch
from .serializers import IDCardTemplateSerializer, IDCardBatchSerializer
from core.permissions import IsSchoolOrTeacher, IsSchoolAdmin, IsSuperAdmin

class IDCardTemplateViewSet(viewsets.ModelViewSet):
    serializer_class = IDCardTemplateSerializer

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [IsSchoolOrTeacher()]
        return [IsSchoolAdmin()]

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser or user.role == 'admin':
            return IDCardTemplate.objects.all()
        elif user.school:
            return IDCardTemplate.objects.filter(school=user.school) | IDCardTemplate.objects.filter(school__isnull=True)
        return IDCardTemplate.objects.filter(school__isnull=True)

    def perform_create(self, serializer):
        user = self.request.user
        if user.school and not (user.is_superuser or user.role == 'admin'):
            serializer.save(school=user.school)
        else:
            serializer.save()

    def perform_update(self, serializer):
        instance = serializer.instance
        if instance.school is None and not (self.request.user.is_superuser or self.request.user.role == 'admin'):
            raise permissions.PermissionDenied("You cannot modify a system default template.")
        serializer.save()

    def perform_destroy(self, instance):
        if instance.school is None and not (self.request.user.is_superuser or self.request.user.role == 'admin'):
            raise permissions.PermissionDenied("You cannot delete a system default template.")
        instance.delete()

class IDCardBatchViewSet(viewsets.ModelViewSet):
    serializer_class = IDCardBatchSerializer

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [IsSchoolOrTeacher()]
        return [IsSchoolAdmin()]

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser or user.role == 'admin':
            return IDCardBatch.objects.all()
        elif user.school:
            return IDCardBatch.objects.filter(school=user.school)
        return IDCardBatch.objects.none()

    def perform_create(self, serializer):
        user = self.request.user
        if user.school and not (user.is_superuser or user.role == 'admin'):
            serializer.save(school=user.school)
        else:
            serializer.save()
