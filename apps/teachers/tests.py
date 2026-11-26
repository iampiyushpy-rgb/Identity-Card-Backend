from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
from apps.schools.models import School
from apps.teachers.models import Teacher

User = get_user_model()


class TeacherCredentialsTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.school = School.objects.create(name="Greenwood High", code="GWH")
        self.other_school = School.objects.create(name="Riverdale High", code="RVH")

        self.school_admin = User.objects.create_user(
            username="school_gwh",
            email="school@gwh.edu",
            password="schoolpassword123",
            role="school",
            school=self.school,
        )
        self.other_school_admin = User.objects.create_user(
            username="school_rvh",
            email="school@rvh.edu",
            password="schoolpassword123",
            role="school",
            school=self.other_school,
        )
        self.teacher_user = User.objects.create_user(
            username="gwh_alan",
            email="alan@gwh.edu",
            first_name="Alan",
            last_name="Turing",
            password="oldpassword123",
            role="teacher",
            school=self.school,
            raw_password="oldpassword123",
        )
        self.teacher = Teacher.objects.create(
            user=self.teacher_user,
            school=self.school,
            employee_id="TCH-001",
            designation="HOD",
        )
        self.second_teacher_user = User.objects.create_user(
            username="gwh_sarah",
            email="sarah@gwh.edu",
            first_name="Sarah",
            password="sarahpassword123",
            role="teacher",
            school=self.school,
        )
        self.second_teacher = Teacher.objects.create(
            user=self.second_teacher_user,
            school=self.school,
            employee_id="TCH-002",
        )

    def test_school_admin_can_update_username_and_password_and_teacher_can_login(self):
        self.client.force_authenticate(user=self.school_admin)
        res = self.client.post(
            f"/api/v1/teachers/{self.teacher.id}/reset_password/",
            {"username": "alan_custom", "new_password": "newsecret123"},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["username"], "alan_custom")

        self.teacher_user.refresh_from_db()
        self.assertEqual(self.teacher_user.username, "alan_custom")
        self.assertEqual(self.teacher_user.raw_password, "newsecret123")
        self.assertTrue(self.teacher_user.check_password("newsecret123"))

        # Verify teacher can log in with the newly set username and password
        self.client.force_authenticate(user=None)
        login_res = self.client.post(
            "/api/v1/auth/login/",
            {"username": "alan_custom", "password": "newsecret123"},
            format="json",
        )
        self.assertEqual(login_res.status_code, status.HTTP_200_OK)
        self.assertEqual(login_res.data["user"]["username"], "alan_custom")
        self.assertEqual(login_res.data["user"]["role"], "teacher")

    def test_school_admin_can_update_only_username_keeping_existing_password(self):
        self.client.force_authenticate(user=self.school_admin)
        res = self.client.post(
            f"/api/v1/teachers/{self.teacher.id}/reset_password/",
            {"username": "alan_renamed"},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        self.client.force_authenticate(user=None)
        login_res = self.client.post(
            "/api/v1/auth/login/",
            {"username": "alan_renamed", "password": "oldpassword123"},
            format="json",
        )
        self.assertEqual(login_res.status_code, status.HTTP_200_OK)

    def test_rejects_duplicate_or_invalid_username_and_short_password(self):
        self.client.force_authenticate(user=self.school_admin)

        dup_res = self.client.post(
            f"/api/v1/teachers/{self.teacher.id}/reset_password/",
            {"username": "GWH_SARAH"},
            format="json",
        )
        self.assertEqual(dup_res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("username", dup_res.data)

        space_res = self.client.post(
            f"/api/v1/teachers/{self.teacher.id}/reset_password/",
            {"username": "alan turing"},
            format="json",
        )
        self.assertEqual(space_res.status_code, status.HTTP_400_BAD_REQUEST)

        short_pw_res = self.client.post(
            f"/api/v1/teachers/{self.teacher.id}/reset_password/",
            {"new_password": "123"},
            format="json",
        )
        self.assertEqual(short_pw_res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("new_password", short_pw_res.data)

    def test_cross_school_and_teacher_permissions_blocked(self):
        self.client.force_authenticate(user=self.other_school_admin)
        cross_res = self.client.post(
            f"/api/v1/teachers/{self.teacher.id}/reset_password/",
            {"username": "hijack", "new_password": "password123"},
            format="json",
        )
        self.assertEqual(cross_res.status_code, status.HTTP_404_NOT_FOUND)

        self.client.force_authenticate(user=self.teacher_user)
        teacher_res = self.client.post(
            f"/api/v1/teachers/{self.teacher.id}/reset_password/",
            {"username": "self_edit", "new_password": "password123"},
            format="json",
        )
        self.assertEqual(teacher_res.status_code, status.HTTP_403_FORBIDDEN)
