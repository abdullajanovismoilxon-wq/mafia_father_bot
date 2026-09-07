from rest_framework import serializers
from .models import Plan, PlanFeature, Subscription, Coupon


class PlanFeatureSerializer(serializers.ModelSerializer):
    class Meta:
        model = PlanFeature
        fields = ('id', 'feature_code', 'limit_value', 'enabled')


class PlanSerializer(serializers.ModelSerializer):
    features = PlanFeatureSerializer(many=True, read_only=True)

    class Meta:
        model = Plan
        fields = (
            'id', 'name', 'code', 'description', 'price', 'currency',
            'billing_interval', 'is_active', 'display_order', 'features'
        )


class SubscriptionSerializer(serializers.ModelSerializer):
    plan = PlanSerializer(read_only=True)
    is_valid = serializers.BooleanField(read_only=True)

    class Meta:
        model = Subscription
        fields = (
            'id', 'plan', 'plan_tier', 'status', 'provider',
            'provider_subscription_id', 'current_period_start',
            'current_period_end', 'cancel_at_period_end', 'canceled_at',
            'trial_start', 'trial_end', 'is_valid', 'created_at'
        )


class CheckoutRequestSerializer(serializers.Serializer):
    plan_code = serializers.CharField(max_length=50)
    provider = serializers.ChoiceField(choices=['STRIPE', 'PAYME', 'CLICK'])
    return_url = serializers.URLField(required=False, default='http://localhost:3000/dashboard/billing')
    cancel_url = serializers.URLField(required=False, default='http://localhost:3000/dashboard/billing')


class CouponSerializer(serializers.ModelSerializer):
    class Meta:
        model = Coupon
        fields = ('id', 'code', 'discount_type', 'discount_value', 'is_active')
