import uuid
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
    admission_number = serializers.CharField(required=False, allow_blank=True, default='')
    gender = serializers.ChoiceField(choices=Student.GENDER_CHOICES, required=False, default='Male')
    dob = serializers.DateField(required=False, allow_null=True)
    blood_group = serializers.CharField(required=False, allow_blank=True, allow_null=True, default='')
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
            'emergency_contact', 'address', 'photo', 'photo_number',
            'current_session', 'session_name',
            'current_class', 'class_name',
            'current_section', 'section_name',
            'extra_fields',
            'id_card_status', 'is_active', 'session_history',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'school', 'created_at', 'updated_at']

    def to_internal_value(self, data):
        # Normalize empty strings from multipart FormData into None / defaults
        if hasattr(data, 'copy'):
            mutable = data.copy()
        elif isinstance(data, dict):
            mutable = dict(data)
        else:
            mutable = data

        if isinstance(mutable, dict):
            for nullable_field in ('dob', 'current_section', 'current_session', 'current_class'):
                if mutable.get(nullable_field) == '':
                    mutable[nullable_field] = None
            if mutable.get('gender') == '':
                mutable['gender'] = 'Male'

        return super().to_internal_value(mutable)

    def _resolve_school(self, request):
        user = request.user if request else None
        if user and (user.is_superuser or user.role == 'admin'):
            school_id = request.data.get('school') or request.data.get('school_id')
            if school_id:
                from apps.schools.models import School
                return get_object_or_404(School, id=school_id)
        if user and hasattr(user, 'school') and user.school:
            return user.school
        if self.instance:
            return self.instance.school
        return None

    def validate(self, attrs):
        request = self.context.get('request')
        user = request.user if request else None
        school = self._resolve_school(request)

        if 'first_name' in attrs:
            attrs['first_name'] = (attrs['first_name'] or '').strip()
            if not attrs['first_name']:
                raise serializers.ValidationError({"first_name": "Student name is required."})

        section = attrs.get('current_section')
        if 'current_section' not in attrs and self.instance:
            section = self.instance.current_section

        class_level = attrs.get('current_class')
        if 'current_class' not in attrs and self.instance:
            class_level = self.instance.current_class

        session = attrs.get('current_session')
        if 'current_session' not in attrs and self.instance:
            session = self.instance.current_session

        if not self.partial and not class_level:
            raise serializers.ValidationError({"current_class": "Class is required."})

        adm_no = (attrs.get('admission_number') or '').strip()
        if adm_no and school:
            qs = Student.objects.filter(school=school, admission_number=adm_no)
            if self.instance:
                qs = qs.exclude(id=self.instance.id)
            if qs.exists():
                raise serializers.ValidationError({
                    "admission_number": "A student with this admission number already exists in this school."
                })

        # Ensure section belongs to class
        if section and class_level and section.class_level_id != class_level.id:
            raise serializers.ValidationError({
                "current_section": f"Selected section '{section.name}' does not belong to class '{class_level.name}'."
            })

        # Ensure entities belong to the school
        if school and user and not (user.is_superuser or user.role == 'admin'):
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

    def _generate_admission_number(self, school):
        prefix = f"ADM-{(school.code or 'SCH').upper()}"
        seq = Student.objects.filter(school=school).count() + 1
        candidate = f"{prefix}-{seq:04d}"
        while Student.objects.filter(school=school, admission_number=candidate).exists():
            seq += 1
            candidate = f"{prefix}-{seq:04d}"
            if seq > 99999:
                candidate = f"{prefix}-{uuid.uuid4().hex[:6].upper()}"
                break
        return candidate

    def create(self, validated_data):
        request = self.context.get('request')
        school = self._resolve_school(request)
        if school:
            validated_data['school'] = school

        adm_no = (validated_data.get('admission_number') or '').strip()
        if not adm_no and school:
            adm_no = self._generate_admission_number(school)
        elif not adm_no:
            adm_no = f"ADM-{uuid.uuid4().hex[:8].upper()}"
        validated_data['admission_number'] = adm_no

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

    def update(self, instance, validated_data):
        if 'admission_number' in validated_data and not (validated_data['admission_number'] or '').strip():
            validated_data['admission_number'] = instance.admission_number
        return super().update(instance, validated_data)

class SessionChangeSerializer(serializers.Serializer):
    student_ids = serializers.ListField(child=serializers.IntegerField(), required=True)
    target_session_id = serializers.IntegerField(required=True)
    target_class_id = serializers.IntegerField(required=True)
    target_section_id = serializers.IntegerField(required=True)
