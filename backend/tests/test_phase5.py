"""
Phase 5 Tests — Production RBAC, Player Economy, Marketplace, VIP, Stats, Achievements, Admin APIs, Audit Logs & Health Checks.
"""
from decimal import Decimal
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework import status

from apps.users.models import UserRole
from apps.common.models import AdminAuditLog, AdminAuditAction
from apps.bots.models import Bot, BotStatus
from apps.games.models import Game, GamePhase
from apps.economy.models import (
    Wallet, WalletTransaction, CurrencyType, TransactionType,
    MarketplaceItem, MarketplaceCategory, VIPSubscription, VIPLevel,
    PaymentOrder, PaymentOrderStatus
)
from apps.economy.services import (
    EconomyService, MarketplaceService, InsufficientBalanceError
)
from apps.stats.models import PlayerProfile, PlayerStats, Achievement, UserAchievement
from apps.stats.services import StatsService, AchievementService

User = get_user_model()


def make_user(email='user@example.com', password='testpass123', role=UserRole.USER, is_staff=False, is_superuser=False):
    return User.objects.create_user(
        username=email.split('@')[0],
        email=email,
        password=password,
        role=role,
        is_staff=is_staff,
        is_superuser=is_superuser
    )


class TestUserRBACAndSuspension(TestCase):
    """Test User RBAC roles and account suspension properties."""

    def test_role_properties(self):
        user = make_user('user1@example.com', role=UserRole.USER)
        mod = make_user('mod1@example.com', role=UserRole.MODERATOR)
        admin = make_user('admin1@example.com', role=UserRole.ADMIN)
        superadmin = make_user('sadmin1@example.com', role=UserRole.SUPERADMIN, is_superuser=True)

        self.assertFalse(user.is_admin_or_staff)
        self.assertFalse(user.is_moderator_or_higher)

        self.assertFalse(mod.is_admin_or_staff)
        self.assertTrue(mod.is_moderator_or_higher)

        self.assertTrue(admin.is_admin_or_staff)
        self.assertTrue(admin.is_moderator_or_higher)

        self.assertTrue(superadmin.is_admin_or_staff)
        self.assertTrue(superadmin.is_moderator_or_higher)

    def test_suspension_flag(self):
        user = make_user('suspended@example.com')
        self.assertFalse(user.is_suspended)
        user.is_suspended = True
        user.is_active = False
        user.save()
        user.refresh_from_db()
        self.assertTrue(user.is_suspended)
        self.assertFalse(user.is_active)


class TestWalletAndEconomyOperations(TestCase):
    """Test virtual wallet balances, transactions, and P2P transfers."""

    def setUp(self):
        self.user_a = make_user('userA@example.com')
        self.user_b = make_user('userB@example.com')
        self.wallet_a = EconomyService.get_or_create_wallet(user=self.user_a)
        self.wallet_b = EconomyService.get_or_create_wallet(user=self.user_b)

    def test_wallet_creation_and_defaults(self):
        self.assertEqual(self.wallet_a.money, Decimal('0.00'))
        self.assertEqual(self.wallet_a.diamonds, 0)
        self.assertEqual(self.wallet_a.coins, 0)

    def test_credit_and_debit_operations(self):
        # Credit Money
        EconomyService.credit_wallet(self.wallet_a, CurrencyType.MONEY, Decimal('50.00'))
        self.wallet_a.refresh_from_db()
        self.assertEqual(self.wallet_a.money, Decimal('50.00'))

        # Credit Diamonds
        EconomyService.credit_wallet(self.wallet_a, CurrencyType.DIAMONDS, Decimal('100'))
        self.wallet_a.refresh_from_db()
        self.assertEqual(self.wallet_a.diamonds, 100)

        # Debit Money
        EconomyService.debit_wallet(self.wallet_a, CurrencyType.MONEY, Decimal('20.00'))
        self.wallet_a.refresh_from_db()
        self.assertEqual(self.wallet_a.money, Decimal('30.00'))

        # Debit Diamonds
        EconomyService.debit_wallet(self.wallet_a, CurrencyType.DIAMONDS, Decimal('40'))
        self.wallet_a.refresh_from_db()
        self.assertEqual(self.wallet_a.diamonds, 60)

    def test_debit_insufficient_balance_raises_error(self):
        with self.assertRaises(InsufficientBalanceError):
            EconomyService.debit_wallet(self.wallet_a, CurrencyType.MONEY, Decimal('10.00'))

        with self.assertRaises(InsufficientBalanceError):
            EconomyService.debit_wallet(self.wallet_a, CurrencyType.DIAMONDS, Decimal('5'))

    def test_money_transfer_success(self):
        EconomyService.credit_wallet(self.wallet_a, CurrencyType.MONEY, Decimal('100.00'))
        debit_tx, credit_tx = EconomyService.transfer_money(
            sender_wallet=self.wallet_a,
            recipient_wallet=self.wallet_b,
            amount=Decimal('35.50')
        )
        self.wallet_a.refresh_from_db()
        self.wallet_b.refresh_from_db()

        self.assertEqual(self.wallet_a.money, Decimal('64.50'))
        self.assertEqual(self.wallet_b.money, Decimal('35.50'))
        self.assertEqual(debit_tx.amount, Decimal('-35.50'))
        self.assertEqual(credit_tx.amount, Decimal('35.50'))

    def test_diamond_transfer_success(self):
        EconomyService.credit_wallet(self.wallet_a, CurrencyType.DIAMONDS, Decimal('50'))
        debit_tx, credit_tx = EconomyService.transfer_diamonds(
            sender_wallet=self.wallet_a,
            recipient_wallet=self.wallet_b,
            amount=20
        )
        self.wallet_a.refresh_from_db()
        self.wallet_b.refresh_from_db()

        self.assertEqual(self.wallet_a.diamonds, 30)
        self.assertEqual(self.wallet_b.diamonds, 20)

    def test_self_transfer_prevented(self):
        with self.assertRaises(ValueError):
            EconomyService.transfer_money(self.wallet_a, self.wallet_a, Decimal('10.00'))

        with self.assertRaises(ValueError):
            EconomyService.transfer_diamonds(self.wallet_a, self.wallet_a, 10)


class TestMarketplaceAndVIP(TestCase):
    """Test Marketplace catalog, purchases, VIP subscriptions, and P2P payments."""

    def setUp(self):
        self.user = make_user('buyer@example.com')
        self.admin = make_user('admin@example.com', role=UserRole.ADMIN, is_staff=True)
        self.wallet = EconomyService.get_or_create_wallet(user=self.user)
        MarketplaceService.get_or_create_default_categories_and_items()

    def test_default_items_created(self):
        dia_count = MarketplaceItem.objects.filter(item_type='DIAMONDS_PACK').count()
        vip_count = MarketplaceItem.objects.filter(item_type='VIP_PACK').count()
        self.assertGreaterEqual(dia_count, 8)
        self.assertGreaterEqual(vip_count, 3)

    def test_purchase_diamonds_pack(self):
        # Give user money
        EconomyService.credit_wallet(self.wallet, CurrencyType.MONEY, Decimal('20.00'))
        purchase = MarketplaceService.purchase_item(
            item_code='DIA_10',
            user=self.user,
            currency=CurrencyType.MONEY
        )
        self.wallet.refresh_from_db()
        self.assertEqual(purchase.status, 'COMPLETED')
        self.assertEqual(self.wallet.diamonds, 10)
        self.assertEqual(self.wallet.money, Decimal('20.00') - Decimal('1.36'))

    def test_purchase_vip_membership(self):
        # Give user diamonds
        EconomyService.credit_wallet(self.wallet, CurrencyType.DIAMONDS, Decimal('100'))
        purchase = MarketplaceService.purchase_item(
            item_code='VIP_GOLD_30',
            user=self.user,
            currency=CurrencyType.DIAMONDS
        )
        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.diamonds, 50)

        vip_sub = VIPSubscription.objects.get(user=self.user)
        self.assertTrue(vip_sub.is_active)
        self.assertEqual(vip_sub.vip_level, VIPLevel.GOLD)

    def test_manual_payment_order_flow(self):
        # 1. Create order for 100 diamonds
        order = MarketplaceService.create_payment_order(
            diamonds=100,
            user=self.user
        )
        self.assertEqual(order.status, PaymentOrderStatus.PENDING_REVIEW)
        self.assertEqual(order.diamonds_to_credit, 100)
        self.assertEqual(order.amount_usd, Decimal('13.60'))

        # 2. Admin approves order
        reviewed = MarketplaceService.review_payment_order(
            order_id=order.order_id,
            admin_user=self.admin,
            approve=True,
            admin_notes="Approved via Payme receipt check"
        )
        self.assertEqual(reviewed.status, PaymentOrderStatus.APPROVED)
        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.diamonds, 100)

        # Audit log created
        log = AdminAuditLog.objects.filter(action=AdminAuditAction.APPROVE_PAYMENT, target_id=order.order_id).first()
        self.assertIsNotNone(log)


class TestPlayerStatsAndAchievements(TestCase):
    """Test gameplay statistics recording and automatic achievement unlocks."""

    def setUp(self):
        self.profile = StatsService.get_or_create_profile(telegram_id=987654321, username='mafia_pro')

    def test_initial_profile_and_stats(self):
        self.assertEqual(self.profile.stats.games_played, 0)
        self.assertEqual(self.profile.stats.games_won, 0)
        self.assertEqual(self.profile.stats.current_win_streak, 0)

    def test_record_game_player_result_and_achievements(self):
        # 1. First victory
        StatsService.record_game_player_result(
            telegram_id=987654321,
            won=True,
            role_team='MAFIA',
            role_type='MAFIA',
            survived=True,
            kills=2
        )
        self.profile.refresh_from_db()
        stats = self.profile.stats
        self.assertEqual(stats.games_played, 1)
        self.assertEqual(stats.games_won, 1)
        self.assertEqual(stats.mafia_wins, 1)
        self.assertEqual(stats.survival_count, 1)
        self.assertEqual(stats.successful_kills, 2)
        self.assertEqual(stats.current_win_streak, 1)

        # Check FIRST_WIN achievement unlocked
        first_win_ach = UserAchievement.objects.filter(
            player_profile=self.profile,
            achievement__code='FIRST_WIN'
        ).first()
        self.assertIsNotNone(first_win_ach)

        # Wallet should receive achievement reward (5 diamonds + 50 coins) + game win coins (30 coins)
        wallet = EconomyService.get_or_create_wallet(telegram_id=987654321)
        self.assertGreaterEqual(wallet.diamonds, 5)
        self.assertGreaterEqual(wallet.coins, 80)

    def test_leaderboard_service(self):
        StatsService.record_game_player_result(telegram_id=987654321, won=True)
        leaders = StatsService.get_leaderboard(category='wins', limit=10)
        self.assertGreaterEqual(len(leaders), 1)
        self.assertEqual(leaders[0]['name'], 'mafia_pro')


class TestAdminAPIsAndSecurity(TestCase):
    """Test Admin Control Plane endpoints and RBAC security enforcement."""

    def setUp(self):
        self.admin = make_user('super@example.com', role=UserRole.ADMIN, is_staff=True)
        self.regular_user = make_user('normal@example.com', role=UserRole.USER)
        self.client = APIClient()

    def test_regular_user_forbidden_from_admin_endpoints(self):
        self.client.force_authenticate(user=self.regular_user)
        response = self.client.get('/api/v1/admin/overview/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        response = self.client.get('/api/v1/admin/users/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_overview_endpoint(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.get('/api/v1/admin/overview/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('users', response.data)
        self.assertIn('bots', response.data)
        self.assertIn('games', response.data)
        self.assertIn('revenue', response.data)
        self.assertIn('economy', response.data)

    def test_admin_suspend_and_activate_user(self):
        self.client.force_authenticate(user=self.admin)
        # Suspend
        url_suspend = f'/api/v1/admin/users/{self.regular_user.id}/suspend/'
        resp = self.client.post(url_suspend)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.regular_user.refresh_from_db()
        self.assertTrue(self.regular_user.is_suspended)

        # Activate
        url_activate = f'/api/v1/admin/users/{self.regular_user.id}/activate/'
        resp = self.client.post(url_activate)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.regular_user.refresh_from_db()
        self.assertFalse(self.regular_user.is_suspended)

    def test_admin_adjust_balance_endpoint(self):
        self.client.force_authenticate(user=self.admin)
        url = f'/api/v1/admin/users/{self.regular_user.id}/adjust_balance/'
        resp = self.client.post(url, {
            'currency': 'DIAMONDS',
            'amount': 25,
            'reason': 'Bonus reward'
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        wallet = EconomyService.get_or_create_wallet(user=self.regular_user)
        self.assertEqual(wallet.diamonds, 25)

    def test_health_endpoints(self):
        resp = self.client.get('/health/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['status'], 'healthy')

        resp_live = self.client.get('/health/live/')
        self.assertEqual(resp_live.status_code, status.HTTP_200_OK)

        resp_ready = self.client.get('/health/ready/')
        self.assertIn(resp_ready.status_code, [status.HTTP_200_OK, status.HTTP_503_SERVICE_UNAVAILABLE])
