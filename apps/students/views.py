from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Q
from django.shortcuts import get_object_or_404
from .models import Student, StudentSessionHistory
from .serializers import StudentSerializer, SessionChangeSerializer
from apps.academics.models import AcademicSession, ClassLevel, Section
from core.permissions import IsSchoolOrTeacher, IsSchoolAdmin

class StudentViewSet(viewsets.ModelViewSet):
    serializer_class = StudentSerializer
    permission_classes = [IsSchoolOrTeacher]

    def get_queryset(self):
        user = self.request.user
        qs = Student.objects.select_related(
            'school', 'current_session', 'current_class', 'current_section'
        ).prefetch_related('session_history')

        if user.is_superuser or user.role == 'admin':
            school_id = self.request.query_params.get('school_id')
            if school_id:
                qs = qs.filter(school_id=school_id)
        elif user.role == 'school' and user.school:
            qs = qs.filter(school=user.school)
        elif user.role == 'teacher' and user.school:
            if hasattr(user, 'teacher_profile'):
                assigned_section_ids = user.teacher_profile.assigned_sections.values_list('id', flat=True)
                qs = qs.filter(school=user.school, current_section_id__in=assigned_section_ids)
            else:
                return Student.objects.none()
        elif user.school:
            qs = qs.filter(school=user.school)
        else:
            return Student.objects.none()

        # Query Filters
        class_id = self.request.query_params.get('class_id')
        if class_id:
            qs = qs.filter(current_class_id=class_id)

        section_id = self.request.query_params.get('section_id')
        if section_id:
            qs = qs.filter(current_section_id=section_id)

        session_id = self.request.query_params.get('session_id')
        if session_id:
            qs = qs.filter(current_session_id=session_id)

        card_status = self.request.query_params.get('id_card_status')
        if card_status:
            qs = qs.filter(id_card_status=card_status)

        search = self.request.query_params.get('search')
        if search:
            qs = qs.filter(
                Q(first_name__icontains=search) |
                Q(last_name__icontains=search) |
                Q(admission_number__icontains=search) |
                Q(roll_number__icontains=search) |
                Q(father_name__icontains=search)
            )

        return qs

    @action(detail=False, methods=['post'], permission_classes=[IsSchoolAdmin])
    def change_session(self, request):
        """Promote or transfer selected students to a new session/class/section."""
        serializer = SessionChangeSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        student_ids = serializer.validated_data['student_ids']
        target_session = get_object_or_404(AcademicSession, id=serializer.validated_data['target_session_id'])
        target_class = get_object_or_404(ClassLevel, id=serializer.validated_data['target_class_id'])
        target_section = get_object_or_404(Section, id=serializer.validated_data['target_section_id'])

        user = request.user
        school = user.school if hasattr(user, 'school') and user.school else None

        # Cross-school security check
        if school and not (user.is_superuser or user.role == 'admin'):
            if target_session.school_id != school.id or target_class.school_id != school.id or target_section.class_level.school_id != school.id:
                return Response({"detail": "Target academic session, class, or section does not belong to your school."}, status=status.HTTP_403_FORBIDDEN)

        # Integrity check: target section must belong to target class
        if target_section.class_level_id != target_class.id:
            return Response({"detail": f"Section '{target_section.name}' does not belong to class '{target_class.name}'."}, status=status.HTTP_400_BAD_REQUEST)

        students = self.get_queryset().filter(id__in=student_ids)
        updated_count = 0

        for student in students:
            # Update student record
            student.current_session = target_session
            student.current_class = target_class
            student.current_section = target_section
            student.id_card_status = 'pending'  # new card needed for new session
            student.save()

            # Record session history
            StudentSessionHistory.objects.create(
                student=student,
                session=target_session,
                class_level=target_class,
                section=target_section,
                roll_number=student.roll_number
            )
            updated_count += 1

        return Response({
            "message": f"Successfully updated session for {updated_count} students.",
            "updated_count": updated_count
        })

    @action(detail=False, methods=['post'])
    def bulk_status_update(self, request):
        """Update ID card status (e.g. mark printed/delivered) for multiple students."""
        student_ids = request.data.get('student_ids', [])
        new_status = request.data.get('status', 'printed')
        if new_status not in ['pending', 'printed', 'delivered']:
            return Response({"error": "Invalid status."}, status=status.HTTP_400_BAD_REQUEST)

        students = self.get_queryset().filter(id__in=student_ids)
        count = students.update(id_card_status=new_status)
        return Response({"message": f"Updated {count} student ID card statuses to '{new_status}'."})
