from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import AcademicSessionViewSet, ClassLevelViewSet, SectionViewSet

router = DefaultRouter()
router.register(r'sessions', AcademicSessionViewSet, basename='academic-session')
router.register(r'classes', ClassLevelViewSet, basename='class-level')
router.register(r'sections', SectionViewSet, basename='section')

urlpatterns = [
    path('', include(router.urls)),
]
