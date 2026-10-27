from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
from apps.schools.models import School

User = get_user_model()

class AccountsAuthTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.school = School.objects.create(name="Greenwood High", code="GWH")
        self.admin = User.objects.create_superuser(
            username="admin", email="admin@example.com", password="adminpassword123", role="admin"
        )
        self.school_user = User.objects.create_user(
            username="school_admin", email="school@example.com", password="schoolpassword123", role="school", school=self.school
        )

    def test_login_returns_token_and_context(self):
        res = self.client.post('/api/v1/auth/login/', {
            'username': 'school_admin',
            'password': 'schoolpassword123'
        })
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn('access', res.data)
        self.assertIn('user', res.data)
        self.assertEqual(res.data['user']['role'], 'school')
        self.assertEqual(res.data['user']['school_id'], self.school.id)

    def test_profile_patch_cannot_elevate_role_or_switch_school(self):
        self.client.force_authenticate(user=self.school_user)
        other_school = School.objects.create(name="Other School", code="OTH")
        res = self.client.patch('/api/v1/auth/me/', {
            'role': 'admin',
            'school': other_school.id,
            'first_name': 'Updated Name'
        })
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.school_user.refresh_from_db()
        self.assertEqual(self.school_user.role, 'school')
        self.assertEqual(self.school_user.school.id, self.school.id)
        self.assertEqual(self.school_user.first_name, 'Updated Name')
