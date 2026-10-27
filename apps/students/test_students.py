from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
from apps.schools.models import School
from apps.academics.models import AcademicSession, ClassLevel, Section
from apps.students.models import Student
from apps.teachers.models import Teacher

User = get_user_model()

class StudentMultiTenancyTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        # School A
        self.school_a = School.objects.create(name="School Alpha", code="ALPHA")
        self.user_a = User.objects.create_user(
            username="admin_a", email="a@alpha.com", password="password123", role="school", school=self.school_a
        )
        self.session_a = AcademicSession.objects.create(school=self.school_a, name="2025-2026")
        self.class_a = ClassLevel.objects.create(school=self.school_a, name="Class 10")
        self.section_a = Section.objects.create(school=self.school_a, class_level=self.class_a, name="A")

        self.student_a = Student.objects.create(
            school=self.school_a,
            admission_number="ADM-001",
            roll_number="1",
            first_name="Rohan",
            last_name="Sharma",
            current_session=self.session_a,
            current_class=self.class_a,
            current_section=self.section_a
        )

        # School B
        self.school_b = School.objects.create(name="School Beta", code="BETA")
        self.user_b = User.objects.create_user(
            username="admin_b", email="b@beta.com", password="password123", role="school", school=self.school_b
        )
        self.session_b = AcademicSession.objects.create(school=self.school_b, name="2025-2026")
        self.class_b = ClassLevel.objects.create(school=self.school_b, name="Class 10")
        self.section_b = Section.objects.create(school=self.school_b, class_level=self.class_b, name="B")

        self.student_b = Student.objects.create(
            school=self.school_b,
            admission_number="ADM-002",
            roll_number="2",
            first_name="Priya",
            last_name="Verma",
            current_session=self.session_b,
            current_class=self.class_b,
            current_section=self.section_b
        )

    def test_school_a_cannot_view_school_b_students(self):
        self.client.force_authenticate(user=self.user_a)
        res = self.client.get('/api/v1/students/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        results = res.data.get('results', res.data)
        ids = [s['id'] for s in results]
        self.assertIn(self.student_a.id, ids)
        self.assertNotIn(self.student_b.id, ids)

    def test_school_a_cannot_retrieve_school_b_student_detail(self):
        self.client.force_authenticate(user=self.user_a)
        res = self.client.get(f'/api/v1/students/{self.student_b.id}/')
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    def test_cross_school_session_change_is_forbidden(self):
        self.client.force_authenticate(user=self.user_a)
        res = self.client.post('/api/v1/students/change_session/', {
            'student_ids': [self.student_a.id],
            'target_session_id': self.session_b.id, # from School B
            'target_class_id': self.class_b.id,
            'target_section_id': self.section_b.id,
        })
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_teacher_only_sees_assigned_section_students(self):
        # Create teacher in School A assigned to Section A
        teacher_user = User.objects.create_user(
            username="teacher_a", email="t@alpha.com", password="password123", role="teacher", school=self.school_a
        )
        teacher_profile = Teacher.objects.create(
            user=teacher_user, school=self.school_a, employee_id="EMP-101"
        )
        self.section_a.teacher = teacher_profile
        self.section_a.save()

        # Create another section and student in School A not assigned to teacher
        sec_other = Section.objects.create(school=self.school_a, class_level=self.class_a, name="Other")
        student_other = Student.objects.create(
            school=self.school_a,
            admission_number="ADM-003",
            roll_number="3",
            first_name="Amit",
            current_session=self.session_a,
            current_class=self.class_a,
            current_section=sec_other
        )

        self.client.force_authenticate(user=teacher_user)
        res = self.client.get('/api/v1/students/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        results = res.data.get('results', res.data)
        ids = [s['id'] for s in results]
        self.assertIn(self.student_a.id, ids)
        self.assertNotIn(student_other.id, ids)
