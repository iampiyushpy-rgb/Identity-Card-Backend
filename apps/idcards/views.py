from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.response import Response
from django.db.models import Q
from .models import IDCardTemplate, IDCardBatch
from .serializers import IDCardTemplateSerializer, IDCardBatchSerializer
from .template_detector import detect_raster_template_fields, detect_svg_template_fields
from core.permissions import IsSchoolOrTeacher, IsSchoolAdmin, IsSuperAdmin

class IDCardTemplateViewSet(viewsets.ModelViewSet):
    serializer_class = IDCardTemplateSerializer
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [IsSchoolOrTeacher()]
        return [IsSchoolAdmin()]

    def get_queryset(self):
        user = self.request.user
        school_id = self.request.query_params.get('school_id') or self.request.query_params.get('school')
        if user.is_superuser or user.role == 'admin':
            if school_id:
                return IDCardTemplate.objects.filter(Q(school_id=school_id) | Q(school__isnull=True))
            return IDCardTemplate.objects.all()
        elif user.school:
            return IDCardTemplate.objects.filter(school=user.school) | IDCardTemplate.objects.filter(school__isnull=True)
        return IDCardTemplate.objects.filter(school__isnull=True)

    def perform_create(self, serializer):
        user = self.request.user
        if user.school and not (user.is_superuser or user.role == 'admin'):
            instance = serializer.save(school=user.school)
        else:
            instance = serializer.save()

        if instance.school and instance.is_default:
            IDCardTemplate.objects.filter(school=instance.school).exclude(id=instance.id).update(is_default=False)

    def perform_update(self, serializer):
        instance = serializer.instance
        if instance.school is None and not (self.request.user.is_superuser or self.request.user.role == 'admin'):
            raise permissions.PermissionDenied("You cannot modify a system default template.")
        updated = serializer.save()
        if updated.school and updated.is_default:
            IDCardTemplate.objects.filter(school=updated.school).exclude(id=updated.id).update(is_default=False)

    @action(detail=False, methods=['post'], url_path='detect_fields')
    def detect_fields(self, request):
        """Inspect uploaded SVG/PNG/JPG ID card template and return detected fields and photo frame."""
        uploaded = request.FILES.get('file')
        if not uploaded:
            return Response({'error': 'Template file is required.'}, status=status.HTTP_400_BAD_REQUEST)

        filename = (uploaded.name or '').lower()
        content_type = (uploaded.content_type or '').lower()
        if filename.endswith('.svg') or 'svg' in content_type:
            svg_text = uploaded.read().decode('utf-8', errors='replace')
            result = detect_svg_template_fields(svg_text)
            result['svgContent'] = svg_text
            return Response(result, status=status.HTTP_200_OK)

        try:
            result = detect_raster_template_fields(uploaded)
            return Response(result, status=status.HTTP_200_OK)
        except Exception as exc:
            return Response(
                {'error': f'Could not process uploaded template image: {exc}'},
                status=status.HTTP_400_BAD_REQUEST,
            )

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
