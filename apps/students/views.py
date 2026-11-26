import os
import re
import json
import uuid
import datetime
from django.core.files.base import ContentFile
from django.db import transaction
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from django.db.models import Q
from django.shortcuts import get_object_or_404
from .models import Student, StudentSessionHistory
from .serializers import StudentSerializer, SessionChangeSerializer
from apps.schools.models import School
from apps.academics.models import AcademicSession, ClassLevel, Section
from core.permissions import IsSchoolOrTeacher, IsSchoolAdmin

class OptionalStudentPagination(PageNumberPagination):
    page_size = 50
    page_size_query_param = 'page_size'
    max_page_size = 5000

    def paginate_queryset(self, queryset, request, view=None):
        # Allow disabling pagination when requesting all records (e.g. for complete roster view)
        if (
            request.query_params.get('no_page') == 'true'
            or request.query_params.get('all') == 'true'
            or request.query_params.get('page_size') == 'all'
        ):
            return None
        return super().paginate_queryset(queryset, request, view=view)

class StudentViewSet(viewsets.ModelViewSet):
    serializer_class = StudentSerializer
    pagination_class = OptionalStudentPagination
    permission_classes = [IsSchoolOrTeacher]

    def get_queryset(self):
        user = self.request.user
        qs = Student.objects.select_related(
            'school', 'current_session', 'current_class', 'current_section'
        ).prefetch_related('session_history')

        if user.is_superuser or user.role == 'admin':
            school_id = self.request.query_params.get('school_id')
            if school_id:
                qs = qs.filter(school_id=school_id)
        elif user.role == 'school' and user.school:
            qs = qs.filter(school=user.school)
        elif user.role == 'teacher' and user.school:
            if hasattr(user, 'teacher_profile'):
                assigned_sections = user.teacher_profile.assigned_sections.all()
                assigned_section_ids = list(assigned_sections.values_list('id', flat=True))
                assigned_class_ids = list(assigned_sections.values_list('class_level_id', flat=True))
                qs = qs.filter(school=user.school).filter(
                    Q(current_section_id__in=assigned_section_ids) |
                    Q(current_section__isnull=True, current_class_id__in=assigned_class_ids)
                )
            else:
                return Student.objects.none()
        elif user.school:
            qs = qs.filter(school=user.school)
        else:
            return Student.objects.none()

        # Query Filters
        class_id = self.request.query_params.get('class_id')
        if class_id:
            qs = qs.filter(current_class_id=class_id)

        section_id = self.request.query_params.get('section_id')
        if section_id:
            qs = qs.filter(current_section_id=section_id)

        session_id = self.request.query_params.get('session_id')
        if session_id:
            qs = qs.filter(current_session_id=session_id)

        card_status = self.request.query_params.get('id_card_status')
        if card_status:
            qs = qs.filter(id_card_status=card_status)

        search = self.request.query_params.get('search')
        if search:
            qs = qs.filter(
                Q(first_name__icontains=search) |
                Q(last_name__icontains=search) |
                Q(admission_number__icontains=search) |
                Q(roll_number__icontains=search) |
                Q(photo_number__icontains=search) |
                Q(father_name__icontains=search)
            )

        return qs

    @action(detail=False, methods=['post'], permission_classes=[IsSchoolAdmin])
    def change_session(self, request):
        """Promote or transfer selected students to a new session/class/section."""
        serializer = SessionChangeSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        student_ids = serializer.validated_data['student_ids']
        target_session = get_object_or_404(AcademicSession, id=serializer.validated_data['target_session_id'])
        target_class = get_object_or_404(ClassLevel, id=serializer.validated_data['target_class_id'])
        target_section = get_object_or_404(Section, id=serializer.validated_data['target_section_id'])

        user = request.user
        school = user.school if hasattr(user, 'school') and user.school else None

        # Cross-school security check
        if school and not (user.is_superuser or user.role == 'admin'):
            if target_session.school_id != school.id or target_class.school_id != school.id or target_section.class_level.school_id != school.id:
                return Response({"detail": "Target academic session, class, or section does not belong to your school."}, status=status.HTTP_403_FORBIDDEN)

        # Integrity check: target section must belong to target class
        if target_section.class_level_id != target_class.id:
            return Response({"detail": f"Section '{target_section.name}' does not belong to class '{target_class.name}'."}, status=status.HTTP_400_BAD_REQUEST)

        students = self.get_queryset().filter(id__in=student_ids)
        updated_count = 0

        for student in students:
            # Update student record
            student.current_session = target_session
            student.current_class = target_class
            student.current_section = target_section
            student.id_card_status = 'pending'  # new card needed for new session
            student.save()

            # Record session history
            StudentSessionHistory.objects.create(
                student=student,
                session=target_session,
                class_level=target_class,
                section=target_section,
                roll_number=student.roll_number
            )
            updated_count += 1

        return Response({
            "message": f"Successfully updated session for {updated_count} students.",
            "updated_count": updated_count
        })

    @action(detail=False, methods=['post'])
    def bulk_status_update(self, request):
        """Update ID card status (e.g. mark printed/delivered) for multiple students."""
        student_ids = request.data.get('student_ids', [])
        new_status = request.data.get('status', 'printed')
        if new_status not in ['pending', 'approved', 'printed', 'delivered']:
            return Response({"error": "Invalid status."}, status=status.HTTP_400_BAD_REQUEST)

        students = self.get_queryset().filter(id__in=student_ids)
        count = students.update(id_card_status=new_status)
        return Response({"message": f"Updated {count} student ID card statuses to '{new_status}'."})

    @action(detail=False, methods=['post'], permission_classes=[IsSchoolAdmin])
    def bulk_import(self, request):
        """
        Bulk import students from Excel / JSON rows.
        Automatically handles:
        - Class-wise grouping
        - Auto-creating classes (ClassLevel) if missing
        - Auto-creating sections (Section) if missing
        - Storing extra custom columns into extra_fields JSONField
        """
        user = request.user
        school_id = request.data.get('school_id')

        # Determine target school
        if user.is_superuser or user.role == 'admin':
            if not school_id:
                return Response({"detail": "school_id is required for admin import."}, status=status.HTTP_400_BAD_REQUEST)
            school = get_object_or_404(School, id=school_id)
        elif user.role == 'school' and user.school:
            school = user.school
        else:
            return Response({"detail": "Permission denied: no associated school found."}, status=status.HTTP_403_FORBIDDEN)

        students_data = request.data.get('students', [])
        if not students_data or not isinstance(students_data, list):
            return Response({"detail": "Invalid or empty students list provided."}, status=status.HTTP_400_BAD_REQUEST)

        # Get or create active academic session for this school
        active_session = AcademicSession.objects.filter(school=school, is_active=True).first()
        if not active_session:
            active_session = AcademicSession.objects.filter(school=school).first()
            if not active_session:
                active_session = AcademicSession.objects.create(
                    school=school,
                    name="2025-2026",
                    is_active=True
                )

        # Pre-cache existing classes and sections for this school
        existing_classes = {c.name.strip().lower(): c for c in ClassLevel.objects.filter(school=school)}
        existing_sections = {(s.class_level_id, s.name.strip().lower()): s for s in Section.objects.filter(school=school)}

        classes_created_count = 0
        sections_created_count = 0
        students_imported_count = 0
        students_updated_count = 0
        all_extra_fields_detected = set()
        classes_affected = set()

        def parse_class_order(name):
            digits = re.findall(r'\d+', str(name))
            if digits:
                return int(digits[0])
            name_lower = str(name).lower()
            if 'nur' in name_lower or 'pg' in name_lower:
                return 0
            if 'lkg' in name_lower or 'kg1' in name_lower:
                return 1
            if 'ukg' in name_lower or 'kg2' in name_lower:
                return 2
            return len(existing_classes) + 1

        standard_keys = {
            'class_name', 'class', 'grade', 'standard', 'std',
            'section_name', 'section', 'sec',
            'first_name', 'last_name', 'full_name', 'name', 'student_name', 'student',
            'admission_number', 'admission_no', 'adm_no', 'adm no', 'admission',
            'roll_number', 'roll_no', 'roll', 'roll no', 'roll no.',
            'gender', 'sex',
            'dob', 'date_of_birth', 'd.o.b', 'd.o.b.', 'date of birth', 'birth date',
            'blood_group', 'blood', 'blood group', 'b.g',
            'father_name', "father's_name", "father's name", 'father', 'f name', 'f_name', 'f.name', 'fname',
            'mother_name', "mother's_name", "mother's name", 'mother', 'm name', 'm_name', 'm.name', 'mname',
            'emergency_contact', 'phone', 'mobile', 'contact', 'mob no', 'mob. no', 'mob no.', 'mobile no', 'phone no', 'contact no', 'mob',
            'address', 'extra_fields', 'id', 'photo',
            'photo_number', 'photo_no', 'photo no', 'photo no.', 'photo number'
        }

        with transaction.atomic():
            for idx, item in enumerate(students_data):
                # 1. Resolve Class
                raw_class_name = str(item.get('class_name') or item.get('class') or item.get('grade') or 'Class 1').strip()
                if not raw_class_name:
                    raw_class_name = 'Class 1'

                class_key = raw_class_name.lower()
                class_obj = existing_classes.get(class_key)
                if not class_obj:
                    # Auto-create class!
                    order = parse_class_order(raw_class_name)
                    class_obj = ClassLevel.objects.create(
                        school=school,
                        name=raw_class_name,
                        order=order
                    )
                    existing_classes[class_key] = class_obj
                    classes_created_count += 1

                classes_affected.add(class_obj.name)

                # 2. Resolve Section
                raw_section_name = str(item.get('section_name') or item.get('section') or item.get('sec') or 'A').strip().upper()
                if not raw_section_name:
                    raw_section_name = 'A'

                section_key = (class_obj.id, raw_section_name.lower())
                section_obj = existing_sections.get(section_key)
                if not section_obj:
                    # Auto-create section!
                    section_obj = Section.objects.create(
                        school=school,
                        class_level=class_obj,
                        name=raw_section_name
                    )
                    existing_sections[section_key] = section_obj
                    sections_created_count += 1

                # 3. Resolve Student Name
                first_name = str(item.get('first_name') or '').strip()
                last_name = str(item.get('last_name') or '').strip()
                full_name = str(item.get('full_name') or item.get('name') or item.get('student_name') or '').strip()

                if not first_name and full_name:
                    parts = full_name.split(None, 1)
                    first_name = parts[0]
                    last_name = parts[1] if len(parts) > 1 else ''
                elif not first_name:
                    first_name = f"Student {idx + 1}"

                # 4. Roll number
                roll_no = str(item.get('roll_number') or item.get('roll_no') or item.get('roll') or item.get('roll no') or item.get('roll no.') or '').strip() or None

                # 5. Resolve Admission Number & Match Existing Student to Prevent Duplicates
                adm_no = str(item.get('admission_number') or item.get('admission_no') or item.get('adm_no') or item.get('adm no') or '').strip()

                existing_student = None
                if adm_no:
                    existing_student = Student.objects.filter(school=school, admission_number=adm_no).first()
                else:
                    # Match by class + roll_number if roll_number is provided
                    if roll_no:
                        existing_student = Student.objects.filter(school=school, current_class=class_obj, roll_number=roll_no).first()
                    # If still not found, match by class + student name
                    if not existing_student and first_name:
                        existing_student = Student.objects.filter(
                            school=school,
                            current_class=class_obj,
                            first_name__iexact=first_name,
                            last_name__iexact=last_name
                        ).first()

                if existing_student:
                    adm_no = existing_student.admission_number
                elif not adm_no:
                    adm_prefix = f"ADM-{school.code or 'SCH'}-{active_session.name[:4]}"
                    adm_no = f"{adm_prefix}-{class_obj.id:02d}-{idx + 1:04d}"
                    while Student.objects.filter(school=school, admission_number=adm_no).exists():
                        adm_no = f"{adm_prefix}-{uuid.uuid4().hex[:6].upper()}"

                # 6. Gender
                gender_raw = str(item.get('gender') or item.get('sex') or 'Male').strip().lower()
                if gender_raw in ['f', 'female', 'girl', 'woman']:
                    gender = 'Female'
                elif gender_raw in ['m', 'male', 'boy', 'man']:
                    gender = 'Male'
                else:
                    gender = 'Other'

                # 7. DOB
                dob = None
                raw_dob = item.get('dob') or item.get('date_of_birth') or item.get('d.o.b') or item.get('d.o.b.') or item.get('date of birth')
                if raw_dob:
                    if isinstance(raw_dob, (datetime.date, datetime.datetime)):
                        dob = raw_dob.date() if isinstance(raw_dob, datetime.datetime) else raw_dob
                    elif isinstance(raw_dob, str):
                        for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y', '%m/%d/%Y'):
                            try:
                                dob = datetime.datetime.strptime(raw_dob.strip(), fmt).date()
                                break
                            except ValueError:
                                pass

                # 8. Blood group
                blood_group = str(item.get('blood_group') or item.get('blood') or item.get('blood group') or item.get('b.g') or '').strip().upper() or None

                # 9. Other standard fields
                father_name = str(item.get('father_name') or item.get("father's_name") or item.get("father's name") or item.get('father') or item.get('f name') or item.get('f_name') or item.get('f.name') or item.get('fname') or '').strip() or None
                mother_name = str(item.get('mother_name') or item.get("mother's_name") or item.get("mother's name") or item.get('mother') or item.get('m name') or item.get('m_name') or item.get('m.name') or item.get('mname') or '').strip() or None
                emergency_contact = str(item.get('emergency_contact') or item.get('phone') or item.get('mobile') or item.get('contact') or item.get('mob no') or item.get('mob. no') or item.get('mob no.') or item.get('mobile no') or item.get('phone no') or item.get('mob') or '').strip() or None
                address = str(item.get('address') or '').strip() or None
                photo_number = str(item.get('photo_number') or item.get('photo_no') or item.get('photo no') or item.get('photo no.') or item.get('photo number') or '').strip() or None
                if not photo_number:
                    raw_photo_val = str(item.get('photo') or '').strip()
                    if raw_photo_val and not raw_photo_val.lower().startswith(('http://', 'https://', 'data:', '/media/')):
                        photo_number = raw_photo_val

                # 10. Extra Fields
                extra_fields = dict(item.get('extra_fields') or {})
                for k, v in item.items():
                    norm_k = str(k).strip()
                    if norm_k.lower() not in standard_keys and v is not None and str(v).strip() != '':
                        extra_fields[norm_k] = str(v).strip()
                        all_extra_fields_detected.add(norm_k)

                for ek in extra_fields.keys():
                    all_extra_fields_detected.add(ek)

                # 11. Create or update student
                student_obj, created = Student.objects.update_or_create(
                    school=school,
                    admission_number=adm_no,
                    defaults={
                        'roll_number': roll_no,
                        'first_name': first_name,
                        'last_name': last_name,
                        'gender': gender,
                        'dob': dob,
                        'blood_group': blood_group,
                        'father_name': father_name,
                        'mother_name': mother_name,
                        'emergency_contact': emergency_contact,
                        'address': address,
                        'photo_number': photo_number,
                        'current_session': active_session,
                        'current_class': class_obj,
                        'current_section': section_obj,
                        'extra_fields': extra_fields,
                        'id_card_status': 'pending',
                        'is_active': True,
                    }
                )

                # Record history
                StudentSessionHistory.objects.update_or_create(
                    student=student_obj,
                    session=active_session,
                    defaults={
                        'class_level': class_obj,
                        'section': section_obj,
                        'roll_number': roll_no
                    }
                )

                if created:
                    students_imported_count += 1
                else:
                    students_updated_count += 1

        return Response({
            "success": True,
            "message": f"Successfully processed {len(students_data)} students ({students_imported_count} new, {students_updated_count} updated).",
            "total_processed": len(students_data),
            "students_created": students_imported_count,
            "students_updated": students_updated_count,
            "classes_created": classes_created_count,
            "sections_created": sections_created_count,
            "classes_affected": list(classes_affected),
            "extra_fields_detected": list(all_extra_fields_detected),
        }, status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'], permission_classes=[IsSchoolAdmin])
    def bulk_photo_import(self, request):
        """
        Bulk upload student photos and automatically match them to students by photo_number
        (from uploaded filename stem or explicit mapping).
        """
        user = request.user
        school_id = request.data.get('school_id')

        if user.is_superuser or user.role == 'admin':
            if not school_id:
                return Response({"detail": "school_id is required for admin photo import."}, status=status.HTTP_400_BAD_REQUEST)
            school = get_object_or_404(School, id=school_id)
        elif user.role == 'school' and user.school:
            school = user.school
        else:
            return Response({"detail": "Permission denied: no associated school found."}, status=status.HTTP_403_FORBIDDEN)

        photos = request.FILES.getlist('photos')
        if not photos:
            return Response({"detail": "No image files were provided."}, status=status.HTTP_400_BAD_REQUEST)

        # Optional per-file mapping JSON: [{"index": 0, "student_id": 12, "photo_number": "PH-101"}, ...]
        mapping_by_index = {}
        raw_mappings = request.data.get('mappings')
        if raw_mappings:
            try:
                parsed = json.loads(raw_mappings) if isinstance(raw_mappings, str) else raw_mappings
                if isinstance(parsed, list):
                    for entry in parsed:
                        if isinstance(entry, dict) and 'index' in entry:
                            mapping_by_index[int(entry['index'])] = entry
            except (ValueError, TypeError):
                return Response({"detail": "Invalid mappings payload."}, status=status.HTTP_400_BAD_REQUEST)

        def normalize_code(val):
            return re.sub(r'[^a-z0-9]', '', str(val or '').strip().lower())

        school_students = list(
            Student.objects.filter(school=school).select_related('current_class', 'current_section')
        )
        students_by_id = {s.id: s for s in school_students}

        exact_map = {}
        norm_map = {}
        for s in school_students:
            pn = (s.photo_number or '').strip()
            if not pn:
                continue
            exact_key = pn.lower()
            exact_map.setdefault(exact_key, []).append(s)
            norm_key = normalize_code(pn)
            if norm_key:
                norm_map.setdefault(norm_key, []).append(s)

        allowed_exts = {'.jpg', '.jpeg', '.png', '.webp', '.gif', '.bmp'}
        matched_results = []
        unmatched_results = []
        updated_student_ids = set()

        for idx, photo_file in enumerate(photos):
            orig_name = photo_file.name or ''
            stem, ext = os.path.splitext(os.path.basename(orig_name))
            ext_lower = ext.lower()
            content_type = (getattr(photo_file, 'content_type', '') or '').lower()

            if ext_lower not in allowed_exts and not content_type.startswith('image/'):
                unmatched_results.append({
                    "filename": orig_name,
                    "photo_number": stem.strip(),
                    "reason": "Unsupported file type (must be an image).",
                })
                continue

            entry = mapping_by_index.get(idx, {})
            explicit_student_id = entry.get('student_id')
            lookup_pn = str(entry.get('photo_number') or stem).strip()

            targets = []
            if explicit_student_id:
                try:
                    student_obj = students_by_id.get(int(explicit_student_id))
                    if student_obj:
                        targets = [student_obj]
                except (ValueError, TypeError):
                    pass

            if not targets and lookup_pn:
                targets = exact_map.get(lookup_pn.lower(), [])
                if not targets:
                    norm_lookup = normalize_code(lookup_pn)
                    if norm_lookup:
                        targets = norm_map.get(norm_lookup, [])

            if not targets:
                unmatched_results.append({
                    "filename": orig_name,
                    "photo_number": lookup_pn,
                    "reason": f"No student matched Photo No. '{lookup_pn}'.",
                })
                continue

            photo_file.seek(0)
            raw_bytes = photo_file.read()
            save_name = os.path.basename(orig_name) or f"photo_{idx}.jpg"
            if '.' not in save_name:
                save_name = f"{save_name}.jpg"

            for student_obj in targets:
                student_obj.photo.save(save_name, ContentFile(raw_bytes), save=True)
                updated_student_ids.add(student_obj.id)
                matched_results.append({
                    "filename": orig_name,
                    "photo_number": student_obj.photo_number or lookup_pn,
                    "student_id": student_obj.id,
                    "student_name": student_obj.full_name,
                    "admission_number": student_obj.admission_number,
                    "photo_url": request.build_absolute_uri(student_obj.photo.url) if student_obj.photo else None,
                })

        return Response({
            "success": True,
            "message": f"Updated profile photos for {len(updated_student_ids)} student(s).",
            "updated_count": len(updated_student_ids),
            "matched_count": len(matched_results),
            "unmatched_count": len(unmatched_results),
            "matched": matched_results,
            "unmatched": unmatched_results,
        }, status=status.HTTP_200_OK)
