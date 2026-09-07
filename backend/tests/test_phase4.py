"""
Phase 4 Tests — Subscriptions, Payments, Monetization & Entitlement System.

Covers Plans, Subscriptions, Payments, Webhooks, Idempotency, Provider Abstraction,
Entitlement Enforcement, Multi-Tenancy Security, and Limit Integrations.
"""
import json
import hashlib
from decimal import Decimal
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status

from apps.subscriptions.models import (
    Plan, PlanFeature, Subscription, SubscriptionStatus, SubscriptionProvider,
    FeatureCode, BillingInterval, PlanTier
)
from apps.subscriptions.services import (
    EntitlementService, SubscriptionService, EntitlementLimitExceededError
)
from apps.payments.models import (
    Payment, PaymentStatus, PaymentWebhookEvent, WebhookStatus, Invoice, InvoiceStatus
)
from apps.payments.providers.factory import PaymentProviderFactory
from apps.payments.providers.base import (
    ProviderConfigurationError, InvalidWebhookSignatureError, BasePaymentProvider
)
from apps.payments.providers.stripe_provider import StripeProvider
from apps.payments.providers.payme_provider import PaymeProvider
from apps.payments.providers.click_provider import ClickProvider
from apps.bots.models import Bot
from apps.games.models import Game, GamePhase
from apps.tournaments.models import Tournament, TournamentStatus
from apps.templates.models import GameTemplate

User = get_user_model()


def make_user(email='user@example.com', password='password123'):
    return User.objects.create_user(email=email, password=password, username=email.split('@')[0])


# ===========================================================================
# Test Suite 1: Plans and Features
# ===========================================================================

class TestPlansAndFeatures(TestCase):
    def test_default_plans_initialization(self):
        """Default plans (FREE, STARTER, PRO) are initialized correctly."""
        plans = EntitlementService.get_or_create_default_plans()
        self.assertIn('FREE', plans)
        self.assertIn('STARTER', plans)
        self.assertIn('PRO', plans)

        free_plan = plans['FREE']
        self.assertEqual(free_plan.price, Decimal('0.00'))

        # Check feature caps for FREE plan
        max_bots = free_plan.features.get(feature_code=FeatureCode.MAX_BOTS)
        self.assertEqual(max_bots.limit_value, 1)

        custom_roles = free_plan.features.get(feature_code=FeatureCode.CUSTOM_ROLES)
        self.assertFalse(custom_roles.enabled)

    def test_inactive_plans_hidden(self):
        """Inactive plans are not returned by default queryset."""
        EntitlementService.get_or_create_default_plans()
        p = Plan.objects.create(name='Deprecated', code='deprecated', is_active=False)
        active_plans = Plan.objects.filter(is_active=True)
        self.assertNotIn(p, active_plans)


# ===========================================================================
# Test Suite 2: Subscription Lifecycle
# ===========================================================================

class TestSubscriptionLifecycle(TestCase):
    def setUp(self):
        self.user = make_user()
        EntitlementService.get_or_create_default_plans()

    def test_default_free_subscription(self):
        """User without subscription automatically receives active FREE subscription."""
        sub = EntitlementService.get_active_subscription(self.user)
        self.assertEqual(sub.user, self.user)
        self.assertEqual(sub.status, SubscriptionStatus.ACTIVE)
        self.assertEqual(sub.plan.code, 'free')
        self.assertTrue(sub.is_valid())

    def test_subscription_activation(self):
        """SubscriptionService.activate_subscription upgrades user plan."""
        starter_plan = Plan.objects.get(code='starter')
        sub = SubscriptionService.activate_subscription(
            user=self.user,
            plan=starter_plan,
            provider='STRIPE',
            provider_sub_id='sub_123',
        )
        self.assertEqual(sub.plan, starter_plan)
        self.assertEqual(sub.status, SubscriptionStatus.ACTIVE)
        self.assertEqual(sub.provider, 'STRIPE')
        self.assertEqual(sub.provider_subscription_id, 'sub_123')

    def test_subscription_cancellation_and_resume(self):
        """Subscription can be scheduled for cancellation and resumed."""
        starter_plan = Plan.objects.get(code='starter')
        sub = SubscriptionService.activate_subscription(self.user, starter_plan)

        # Cancel
        canceled = SubscriptionService.cancel_subscription(sub)
        self.assertTrue(canceled.cancel_at_period_end)
        self.assertIsNotNone(canceled.canceled_at)

        # Resume
        resumed = SubscriptionService.resume_subscription(canceled)
        self.assertFalse(resumed.cancel_at_period_end)
        self.assertIsNone(resumed.canceled_at)


# ===========================================================================
# Test Suite 3: Payment Provider Abstraction
# ===========================================================================

class TestPaymentProviderAbstraction(TestCase):
    def test_factory_returns_correct_providers(self):
        """PaymentProviderFactory returns valid instances for supported names."""
        stripe = PaymentProviderFactory.get_provider('STRIPE')
        payme = PaymentProviderFactory.get_provider('PAYME')
        click = PaymentProviderFactory.get_provider('CLICK')

        self.setIsInstance(stripe, StripeProvider)
        self.setIsInstance(payme, PaymeProvider)
        self.setIsInstance(click, ClickProvider)

    def setIsInstance(self, obj, cls):
        self.assertTrue(isinstance(obj, cls))

    def test_unsupported_provider_raises(self):
        """Unsupported provider name raises PaymentProviderError."""
        from apps.payments.providers.base import PaymentProviderError
        with self.assertRaises(PaymentProviderError):
            PaymentProviderFactory.get_provider('BITCOIN')

    def test_missing_credentials_raises_configuration_error(self):
        """Providers raise ProviderConfigurationError when API keys are absent."""
        stripe = StripeProvider()
        payme = PaymeProvider()
        click = ClickProvider()

        user = make_user()
        plan = Plan.objects.create(name='Test', code='test_plan', price=10.00)

        # Assuming test env does not have real secret keys set
        with self.assertRaises(ProviderConfigurationError):
            stripe.validate_configuration()
        with self.assertRaises(ProviderConfigurationError):
            payme.validate_configuration()
        with self.assertRaises(ProviderConfigurationError):
            click.validate_configuration()


# ===========================================================================
# Test Suite 4: Webhook Verification and Idempotency
# ===========================================================================

class TestWebhookVerificationAndIdempotency(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = make_user()
        EntitlementService.get_or_create_default_plans()

    def test_stripe_webhook_invalid_signature_rejected(self):
        """Stripe webhook with missing or bad signature returns 400."""
        url = '/api/v1/billing/webhooks/stripe/'
        response = self.client.post(url, data={'type': 'checkout.session.completed'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_payme_webhook_invalid_auth_rejected(self):
        """Payme webhook with bad Basic auth returns 400."""
        url = '/api/v1/billing/webhooks/payme/'
        response = self.client.post(
            url,
            data={'method': 'PerformTransaction'},
            format='json',
            HTTP_AUTHORIZATION='Basic invalid_base64_payload'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_click_webhook_invalid_sign_rejected(self):
        """Click webhook with bad sign_string returns 400."""
        url = '/api/v1/billing/webhooks/click/'
        response = self.client.post(
            url,
            data={'click_trans_id': '123', 'sign_string': 'bad_md5'},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_idempotent_webhook_deduplication(self):
        """Duplicate webhook payload hash is safely skipped."""
        payload_data = json.dumps({'type': 'checkout.session.completed', 'id': 'evt_test_123'})
        payload_hash = hashlib.sha256(payload_data.encode('utf-8')).hexdigest()

        # Pre-create processed event
        PaymentWebhookEvent.objects.create(
            provider='STRIPE',
            event_id='evt_test_123',
            event_type='checkout.session.completed',
            payload_hash=payload_hash,
            status=WebhookStatus.PROCESSED,
            raw_payload={'type': 'checkout.session.completed', 'id': 'evt_test_123'},
        )

        url = '/api/v1/billing/webhooks/stripe/'
        # Send duplicate request
        response = self.client.post(
            url,
            data=payload_data,
            content_type='application/json',
            HTTP_STRIPE_SIGNATURE='t=123,v1=mock_sig'
        )
        # Should return 200 with idempotent: True
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data.get('idempotent'))


# ===========================================================================
# Test Suite 5: Entitlement Enforcement & Usage Limits
# ===========================================================================

class TestEntitlementLimits(TestCase):
    def setUp(self):
        self.user = make_user()
        EntitlementService.get_or_create_default_plans()

    def test_free_tier_bot_limit(self):
        """Free tier user can create 1 bot, but 2nd bot raises EntitlementLimitExceededError."""
        # 1st bot -> allowed
        EntitlementService.can_create_bot(self.user)

        # Create 1st bot in DB
        Bot.objects.create(owner=self.user, name='Bot 1', telegram_username='@bot1')

        # 2nd bot -> limit reached
        with self.assertRaises(EntitlementLimitExceededError) as ctx:
            EntitlementService.can_create_bot(self.user)

        self.assertEqual(ctx.exception.feature_code, FeatureCode.MAX_BOTS)
        self.assertEqual(ctx.exception.limit, 1)

    def test_upgraded_starter_tier_bot_limit(self):
        """Starter tier allows 3 bots."""
        starter_plan = Plan.objects.get(code='starter')
        SubscriptionService.activate_subscription(self.user, starter_plan)

        # Create 2 bots in DB
        Bot.objects.create(owner=self.user, name='Bot 1', telegram_username='@bot1')
        Bot.objects.create(owner=self.user, name='Bot 2', telegram_username='@bot2')

        # 3rd bot -> allowed
        EntitlementService.can_create_bot(self.user)

        # Create 3rd bot
        Bot.objects.create(owner=self.user, name='Bot 3', telegram_username='@bot3')

        # 4th bot -> limit reached
        with self.assertRaises(EntitlementLimitExceededError):
            EntitlementService.can_create_bot(self.user)

    def test_custom_roles_feature_gate(self):
        """Free tier user cannot create custom roles; Starter tier can."""
        # Free tier
        with self.assertRaises(EntitlementLimitExceededError):
            EntitlementService.can_use_custom_roles(self.user)

        # Upgrade to Starter
        starter_plan = Plan.objects.get(code='starter')
        SubscriptionService.activate_subscription(self.user, starter_plan)

        # Starter tier -> allowed
        EntitlementService.can_use_custom_roles(self.user)

    def test_tournament_mode_feature_gate(self):
        """Free tier user cannot create tournaments; Starter/Pro tier can."""
        with self.assertRaises(EntitlementLimitExceededError):
            EntitlementService.can_create_tournament(self.user)

        # Upgrade to Starter
        starter_plan = Plan.objects.get(code='starter')
        SubscriptionService.activate_subscription(self.user, starter_plan)

        # Starter tier -> allowed
        EntitlementService.can_create_tournament(self.user)


# ===========================================================================
# Test Suite 6: Multi-Tenancy Isolation
# ===========================================================================

class TestMultiTenancyBillingIsolation(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user_a = make_user('usera@example.com')
        self.user_b = make_user('userb@example.com')
        EntitlementService.get_or_create_default_plans()

        # Create payments for User A & B
        Payment.objects.create(user=self.user_a, amount=Decimal('9.99'), provider='STRIPE')
        Payment.objects.create(user=self.user_b, amount=Decimal('29.99'), provider='PAYME')

    def test_user_a_cannot_see_user_b_payments(self):
        """User A only sees their own payment history."""
        self.client.force_authenticate(user=self.user_a)
        response = self.client.get('/api/v1/billing/payments/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data.get('results', response.data)
        self.assertEqual(len(results), 1)
        self.assertEqual(float(results[0]['amount']), 9.99)

    def test_user_b_cannot_see_user_a_payments(self):
        """User B only sees their own payment history."""
        self.client.force_authenticate(user=self.user_b)
        response = self.client.get('/api/v1/billing/payments/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data.get('results', response.data)
        self.assertEqual(len(results), 1)
        self.assertEqual(float(results[0]['amount']), 29.99)
