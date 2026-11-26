import re
from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.db import transaction
from .models import Teacher

User = get_user_model()
USERNAME_PATTERN = re.compile(r'^[\w.@+-]+$')


def validate_teacher_username(username, exclude_user_id=None):
    """Validate format and case-insensitive uniqueness of a teacher login username."""
    if not username:
        raise serializers.ValidationError({"username": ["Username cannot be empty."]})
    if not USERNAME_PATTERN.match(username):
        raise serializers.ValidationError({
            "username": ["Username may only contain letters, numbers, and @/./+/-/_ characters (no spaces)."]
        })
    qs = User.objects.filter(username__iexact=username)
    if exclude_user_id is not None:
        qs = qs.exclude(id=exclude_user_id)
    if qs.exists():
        raise serializers.ValidationError({"username": ["This username is already taken. Please choose another."]})
    return username

class AssignedSectionInfoSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    class_name = serializers.CharField(source='class_level.name')

class TeacherSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', required=False, allow_blank=True)
    email = serializers.EmailField(source='user.email', required=False, allow_blank=True, default='')
    first_name = serializers.CharField(source='user.first_name')
    last_name = serializers.CharField(source='user.last_name', required=False, allow_blank=True, default='')
    employee_id = serializers.CharField(required=False, allow_blank=True, default='')
    password = serializers.CharField(write_only=True, required=False, allow_blank=True, default='')
    raw_password = serializers.SerializerMethodField()
    assigned_sections = serializers.SerializerMethodField()
    school_name = serializers.CharField(source='school.name', read_only=True)

    class Meta:
        model = Teacher
        fields = [
            'id', 'school', 'school_name', 'employee_id', 'designation',
            'qualification', 'phone', 'address', 'joining_date', 'is_active',
            'username', 'email', 'first_name', 'last_name', 'password', 'raw_password',
            'assigned_sections', 'created_at'
        ]
        read_only_fields = ['id', 'school', 'created_at']

    def get_raw_password(self, obj):
        request = self.context.get('request')
        if request and request.user and (request.user.role in ['admin', 'school'] or request.user.is_superuser):
            return obj.user.raw_password or ''
        return ''

    def get_assigned_sections(self, obj):
        sections = obj.assigned_sections.all()
        return [
            {
                'id': s.id,
                'name': s.name,
                'class_id': s.class_level.id,
                'class_name': s.class_level.name
            }
            for s in sections
        ]

    def create(self, validated_data):
        user_data = validated_data.pop('user', {})
        raw_password = (validated_data.pop('password', None) or '').strip()
        password = raw_password or 'teacher123'

        request = self.context.get('request')
        school = request.user.school if request and hasattr(request.user, 'school') and request.user.school else validated_data.get('school')

        if not school and request:
            school_id = request.data.get('school') or request.data.get('school_id')
            if school_id:
                from apps.schools.models import School
                school = School.objects.filter(id=school_id).first()

        if not school:
            raise serializers.ValidationError({"school": "School association is required to create a faculty teacher."})

        first_name = (user_data.get('first_name') or validated_data.get('first_name') or '').strip()
        last_name = (user_data.get('last_name') or validated_data.get('last_name') or '').strip()

        custom_username = (user_data.get('username') or '').strip()
        if custom_username:
            username = validate_teacher_username(custom_username)
        else:
            # Clean username generation based on first name and school
            clean_name = re.sub(r'[^a-zA-Z0-9]', '', first_name).lower() or 'teacher'
            school_prefix = f"{school.code.lower()}_" if school and school.code else ""
            base_username = f"{school_prefix}{clean_name}"
            username = base_username
            counter = 1
            while User.objects.filter(username__iexact=username).exists():
                username = f"{base_username}{counter}"
                counter += 1

        email = user_data.get('email') or f"{username}@school.internal"

        # Auto-generate employee_id if not supplied
        if not validated_data.get('employee_id'):
            count = Teacher.objects.filter(school=school).count() + 1
            candidate_id = f"TCH-{count:03d}"
            while Teacher.objects.filter(school=school, employee_id=candidate_id).exists():
                count += 1
                candidate_id = f"TCH-{count:03d}"
            validated_data['employee_id'] = candidate_id

        with transaction.atomic():
            user = User.objects.create_user(
                username=username,
                email=email,
                first_name=first_name,
                last_name=last_name,
                password=password,
                role='teacher',
                school=school,
                raw_password=password,
            )
            teacher = Teacher.objects.create(user=user, school=school, **validated_data)
        return teacher

    def update(self, instance, validated_data):
        user_data = validated_data.pop('user', {})
        raw_password = (validated_data.pop('password', None) or '').strip()
        user = instance.user

        if 'username' in user_data:
            new_username = (user_data.get('username') or '').strip()
            if new_username != user.username:
                user.username = validate_teacher_username(new_username, exclude_user_id=user.id)
        if 'first_name' in user_data and user_data['first_name']:
            user.first_name = user_data['first_name'].strip()
        if 'last_name' in user_data:
            user.last_name = user_data['last_name'].strip()
        if 'email' in user_data and user_data['email']:
            user.email = user_data['email'].strip()
        if raw_password:
            user.set_password(raw_password)
            user.raw_password = raw_password
        user.save()

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance
