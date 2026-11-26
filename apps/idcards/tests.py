from io import BytesIO
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from PIL import Image, ImageDraw
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.idcards.models import IDCardTemplate
from apps.schools.models import School


class IDCardTemplateUploadTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_superuser(
            username='admin_tpl',
            email='admin_tpl@example.com',
            password='password123',
        )
        self.school = School.objects.create(name='Sardar Patel High School', code='SPH001')
        self.school_admin = User.objects.create_user(
            username='school_tpl',
            password='password123',
            role='school',
            school=self.school,
        )
        self.teacher = User.objects.create_user(
            username='teacher_tpl',
            password='password123',
            role='teacher',
            school=self.school,
        )

    def _make_sample_card_png(self):
        img = Image.new('RGB', (420, 640), '#ffffff')
        draw = ImageDraw.Draw(img)
        # Portrait photo frame rectangle
        draw.rectangle([125, 145, 295, 325], outline='#0ea5e9', width=3)
        draw.line([125, 145, 295, 325], fill='#64748b', width=1)
        draw.line([295, 145, 125, 325], fill='#64748b', width=1)
        # Labels mimicking printed Indian school ID cards
        draw.text((35, 360), 'Class -', fill='#7f1d1d')
        draw.text((225, 360), 'Roll No. -', fill='#7f1d1d')
        draw.text((35, 405), 'F.Name -', fill='#7f1d1d')
        draw.text((35, 445), 'D.O.B -', fill='#7f1d1d')
        draw.text((35, 485), 'Mob No. -', fill='#7f1d1d')
        draw.text((35, 525), 'Address -', fill='#7f1d1d')

        buf = BytesIO()
        img.save(buf, format='PNG')
        return SimpleUploadedFile('card_front.png', buf.getvalue(), content_type='image/png')

    def test_detect_fields_raster_png_and_svg(self):
        self.client.force_authenticate(user=self.admin)

        png_upload = self._make_sample_card_png()
        res_png = self.client.post(
            '/api/v1/idcards/templates/detect_fields/',
            {'file': png_upload},
            format='multipart',
        )
        self.assertEqual(res_png.status_code, status.HTTP_200_OK)
        self.assertEqual(res_png.data['fileType'], 'raster')
        self.assertEqual(res_png.data['layout'], 'vertical')
        self.assertIsNotNone(res_png.data['photoBox'])

        svg_bytes = (
            b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 340 520">'
            b'<text x="20" y="300">{{full_name}}</text></svg>'
        )
        svg_upload = SimpleUploadedFile('card_front.svg', svg_bytes, content_type='image/svg+xml')
        res_svg = self.client.post(
            '/api/v1/idcards/templates/detect_fields/',
            {'file': svg_upload},
            format='multipart',
        )
        self.assertEqual(res_svg.status_code, status.HTTP_200_OK)
        self.assertEqual(res_svg.data['fileType'], 'svg')
        self.assertEqual(res_svg.data['layout'], 'vertical')
        self.assertIn('{{full_name}}', res_svg.data['svgContent'])

    def test_create_update_and_clear_school_template_and_permissions(self):
        self.client.force_authenticate(user=self.school_admin)
        png_upload = self._make_sample_card_png()
        mappings = '{"front": {"aspectRatio": 0.656, "photoBox": {"xPct": 30, "yPct": 22, "widthPct": 40, "heightPct": 28}, "fields": [{"id": "f1", "fieldKey": "class_section", "label": "Class", "xPct": 24, "yPct": 56, "fontSizePct": 3.0}]}, "back": {"fields": []}}'

        create_res = self.client.post(
            '/api/v1/idcards/templates/',
            {
                'name': 'Sardar Patel Template',
                'layout': 'vertical',
                'is_default': 'true',
                'front_template': png_upload,
                'field_mappings': mappings,
            },
            format='multipart',
        )
        self.assertEqual(create_res.status_code, status.HTTP_201_CREATED, create_res.data)
        tpl_id = create_res.data['id']
        tpl = IDCardTemplate.objects.get(id=tpl_id)
        self.assertEqual(tpl.school_id, self.school.id)
        self.assertTrue(bool(tpl.front_template))
        self.assertEqual(tpl.field_mappings['front']['fields'][0]['fieldKey'], 'class_section')

        # Teacher can read their school template, cannot upload or detect
        self.client.force_authenticate(user=self.teacher)
        list_res = self.client.get(f'/api/v1/idcards/templates/?school_id={self.school.id}')
        self.assertEqual(list_res.status_code, status.HTTP_200_OK)
        rows = list_res.data['results'] if isinstance(list_res.data, dict) else list_res.data
        school_tpl_ids = [t['id'] for t in rows if t['school'] == self.school.id]
        self.assertEqual(school_tpl_ids, [tpl_id])
        forbidden_res = self.client.post('/api/v1/idcards/templates/detect_fields/', {}, format='multipart')
        self.assertEqual(forbidden_res.status_code, status.HTTP_403_FORBIDDEN)

        # School admin can clear uploaded front template
        self.client.force_authenticate(user=self.school_admin)
        patch_res = self.client.patch(
            f'/api/v1/idcards/templates/{tpl_id}/',
            {'clear_front_template': 'true'},
            format='multipart',
        )
        self.assertEqual(patch_res.status_code, status.HTTP_200_OK)
        tpl.refresh_from_db()
        self.assertFalse(bool(tpl.front_template))
