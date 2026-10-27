import os
import uuid
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination

def student_photo_upload_path(instance, filename):
    """Generate clean upload path for student photos."""
    ext = filename.split('.')[-1]
    filename = f"{uuid.uuid4().hex[:12]}.{ext}"
    school_id = instance.school.id if instance.school else 'general'
    return os.path.join('student_photos', f'school_{school_id}', filename)

def school_logo_upload_path(instance, filename):
    """Generate clean upload path for school logos."""
    ext = filename.split('.')[-1]
    filename = f"logo_{uuid.uuid4().hex[:8]}.{ext}"
    return os.path.join('school_logos', filename)

class StandardResultsSetPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100

def api_response(success=True, message="", data=None, status_code=200):
    """Consistent API response wrapper."""
    payload = {
        "success": success,
        "message": message,
        "data": data
    }
    return Response(payload, status=status_code)
