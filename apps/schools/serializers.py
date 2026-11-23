from rest_framework import serializers
from .models import School
from django.contrib.auth import get_user_model

User = get_user_model()

class SchoolAdminUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'phone', 'is_active', 'raw_password']

class SchoolSerializer(serializers.ModelSerializer):
    code = serializers.CharField(required=False, allow_blank=True, default='')
    affiliation_number = serializers.CharField(required=False, allow_blank=True, allow_null=True, default='')
    total_students = serializers.SerializerMethodField()
    total_teachers = serializers.SerializerMethodField()
    admin_user = serializers.SerializerMethodField()
    admin_username = serializers.CharField(write_only=True, required=False)
    admin_password = serializers.CharField(write_only=True, required=False)
    admin_email = serializers.EmailField(write_only=True, required=False, allow_blank=True)
    admin_is_active = serializers.BooleanField(write_only=True, required=False)

    class Meta:
        model = School
        fields = [
            'id', 'name', 'code', 'affiliation_number', 'address',
            'city', 'state', 'postal_code', 'phone', 'email', 'website',
            'principal_name', 'logo', 'status',
            'card_price', 'total_students', 'total_teachers', 'admin_user',
            'admin_username', 'admin_password', 'admin_email', 'admin_is_active',
            'created_at', 'updated_at'
        ]

    def get_total_students(self, obj):
        if hasattr(obj, 'students'):
            return obj.students.count()
        return 0

    def get_total_teachers(self, obj):
        if hasattr(obj, 'teachers'):
            return obj.teachers.count()
        return 0

    def get_admin_user(self, obj):
        admin = obj.users.filter(role='school').first()
        if admin:
            return SchoolAdminUserSerializer(admin).data
        return None

    def create(self, validated_data):
        admin_username = validated_data.pop('admin_username', None)
        admin_password = validated_data.pop('admin_password', None)
        admin_email = validated_data.pop('admin_email', None)
        admin_is_active = validated_data.pop('admin_is_active', None)
        school = School.objects.create(**validated_data)

        if admin_username and admin_password:
            user = User.objects.create_user(
                username=admin_username,
                email=admin_email or validated_data.get('email', '') or f"{admin_username}@school.com",
                password=admin_password,
                role='school',
                school=school,
                first_name=validated_data.get('principal_name', ''),
                is_active=admin_is_active if admin_is_active is not None else True,
            )
            user.raw_password = admin_password
            user.save(update_fields=['raw_password'])
        return school

    def update(self, instance, validated_data):
        admin_username = validated_data.pop('admin_username', None)
        admin_password = validated_data.pop('admin_password', None)
        admin_email = validated_data.pop('admin_email', None)
        admin_is_active = validated_data.pop('admin_is_active', None)

        school = super().update(instance, validated_data)

        admin_user = school.users.filter(role='school').first()
        if admin_user:
            if admin_username and admin_username != admin_user.username:
                if User.objects.filter(username=admin_username).exclude(id=admin_user.id).exists():
                    raise serializers.ValidationError({"admin_username": "Username already exists."})
                admin_user.username = admin_username
            if admin_email is not None:
                admin_user.email = admin_email
            if admin_password:
                admin_user.set_password(admin_password)
                admin_user.raw_password = admin_password
            if admin_is_active is not None:
                admin_user.is_active = admin_is_active
            admin_user.save()
        elif admin_username and admin_password:
            if User.objects.filter(username=admin_username).exists():
                raise serializers.ValidationError({"admin_username": "Username already exists."})
            user = User.objects.create_user(
                username=admin_username,
                email=admin_email or school.email or f"{admin_username}@school.com",
                password=admin_password,
                role='school',
                school=school,
                first_name=school.principal_name or school.name,
                is_active=admin_is_active if admin_is_active is not None else True,
            )
            user.raw_password = admin_password
            user.save(update_fields=['raw_password'])

        return school
