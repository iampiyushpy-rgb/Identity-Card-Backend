from django.db import models
from django.contrib.auth.models import AbstractUser

class User(AbstractUser):
    ROLE_CHOICES = (
        ('admin', 'Super Admin'),
        ('school', 'School Admin'),
        ('teacher', 'Teacher'),
    )

    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='admin')
    phone = models.CharField(max_length=20, blank=True, null=True)
    school = models.ForeignKey(
        'schools.School',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='users'
    )
    avatar = models.ImageField(upload_to='avatars/', null=True, blank=True)
    raw_password = models.CharField(max_length=128, blank=True, null=True, default='')

    def is_super_admin(self):
        return self.role == 'admin' or self.is_superuser

    def is_school_admin(self):
        return self.role == 'school'

    def is_teacher(self):
        return self.role == 'teacher'

    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"
