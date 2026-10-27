from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/v1/auth/', include('apps.accounts.urls')),
    path('api/v1/schools/', include('apps.schools.urls')),
    path('api/v1/academics/', include('apps.academics.urls')),
    path('api/v1/teachers/', include('apps.teachers.urls')),
    path('api/v1/students/', include('apps.students.urls')),
    path('api/v1/payments/', include('apps.payments.urls')),
    path('api/v1/idcards/', include('apps.idcards.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
