from rest_framework import serializers
from django.shortcuts import get_object_or_404
from .models import Student, StudentSessionHistory

class StudentSessionHistorySerializer(serializers.ModelSerializer):
    session_name = serializers.CharField(source='session.name', read_only=True)
    class_name = serializers.CharField(source='class_level.name', read_only=True)
    section_name = serializers.CharField(source='section.name', read_only=True)

    class Meta:
        model = StudentSessionHistory
        fields = ['id', 'session', 'session_name', 'class_level', 'class_name', 'section', 'section_name', 'roll_number', 'created_at']

class StudentSerializer(serializers.ModelSerializer):
    full_name = serializers.ReadOnlyField()
    class_name = serializers.CharField(source='current_class.name', read_only=True)
    section_name = serializers.CharField(source='current_section.name', read_only=True)
    session_name = serializers.CharField(source='current_session.name', read_only=True)
    school_name = serializers.CharField(source='school.name', read_only=True)
    school_code = serializers.CharField(source='school.code', read_only=True)
    session_history = StudentSessionHistorySerializer(many=True, read_only=True)

    class Meta:
        model = Student
        fields = [
            'id', 'school', 'school_name', 'school_code', 'admission_number',
            'roll_number', 'first_name', 'last_name', 'full_name', 'gender',
            'dob', 'blood_group', 'father_name', 'mother_name',
            'emergency_contact', 'address', 'photo',
            'current_session', 'session_name',
            'current_class', 'class_name',
            'current_section', 'section_name',
            'id_card_status', 'is_active', 'session_history',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'school', 'created_at', 'updated_at']

    def validate(self, attrs):
        request = self.context.get('request')
        user = request.user if request else None
        school = user.school if user and hasattr(user, 'school') and user.school else None

        section = attrs.get('current_section')
        if not section and self.instance:
            section = self.instance.current_section

        class_level = attrs.get('current_class')
        if not class_level and self.instance:
            class_level = self.instance.current_class

        session = attrs.get('current_session')
        if not session and self.instance:
            session = self.instance.current_session

        # Ensure section belongs to class
        if section and class_level and section.class_level_id != class_level.id:
            raise serializers.ValidationError({
                "current_section": f"Selected section '{section.name}' does not belong to class '{class_level.name}'."
            })

        # Ensure entities belong to the school
        if school and not (user.is_superuser or user.role == 'admin'):
            if class_level and class_level.school_id != school.id:
                raise serializers.ValidationError({"current_class": "Class does not belong to your school."})
            if section and section.school_id != school.id:
                raise serializers.ValidationError({"current_section": "Section does not belong to your school."})
            if session and session.school_id != school.id:
                raise serializers.ValidationError({"current_session": "Session does not belong to your school."})

        # Teacher specific scoping check
        if user and user.role == 'teacher':
            if not hasattr(user, 'teacher_profile'):
                raise serializers.ValidationError({"detail": "Teacher profile not found."})
            assigned_sections = list(user.teacher_profile.assigned_sections.all())
            assigned_section_ids = [s.id for s in assigned_sections]
            assigned_class_ids = [s.class_level_id for s in assigned_sections]

            if section and section.id not in assigned_section_ids:
                raise serializers.ValidationError({
                    "current_section": "You are only permitted to manage students in your assigned class section."
                })

            if class_level and class_level.id not in assigned_class_ids:
                raise serializers.ValidationError({
                    "current_class": "You are only permitted to manage students in your assigned class."
                })
        return attrs

    def create(self, validated_data):
        request = self.context.get('request')
        if request and request.user:
            if request.user.is_superuser or request.user.role == 'admin':
                school_id = request.data.get('school') or request.data.get('school_id')
                if school_id:
                    from apps.schools.models import School
                    validated_data['school'] = get_object_or_404(School, id=school_id)
            elif request.user.school:
                validated_data['school'] = request.user.school
        student = super().create(validated_data)

        # Record initial history
        if student.current_session and student.current_class and student.current_section:
            StudentSessionHistory.objects.create(
                student=student,
                session=student.current_session,
                class_level=student.current_class,
                section=student.current_section,
                roll_number=student.roll_number
            )
        return student

class SessionChangeSerializer(serializers.Serializer):
    student_ids = serializers.ListField(child=serializers.IntegerField(), required=True)
    target_session_id = serializers.IntegerField(required=True)
    target_class_id = serializers.IntegerField(required=True)
    target_section_id = serializers.IntegerField(required=True)
