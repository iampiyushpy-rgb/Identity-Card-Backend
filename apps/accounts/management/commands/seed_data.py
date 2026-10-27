import datetime
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from apps.schools.models import School
from apps.academics.models import AcademicSession, ClassLevel, Section
from apps.teachers.models import Teacher
from apps.students.models import Student, StudentSessionHistory
from apps.payments.models import Payment
from apps.idcards.models import IDCardTemplate

User = get_user_model()

class Command(BaseCommand):
    help = 'Seeds initial demo data for Super Admin, School, Teachers, Academics, and Students.'

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.NOTICE("Starting database seeding..."))

        # 1. Super Admin
        super_admin, created = User.objects.get_or_create(
            username='admin',
            defaults={
                'email': 'admin@techravisha.com',
                'first_name': 'Super',
                'last_name': 'Admin',
                'role': 'admin',
                'is_staff': True,
                'is_superuser': True,
            }
        )
        if created or not super_admin.check_password('admin123'):
            super_admin.set_password('admin123')
            super_admin.role = 'admin'
            super_admin.is_staff = True
            super_admin.is_superuser = True
            super_admin.save()
        self.stdout.write(self.style.SUCCESS(f"Super Admin ready: admin / admin123"))

        # 2. School
        school, _ = School.objects.get_or_create(
            code='SCH001',
            defaults={
                'name': "St. Xavier's International Academy",
                'affiliation_number': 'CBSE-983214',
                'address': 'Plot 45, Knowledge Park III, Silicon Expressway',
                'city': 'New Delhi',
                'state': 'Delhi NCR',
                'postal_code': '110001',
                'phone': '+91 98765 43210',
                'email': 'principal@stxaviers.edu',
                'website': 'https://stxaviers.edu',
                'principal_name': 'Dr. Robert Vance',
                'status': 'active',
                'subscription_plan': 'premium',
                'card_price': 60.00
            }
        )
        self.stdout.write(self.style.SUCCESS(f"School ready: {school.name}"))

        # 3. School Admin User
        school_admin, s_created = User.objects.get_or_create(
            username='school_sch001',
            defaults={
                'email': 'admin@stxaviers.edu',
                'first_name': 'Dr. Robert',
                'last_name': 'Vance',
                'role': 'school',
                'school': school
            }
        )
        if s_created or not school_admin.check_password('school123'):
            school_admin.set_password('school123')
            school_admin.role = 'school'
            school_admin.school = school
            school_admin.save()
        self.stdout.write(self.style.SUCCESS(f"School Admin ready: school_sch001 / school123"))

        # 4. Academic Session
        session, _ = AcademicSession.objects.get_or_create(
            school=school,
            name='2025-2026',
            defaults={
                'is_active': True,
                'start_date': datetime.date(2025, 4, 1),
                'end_date': datetime.date(2026, 3, 31)
            }
        )

        # 5. Classes & Sections
        classes_data = [
            ("Class 9", 1),
            ("Class 10", 2),
            ("Class 11", 3),
            ("Class 12", 4),
        ]
        created_classes = {}
        created_sections = {}

        for c_name, order in classes_data:
            cl, _ = ClassLevel.objects.get_or_create(
                school=school,
                name=c_name,
                defaults={'order': order}
            )
            created_classes[c_name] = cl
            for sec_name in ['A', 'B']:
                sec, _ = Section.objects.get_or_create(
                    school=school,
                    class_level=cl,
                    name=sec_name
                )
                created_sections[f"{c_name}-{sec_name}"] = sec

        # 6. Teachers
        teachers_data = [
            ('teacher_sarah', 'sarah.jenkins@stxaviers.edu', 'Sarah', 'Jenkins', 'EMP-0101', 'Senior Faculty', 'M.Sc Mathematics', '+91 91234 56789', 'Class 10-A'),
            ('teacher_alan', 'alan.turing@stxaviers.edu', 'Alan', 'Turing', 'EMP-0102', 'Head of Dept', 'M.Tech Computer Science', '+91 92345 67890', 'Class 10-B'),
        ]

        for uname, email, fname, lname, empid, desig, qual, phone, assign_sec_key in teachers_data:
            t_user, _ = User.objects.get_or_create(
                username=uname,
                defaults={
                    'email': email,
                    'first_name': fname,
                    'last_name': lname,
                    'role': 'teacher',
                    'school': school
                }
            )
            t_user.set_password('teacher123')
            t_user.role = 'teacher'
            t_user.school = school
            t_user.save()

            teacher, _ = Teacher.objects.get_or_create(
                user=t_user,
                school=school,
                defaults={
                    'employee_id': empid,
                    'designation': desig,
                    'qualification': qual,
                    'phone': phone,
                    'is_active': True
                }
            )
            if assign_sec_key in created_sections:
                sec = created_sections[assign_sec_key]
                sec.teacher = teacher
                sec.save()

        self.stdout.write(self.style.SUCCESS("Teachers ready: teacher_sarah / teacher123, teacher_alan / teacher123"))

        # 7. Students
        sample_students = [
            ('ADM-2025-001', '101', 'Aarav', 'Sharma', 'Male', '2010-05-14', 'O+', 'Vikram Sharma', 'Pooja Sharma', '+91 98111 22233', '402, Lotus Towers, Mayur Vihar, Delhi', 'Class 10', 'A', 'pending'),
            ('ADM-2025-002', '102', 'Diya', 'Patel', 'Female', '2010-08-22', 'B+', 'Ketan Patel', 'Bhavna Patel', '+91 98222 33344', '12, Sunrise Residency, Noida Sec 62', 'Class 10', 'A', 'printed'),
            ('ADM-2025-003', '103', 'Kabir', 'Mehta', 'Male', '2010-02-18', 'A+', 'Sunil Mehta', 'Geeta Mehta', '+91 98333 44455', 'A-89, Green Park, South Delhi', 'Class 10', 'A', 'pending'),
            ('ADM-2025-004', '104', 'Ananya', 'Iyer', 'Female', '2010-11-05', 'AB+', 'Raman Iyer', 'Lakshmi Iyer', '+91 98444 55566', 'C-104, Palm Greens, Gurugram', 'Class 10', 'B', 'delivered'),
            ('ADM-2025-005', '105', 'Rohan', 'Verma', 'Male', '2010-09-30', 'O-', 'Rajesh Verma', 'Suman Verma', '+91 98555 66677', 'Flat 5B, Golf View Apartments, Noida', 'Class 10', 'B', 'printed'),
            ('ADM-2025-006', '901', 'Ishaan', 'Gupta', 'Male', '2011-04-12', 'B-', 'Manoj Gupta', 'Renu Gupta', '+91 98666 77788', '77, Vasant Kunj Enclave, New Delhi', 'Class 9', 'A', 'pending'),
            ('ADM-2025-007', '902', 'Meera', 'Nair', 'Female', '2011-07-19', 'A-', 'Unni Nair', 'Sindhu Nair', '+91 98777 88899', 'Tower 3, Supertech Capetown, Noida', 'Class 9', 'A', 'pending'),
        ]

        for adm, roll, fname, lname, gender, dob, bg, fat, mot, phone, addr, c_name, s_name, card_st in sample_students:
            cl = created_classes[c_name]
            sec = created_sections[f"{c_name}-{s_name}"]
            student, _ = Student.objects.get_or_create(
                school=school,
                admission_number=adm,
                defaults={
                    'roll_number': roll,
                    'first_name': fname,
                    'last_name': lname,
                    'gender': gender,
                    'dob': dob,
                    'blood_group': bg,
                    'father_name': fat,
                    'mother_name': mot,
                    'emergency_contact': phone,
                    'address': addr,
                    'current_session': session,
                    'current_class': cl,
                    'current_section': sec,
                    'id_card_status': card_st
                }
            )
            StudentSessionHistory.objects.get_or_create(
                student=student,
                session=session,
                class_level=cl,
                section=sec,
                defaults={'roll_number': roll}
            )

        self.stdout.write(self.style.SUCCESS(f"Created {len(sample_students)} sample students."))

        # 8. Templates
        IDCardTemplate.objects.get_or_create(
            name="Modern Indigo Elite",
            school=school,
            defaults={
                'layout': 'vertical',
                'primary_color': '#4f46e5',
                'secondary_color': '#06b6d4',
                'header_background': '#1e1b4b',
                'show_blood_group': True,
                'show_emergency_contact': True,
                'show_barcode': True,
                'show_address': True,
                'is_default': True
            }
        )
        IDCardTemplate.objects.get_or_create(
            name="Classic Emerald Accent",
            school=school,
            defaults={
                'layout': 'vertical',
                'primary_color': '#059669',
                'secondary_color': '#10b981',
                'header_background': '#064e3b',
                'show_blood_group': True,
                'show_emergency_contact': True,
                'show_barcode': True,
                'show_address': True,
                'is_default': False
            }
        )

        # 9. Payment Record
        Payment.objects.get_or_create(
            receipt_number='REC-2025-001',
            defaults={
                'school': school,
                'amount': 18000.00,
                'payment_date': datetime.date(2025, 4, 15),
                'transaction_id': 'TXN-9842105432',
                'payment_mode': 'UPI',
                'status': 'completed',
                'description': 'Payment for 300 Smart RFID ID Cards batch'
            }
        )

        self.stdout.write(self.style.SUCCESS("All seed data created successfully!"))
