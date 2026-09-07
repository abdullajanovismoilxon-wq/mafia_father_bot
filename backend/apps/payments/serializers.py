from rest_framework import serializers
from .models import Payment, Invoice, RefundRecord


class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = (
            'id', 'amount', 'currency', 'status', 'provider',
            'provider_payment_id', 'transaction_id', 'paid_at',
            'failure_reason', 'created_at'
        )
        read_only_fields = fields


class InvoiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Invoice
        fields = (
            'id', 'invoice_number', 'amount', 'currency',
            'status', 'issued_at', 'paid_at'
        )
        read_only_fields = fields


class RefundRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = RefundRecord
        fields = ('id', 'payment', 'amount', 'reason', 'status', 'created_at')
        read_only_fields = fields
