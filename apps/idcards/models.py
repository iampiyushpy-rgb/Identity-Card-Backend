from django.db import models

class IDCardTemplate(models.Model):
    LAYOUT_CHOICES = (
        ('vertical', 'Vertical (Portrait)'),
        ('horizontal', 'Horizontal (Landscape)'),
    )

    school = models.ForeignKey('schools.School', on_delete=models.CASCADE, null=True, blank=True, related_name='idcard_templates')
    name = models.CharField(max_length=100)
    layout = models.CharField(max_length=20, choices=LAYOUT_CHOICES, default='vertical')
    primary_color = models.CharField(max_length=30, default='#1e3a8a')
    secondary_color = models.CharField(max_length=30, default='#f59e0b')
    header_background = models.CharField(max_length=30, default='#1e293b')
    show_blood_group = models.BooleanField(default=True)
    show_emergency_contact = models.BooleanField(default=True)
    show_barcode = models.BooleanField(default=True)
    show_address = models.BooleanField(default=True)
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-is_default', '-created_at']

    def __str__(self):
        return f"{self.name} ({self.layout})"

class IDCardBatch(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('generated', 'Generated'),
        ('downloaded', 'Downloaded'),
    )

    school = models.ForeignKey('schools.School', on_delete=models.CASCADE, related_name='idcard_batches')
    template = models.ForeignKey(IDCardTemplate, on_delete=models.SET_NULL, null=True, blank=True)
    session = models.ForeignKey('academics.AcademicSession', on_delete=models.CASCADE)
    class_level = models.ForeignKey('academics.ClassLevel', on_delete=models.SET_NULL, null=True, blank=True)
    section = models.ForeignKey('academics.Section', on_delete=models.SET_NULL, null=True, blank=True)
    total_cards = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='generated')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Batch #{self.id} - {self.school.name} ({self.total_cards} cards)"
