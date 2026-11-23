from django.db import models
from core.utils import school_logo_upload_path

class School(models.Model):
    STATUS_CHOICES = (
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('suspended', 'Suspended'),
    )

    name = models.CharField(max_length=255)
    code = models.CharField(max_length=50, unique=True)
    affiliation_number = models.CharField(max_length=100, blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    city = models.CharField(max_length=100, blank=True, null=True)
    state = models.CharField(max_length=100, blank=True, null=True)
    postal_code = models.CharField(max_length=20, blank=True, null=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    website = models.URLField(blank=True, null=True)
    principal_name = models.CharField(max_length=150, blank=True, null=True)
    logo = models.ImageField(upload_to=school_logo_upload_path, blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    subscription_plan = models.CharField(max_length=50, blank=True, null=True, default='')
    card_price = models.DecimalField(max_digits=8, decimal_places=2, default=50.00)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.code:
            import uuid
            self.code = f"SCH{uuid.uuid4().hex[:6].upper()}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name}"
