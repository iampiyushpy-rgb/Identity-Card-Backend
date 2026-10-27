from rest_framework import serializers
from .models import AcademicSession, ClassLevel, Section

class AcademicSessionSerializer(serializers.ModelSerializer):
    class Meta:
        model = AcademicSession
        fields = ['id', 'school', 'name', 'start_date', 'end_date', 'is_active', 'created_at']
        read_only_fields = ['id', 'school', 'created_at']

class SectionSerializer(serializers.ModelSerializer):
    class_name = serializers.CharField(source='class_level.name', read_only=True)
    teacher_name = serializers.SerializerMethodField()

    class Meta:
        model = Section
        fields = ['id', 'school', 'class_level', 'class_name', 'name', 'teacher', 'teacher_name', 'created_at']
        read_only_fields = ['id', 'school', 'created_at']

    def get_teacher_name(self, obj):
        if obj.teacher and obj.teacher.user:
            return f"{obj.teacher.user.first_name} {obj.teacher.user.last_name}".strip() or obj.teacher.user.username
        return None

    def validate(self, attrs):
        request = self.context.get('request')
        user = request.user if request else None
        school = user.school if user and hasattr(user, 'school') and user.school else None

        class_level = attrs.get('class_level')
        teacher = attrs.get('teacher')

        if school and not (user.is_superuser or user.role == 'admin'):
            if class_level and class_level.school_id != school.id:
                raise serializers.ValidationError({"class_level": "Selected class does not belong to your school."})
            if teacher and teacher.school_id != school.id:
                raise serializers.ValidationError({"teacher": "Selected teacher does not belong to your school."})
        elif class_level and teacher and teacher.school_id != class_level.school_id:
            raise serializers.ValidationError({"teacher": "Teacher and class must belong to the same school."})

        return attrs

class ClassLevelSerializer(serializers.ModelSerializer):
    sections = SectionSerializer(many=True, read_only=True)
    student_count = serializers.SerializerMethodField()

    class Meta:
        model = ClassLevel
        fields = ['id', 'school', 'name', 'order', 'sections', 'student_count', 'created_at']
        read_only_fields = ['id', 'school', 'created_at']

    def get_student_count(self, obj):
        if hasattr(obj, 'students'):
            return obj.students.count()
        return 0
