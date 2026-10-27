from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import IDCardTemplateViewSet, IDCardBatchViewSet

router = DefaultRouter()
router.register(r'templates', IDCardTemplateViewSet, basename='idcard-template')
router.register(r'batches', IDCardBatchViewSet, basename='idcard-batch')

urlpatterns = [
    path('', include(router.urls)),
]
