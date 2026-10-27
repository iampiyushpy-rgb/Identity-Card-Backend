from django.db import models

class AcademicSession(models.Model):
    school = models.ForeignKey('schools.School', on_delete=models.CASCADE, related_name='academic_sessions')
    name = models.CharField(max_length=50)  # e.g., "2025-2026"
    start_date = models.DateField(blank=True, null=True)
    end_date = models.DateField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-name']
        unique_together = ('school', 'name')

    def __str__(self):
        return f"{self.name} - {self.school.name}"

class ClassLevel(models.Model):
    school = models.ForeignKey('schools.School', on_delete=models.CASCADE, related_name='classes')
    name = models.CharField(max_length=50)  # e.g., "Class 1", "Class 10"
    order = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['order', 'name']
        unique_together = ('school', 'name')

    def __str__(self):
        return f"{self.name} ({self.school.code})"

class Section(models.Model):
    school = models.ForeignKey('schools.School', on_delete=models.CASCADE, related_name='sections')
    class_level = models.ForeignKey(ClassLevel, on_delete=models.CASCADE, related_name='sections')
    name = models.CharField(max_length=20)  # e.g., "A", "Rose"
    teacher = models.ForeignKey('teachers.Teacher', on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_sections')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['class_level__order', 'name']
        unique_together = ('class_level', 'name')

    def __str__(self):
        return f"{self.class_level.name} - {self.name}"
