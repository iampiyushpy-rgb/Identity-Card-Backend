from rest_framework import serializers
from .models import School
from django.contrib.auth import get_user_model

User = get_user_model()

class SchoolAdminUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'phone', 'is_active']

class SchoolSerializer(serializers.ModelSerializer):
    code = serializers.CharField(required=False, allow_blank=True, default='')
    affiliation_number = serializers.CharField(required=False, allow_blank=True, allow_null=True, default='')
    total_students = serializers.SerializerMethodField()
    total_teachers = serializers.SerializerMethodField()
    admin_user = serializers.SerializerMethodField()
    admin_username = serializers.CharField(write_only=True, required=False)
    admin_password = serializers.CharField(write_only=True, required=False)

    class Meta:
        model = School
        fields = [
            'id', 'name', 'code', 'affiliation_number', 'address',
            'city', 'state', 'postal_code', 'phone', 'email', 'website',
            'principal_name', 'logo', 'status', 'subscription_plan',
            'card_price', 'total_students', 'total_teachers', 'admin_user',
            'admin_username', 'admin_password', 'created_at', 'updated_at'
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
        school = School.objects.create(**validated_data)

        if admin_username and admin_password:
            User.objects.create_user(
                username=admin_username,
                email=validated_data.get('email', ''),
                password=admin_password,
                role='school',
                school=school,
                first_name=validated_data.get('principal_name', ''),
            )
        return school
