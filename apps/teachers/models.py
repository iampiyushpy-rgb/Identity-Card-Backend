from django.db import models
from django.conf import settings

class Teacher(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='teacher_profile')
    school = models.ForeignKey('schools.School', on_delete=models.CASCADE, related_name='teachers')
    employee_id = models.CharField(max_length=50)
    designation = models.CharField(max_length=100, default='Teacher')
    qualification = models.CharField(max_length=100, blank=True, null=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    joining_date = models.DateField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['user__first_name', 'employee_id']
        unique_together = ('school', 'employee_id')

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} ({self.employee_id})"
