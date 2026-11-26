from django.db import models
from core.utils import student_photo_upload_path

class Student(models.Model):
    GENDER_CHOICES = (
        ('Male', 'Male'),
        ('Female', 'Female'),
        ('Other', 'Other'),
    )

    CARD_STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('printed', 'Printed'),
        ('delivered', 'Delivered'),
    )

    school = models.ForeignKey('schools.School', on_delete=models.CASCADE, related_name='students')
    admission_number = models.CharField(max_length=50)
    roll_number = models.CharField(max_length=20, blank=True, null=True)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100, blank=True, null=True)
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES, default='Male')
    dob = models.DateField(blank=True, null=True)
    blood_group = models.CharField(max_length=10, blank=True, null=True)
    father_name = models.CharField(max_length=150, blank=True, null=True)
    mother_name = models.CharField(max_length=150, blank=True, null=True)
    emergency_contact = models.CharField(max_length=20, blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    photo = models.ImageField(upload_to=student_photo_upload_path, blank=True, null=True)
    photo_number = models.CharField(max_length=50, blank=True, null=True)

    current_session = models.ForeignKey('academics.AcademicSession', on_delete=models.SET_NULL, null=True, blank=True, related_name='students')
    current_class = models.ForeignKey('academics.ClassLevel', on_delete=models.SET_NULL, null=True, blank=True, related_name='students')
    current_section = models.ForeignKey('academics.Section', on_delete=models.SET_NULL, null=True, blank=True, related_name='students')

    id_card_status = models.CharField(max_length=20, choices=CARD_STATUS_CHOICES, default='pending')
    extra_fields = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['current_class__order', 'current_section__name', 'roll_number', 'first_name']
        unique_together = ('school', 'admission_number')

    def __str__(self):
        return f"{self.first_name} {self.last_name or ''} ({self.admission_number})"

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name or ''}".strip()

class StudentSessionHistory(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='session_history')
    session = models.ForeignKey('academics.AcademicSession', on_delete=models.CASCADE)
    class_level = models.ForeignKey('academics.ClassLevel', on_delete=models.CASCADE)
    section = models.ForeignKey('academics.Section', on_delete=models.CASCADE)
    roll_number = models.CharField(max_length=20, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.student.full_name} - {self.session.name} - {self.class_level.name}"
