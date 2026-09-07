import hashlib
import json
import logging
from django.db import transaction
from django.utils import timezone
from rest_framework import generics, status, views, serializers as drf_serializers
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from .models import Plan, Subscription, SubscriptionStatus, SubscriptionProvider
from .serializers import PlanSerializer, SubscriptionSerializer, CheckoutRequestSerializer
from .services import EntitlementService, SubscriptionService, EntitlementLimitExceededError
from apps.payments.models import Payment, PaymentStatus, PaymentWebhookEvent, WebhookStatus, Invoice, InvoiceStatus
from apps.payments.serializers import PaymentSerializer, InvoiceSerializer
from apps.payments.providers.factory import PaymentProviderFactory
from apps.payments.providers.base import (
    PaymentProviderError, InvalidWebhookSignatureError, ProviderConfigurationError
)

logger = logging.getLogger(__name__)


class PlanListView(generics.ListAPIView):
    """List active SaaS subscription plans."""
    serializer_class = PlanSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        EntitlementService.get_or_create_default_plans()
        return Plan.objects.filter(is_active=True).prefetch_related('features')


class MySubscriptionView(generics.RetrieveAPIView):
    """Retrieve current authenticated user's active subscription."""
    serializer_class = SubscriptionSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return EntitlementService.get_active_subscription(self.request.user)


class CheckoutView(views.APIView):
    """
    Create a payment checkout session with selected provider (Stripe, Payme, Click).
    Does NOT activate subscription directly — subscription is activated via verified webhook.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = CheckoutRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        plan_code = serializer.validated_data['plan_code']
        provider_name = serializer.validated_data['provider']
        return_url = serializer.validated_data['return_url']
        cancel_url = serializer.validated_data['cancel_url']

        try:
            plan = Plan.objects.get(code=plan_code, is_active=True)
        except Plan.DoesNotExist:
            return Response({'detail': f"Plan '{plan_code}' not found."}, status=status.HTTP_404_NOT_FOUND)

        try:
            provider = PaymentProviderFactory.get_provider(provider_name)
            checkout_result = provider.create_checkout_session(
                user=request.user,
                plan=plan,
                return_url=return_url,
                cancel_url=cancel_url,
            )

            # Record PENDING Payment
            with transaction.atomic():
                Payment.objects.create(
                    user=request.user,
                    amount=plan.price,
                    currency=plan.currency,
                    status=PaymentStatus.PENDING,
                    provider=provider_name,
                    provider_payment_id=checkout_result.session_id,
                    metadata=checkout_result.metadata,
                )

            return Response({
                'checkout_url': checkout_result.checkout_url,
                'session_id': checkout_result.session_id,
                'provider': provider_name,
                'plan': plan_code,
            }, status=status.HTTP_200_OK)

        except ProviderConfigurationError as e:
            return Response(
                {'detail': str(e), 'code': 'PROVIDER_NOT_CONFIGURED'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )
        except PaymentProviderError as e:
            return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.exception("Error creating checkout session:")
            return Response({'detail': 'Checkout creation failed.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class CancelSubscriptionView(views.APIView):
    """Schedules subscription cancellation at current period end."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        sub = EntitlementService.get_active_subscription(request.user)
        if sub.plan and sub.plan.code == 'free':
            return Response({'detail': 'Free plan cannot be canceled.'}, status=status.HTTP_400_BAD_REQUEST)

        SubscriptionService.cancel_subscription(sub)
        return Response(SubscriptionSerializer(sub).data)


class ResumeSubscriptionView(views.APIView):
    """Resumes a subscription scheduled for cancellation."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        sub = EntitlementService.get_active_subscription(request.user)
        SubscriptionService.resume_subscription(sub)
        return Response(SubscriptionSerializer(sub).data)


class MyPaymentsListView(generics.ListAPIView):
    """List authenticated user's payment transaction history."""
    serializer_class = PaymentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Payment.objects.filter(user=self.request.user)


class MyInvoicesListView(generics.ListAPIView):
    """List authenticated user's billing invoices."""
    serializer_class = InvoiceSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Invoice.objects.filter(user=self.request.user)


class MyUsageView(views.APIView):
    """Retrieve authenticated user's resource usage vs plan limits."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        usage = EntitlementService.get_usage_summary(request.user)
        return Response(usage)


class MyEntitlementsView(views.APIView):
    """Retrieve active plan entitlements summary."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        plan = EntitlementService.get_active_plan(request.user)
        return Response(PlanSerializer(plan).data)


class WebhookReceiverView(views.APIView):
    """
    Public webhook endpoint processing payment provider events.
    Enforces signature verification, payload hash deduplication,
    idempotent transaction processing, and atomic subscription activation.
    """
    permission_classes = [AllowAny]

    def post(self, request, provider_name: str):
        provider_name = provider_name.upper()

        try:
            provider = PaymentProviderFactory.get_provider(provider_name)
        except PaymentProviderError as e:
            return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)

        body_bytes = request.body
        payload_hash = hashlib.sha256(body_bytes).hexdigest()

        # Idempotency check: see if payload hash was already processed
        existing_event = PaymentWebhookEvent.objects.filter(
            provider=provider_name, payload_hash=payload_hash, status=WebhookStatus.PROCESSED
        ).first()
        if existing_event:
            logger.info(f"Idempotent webhook skipped (already processed event #{existing_event.event_id})")
            return Response({
                'status': 'already_processed',
                'event_id': existing_event.event_id,
                'idempotent': True
            }, status=status.HTTP_200_OK)

        try:
            result = provider.process_webhook_event(request.headers, body_bytes)

            # Deduplicate by provider + event_id
            event_obj, created = PaymentWebhookEvent.objects.get_or_create(
                provider=provider_name,
                event_id=result.event_id,
                defaults={
                    'event_type': result.event_type,
                    'payload_hash': payload_hash,
                    'status': WebhookStatus.PENDING,
                    'raw_payload': result.metadata,
                }
            )
            if not created and event_obj.status == WebhookStatus.PROCESSED:
                return Response({
                    'status': 'already_processed',
                    'event_id': event_obj.event_id,
                    'idempotent': True
                }, status=status.HTTP_200_OK)

            # Atomic transaction processing
            with transaction.atomic():
                # Find user
                user = None
                if result.user_id:
                    from django.contrib.auth import get_user_model
                    User = get_user_model()
                    try:
                        user = User.objects.get(id=result.user_id)
                    except (User.DoesNotExist, ValueError):
                        pass

                # Find plan
                plan = None
                if result.plan_code:
                    try:
                        plan = Plan.objects.get(code=result.plan_code)
                    except Plan.DoesNotExist:
                        pass

                # Update or create Payment
                payment = None
                if user and result.amount:
                    payment, _ = Payment.objects.update_or_create(
                        provider=provider_name,
                        provider_payment_id=result.provider_payment_id or result.event_id,
                        defaults={
                            'user': user,
                            'amount': result.amount,
                            'currency': result.currency or 'USD',
                            'status': result.payment_status,
                            'paid_at': timezone.now() if result.payment_status == 'SUCCEEDED' else None,
                            'metadata': result.metadata,
                        }
                    )

                # Activate Subscription on SUCCEEDED
                if result.payment_status == 'SUCCEEDED' and user and plan:
                    sub = SubscriptionService.activate_subscription(
                        user=user,
                        plan=plan,
                        provider=provider_name,
                        provider_sub_id=result.provider_payment_id or result.event_id,
                    )
                    if payment:
                        payment.subscription = sub
                        payment.save(update_fields=['subscription'])

                    # Generate Invoice
                    Invoice.objects.get_or_create(
                        user=user,
                        payment=payment,
                        defaults={
                            'subscription': sub,
                            'invoice_number': f"INV-{provider_name}-{result.event_id[:16]}",
                            'amount': result.amount,
                            'currency': result.currency or 'USD',
                            'status': InvoiceStatus.PAID,
                            'paid_at': timezone.now(),
                        }
                    )

                # Mark webhook event PROCESSED
                event_obj.status = WebhookStatus.PROCESSED
                event_obj.processed_at = timezone.now()
                event_obj.save(update_fields=['status', 'processed_at'])

            logger.info(f"Successfully processed webhook event #{result.event_id} from {provider_name}")
            return Response({
                'status': 'processed',
                'event_id': result.event_id,
                'payment_status': result.payment_status
            }, status=status.HTTP_200_OK)

        except (InvalidWebhookSignatureError, ProviderConfigurationError, PaymentProviderError) as e:
            logger.warning(f"Invalid webhook request for {provider_name}: {str(e)}")
            return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.exception(f"Error processing webhook for {provider_name}:")
            return Response({'detail': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
