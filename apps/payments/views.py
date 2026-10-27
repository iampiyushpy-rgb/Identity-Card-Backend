from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Sum
from .models import Payment
from .serializers import PaymentSerializer
from core.permissions import IsSuperAdmin

class PaymentViewSet(viewsets.ModelViewSet):
    serializer_class = PaymentSerializer

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsSuperAdmin()]
        return [permissions.IsAuthenticated()]

    def get_queryset(self):
        user = self.request.user
        qs = Payment.objects.select_related('school')
        if user.is_superuser or user.role == 'admin':
            school_id = self.request.query_params.get('school_id')
            if school_id:
                qs = qs.filter(school_id=school_id)
            return qs
        elif user.school:
            return qs.filter(school=user.school)
        return Payment.objects.none()

    @action(detail=False, methods=['get'])
    def summary(self, request):
        qs = self.get_queryset()
        total_completed = qs.filter(status='completed').aggregate(total=Sum('amount'))['total'] or 0
        total_pending = qs.filter(status='pending').aggregate(total=Sum('amount'))['total'] or 0
        return Response({
            "total_completed": float(total_completed),
            "total_pending": float(total_pending),
            "total_transactions": qs.count()
        })
