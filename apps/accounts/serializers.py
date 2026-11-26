from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.contrib.auth import get_user_model

User = get_user_model()

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        # Custom claims
        token['username'] = user.username
        token['email'] = user.email
        token['role'] = user.role
        token['school_id'] = user.school.id if user.school else None
        token['school_name'] = user.school.name if user.school else None
        token['full_name'] = f"{user.first_name} {user.last_name}".strip() or user.username
        return token

    def validate(self, attrs):
        # Allow logging in via email, case-insensitive username, or whitespace-trimmed input
        username_input = str(attrs.get(self.username_field, '')).strip()
        attrs[self.username_field] = username_input

        user_match = None
        if '@' in username_input:
            user_match = User.objects.filter(email__iexact=username_input).first()
        if not user_match:
            user_match = User.objects.filter(username__iexact=username_input).first()

        if user_match:
            attrs[self.username_field] = user_match.username

            # Support password fallback for school accounts (e.g. school123 vs school_123)
            password_input = attrs.get('password', '')
            if not user_match.check_password(password_input):
                alt_pass = password_input.replace('_', '') if '_' in password_input else password_input.replace('school', 'school_')
                if user_match.check_password(alt_pass):
                    attrs['password'] = alt_pass

        data = super().validate(attrs)
        user = self.user
        data['user'] = {
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'role': user.role,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'phone': user.phone,
            'school_id': user.school.id if user.school else None,
            'school_name': user.school.name if user.school else None,
        }
        return data

class UserSerializer(serializers.ModelSerializer):
    school_name = serializers.CharField(source='school.name', read_only=True)

    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name',
            'role', 'phone', 'school', 'school_name', 'avatar', 'is_active'
        ]
        read_only_fields = ['id', 'role', 'school', 'is_active']

class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True, min_length=6)

    def validate_old_password(self, value):
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError("Current password is incorrect.")
        return value
