from django.test import TestCase
from django.core.files.uploadedfile import SimpleUploadedFile
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

    def test_enroll_requires_only_name_and_class(self):
        self.client.force_authenticate(user=self.user_a)

        # Missing class fails
        missing_class = self.client.post('/api/v1/students/', {'first_name': 'OnlyName'}, format='json')
        self.assertEqual(missing_class.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('current_class', missing_class.data)

        # Missing first_name fails
        missing_name = self.client.post('/api/v1/students/', {'current_class': self.class_a.id}, format='json')
        self.assertEqual(missing_name.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('first_name', missing_name.data)

        # Only first_name and current_class succeeds and auto-generates admission_number
        res = self.client.post('/api/v1/students/', {
            'first_name': 'Minimal',
            'current_class': self.class_a.id,
            'photo_number': 'PH-404',
        }, format='json')
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.data['first_name'], 'Minimal')
        self.assertEqual(res.data['current_class'], self.class_a.id)
        self.assertEqual(res.data['photo_number'], 'PH-404')
        self.assertTrue(bool(res.data['admission_number']))
        self.assertIsNone(res.data['current_section'])
        self.assertIsNone(res.data['current_session'])

        # Search by photo_number
        search_res = self.client.get('/api/v1/students/?search=PH-404')
        self.assertEqual(search_res.status_code, status.HTTP_200_OK)
        results = search_res.data.get('results', search_res.data)
        self.assertIn(res.data['id'], [s['id'] for s in results])

    def test_teacher_can_enroll_with_only_name_and_class_and_view_student(self):
        teacher_user = User.objects.create_user(
            username="teacher_enroll", email="te@alpha.com", password="password123", role="teacher", school=self.school_a
        )
        teacher_profile = Teacher.objects.create(
            user=teacher_user, school=self.school_a, employee_id="EMP-102"
        )
        self.section_a.teacher = teacher_profile
        self.section_a.save()

        self.client.force_authenticate(user=teacher_user)
        create_res = self.client.post('/api/v1/students/', {
            'first_name': 'Sectionless',
            'current_class': self.class_a.id,
        })
        self.assertEqual(create_res.status_code, status.HTTP_201_CREATED)

        list_res = self.client.get('/api/v1/students/')
        self.assertEqual(list_res.status_code, status.HTTP_200_OK)
        results = list_res.data.get('results', list_res.data)
        ids = [s['id'] for s in results]
        self.assertIn(create_res.data['id'], ids)

        # Patch with empty optional strings (simulating FormData edit) succeeds
        patch_res = self.client.patch(f"/api/v1/students/{create_res.data['id']}/", {
            'first_name': 'Sectionless Updated',
            'current_class': self.class_a.id,
            'dob': '',
            'current_section': '',
            'current_session': '',
        })
        self.assertEqual(patch_res.status_code, status.HTTP_200_OK)
        self.assertEqual(patch_res.data['first_name'], 'Sectionless Updated')

    def test_bulk_photo_import_matches_by_photo_number(self):
        admin_user = User.objects.create_superuser(
            username="super_photo", email="sp@example.com", password="password123", role="admin"
        )
        self.student_a.photo_number = "PH-101"
        self.student_a.save(update_fields=['photo_number'])
        self.student_b.photo_number = "PH-101"
        self.student_b.save(update_fields=['photo_number'])

        # 1x1 valid minimal PNG bytes
        png_bytes = (
            b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01'
            b'\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc`\x00\x00'
            b'\x00\x02\x00\x01H\xaf\xa4q\x00\x00\x00\x00IEND\xaeB`\x82'
        )
        matched_file = SimpleUploadedFile("ph-101.png", png_bytes, content_type="image/png")
        unmatched_file = SimpleUploadedFile("999.png", png_bytes, content_type="image/png")

        self.client.force_authenticate(user=admin_user)
        res = self.client.post(
            '/api/v1/students/bulk_photo_import/',
            {
                'school_id': self.school_a.id,
                'photos': [matched_file, unmatched_file],
            },
            format='multipart',
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['updated_count'], 1)
        self.assertEqual(res.data['matched_count'], 1)
        self.assertEqual(res.data['unmatched_count'], 1)

        self.student_a.refresh_from_db()
        self.student_b.refresh_from_db()
        self.assertTrue(bool(self.student_a.photo))
        # Ensure School B student with same photo_number was NOT touched
        self.assertFalse(bool(self.student_b.photo))

        # Clean up uploaded test file
        if self.student_a.photo:
            self.student_a.photo.delete(save=False)

    def test_bulk_import_saves_photo_number_column(self):
        self.client.force_authenticate(user=self.user_a)
        res = self.client.post(
            '/api/v1/students/bulk_import/',
            {
                'students': [
                    {
                        'first_name': 'Kavya',
                        'class_name': 'Class 10',
                        'section_name': 'A',
                        'admission_number': 'ADM-PHOTO-1',
                        'photo_number': 'CAM-77',
                    }
                ]
            },
            format='json',
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        created = Student.objects.get(school=self.school_a, admission_number='ADM-PHOTO-1')
        self.assertEqual(created.photo_number, 'CAM-77')

    def test_super_admin_can_edit_student_details(self):
        admin_user = User.objects.create_superuser(
            username="super_editor", email="se@example.com", password="password123", role="admin"
        )
        self.client.force_authenticate(user=admin_user)
        res = self.client.patch(
            f"/api/v1/students/{self.student_a.id}/",
            {
                'first_name': 'Rohan Updated',
                'roll_number': '10',
                'photo_number': 'PH-99',
                'father_name': 'Manoj Sharma',
                'dob': '',
            },
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.student_a.refresh_from_db()
        self.assertEqual(self.student_a.first_name, 'Rohan Updated')
        self.assertEqual(self.student_a.roll_number, '10')
        self.assertEqual(self.student_a.photo_number, 'PH-99')
        self.assertEqual(self.student_a.father_name, 'Manoj Sharma')
