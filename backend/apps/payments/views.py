from rest_framework import generics, serializers
from rest_framework.permissions import IsAuthenticated
from .models import Payment


class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = ('id', 'amount', 'currency', 'status', 'provider', 'transaction_id', 'created_at')


class MyPaymentsListView(generics.ListAPIView):
    """List authenticated user payment transactions."""
    serializer_class = PaymentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Payment.objects.filter(user=self.request.user)
