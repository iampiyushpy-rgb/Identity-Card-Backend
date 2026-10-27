from rest_framework import serializers
from .models import Payment

class PaymentSerializer(serializers.ModelSerializer):
    school_name = serializers.CharField(source='school.name', read_only=True)
    school_code = serializers.CharField(source='school.code', read_only=True)

    class Meta:
        model = Payment
        fields = [
            'id', 'school', 'school_name', 'school_code',
            'amount', 'payment_date', 'transaction_id',
            'payment_mode', 'status', 'receipt_number',
            'description', 'created_at'
        ]
        read_only_fields = ['id', 'receipt_number', 'transaction_id', 'created_at']
