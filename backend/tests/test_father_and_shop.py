"""
MAFIA BOT FATHER — Bot Creator & 10 Game Shop Items Test Suite
Validates the 10 custom in-game shop items and bot provisioning.
"""
from decimal import Decimal
from django.test import TestCase
from apps.users.models import User, UserRole
from apps.bots.models import Bot, BotStatus, BotCredential
from apps.economy.models import (
    MarketplaceItem, MarketplaceCategory, CurrencyType, Wallet
)
from apps.economy.services import MarketplaceService, EconomyService, InsufficientBalanceError
from apps.stats.models import PlayerProfile
from apps.stats.services import StatsService


class FatherAndShopItemsTest(TestCase):
    """Test suite for the 10 in-game shop items and father provisioning."""

    def setUp(self):
        self.user = User.objects.create_user(
            email='shopper@mafiabotfather.uz',
            username='shopper',
            password='password123'
        )
        self.profile = StatsService.get_or_create_profile(
            telegram_id=987654321,
            username='shopper',
            user=self.user
        )
        self.wallet = EconomyService.get_or_create_wallet(user=self.user, telegram_id=self.profile.telegram_id)
        MarketplaceService.get_or_create_default_categories_and_items()

    def test_ten_game_shop_items_initialized(self):
        """Verifies all 10 custom shop items are created with exact specs."""
        expected_items = [
            ('DOCUMENTS', '📁 Hujjatlar', 5),
            ('SHIELD', '🛡 Himoya', 10),
            ('VOTE_SHIELD', '⚖️ Ovozdan himoya', 8),
            ('KILLER_SHIELD', '⛑️ Qotildan himoya', 12),
            ('RIFLE', '🔫 Miltiq', 15),
            ('POISON_SHIELD', '💊 Doridan himoya', 6),
            ('MASK', '🎭 Maska', 7),
            ('HERO', '🥷 Geroy', 20),
            ('SLIP_SHIELD', '🪤 Sirpanishdan himoya', 6),
            ('HERO_SHIELD', '🔰 Geroydan himoya', 14),
        ]

        for code, expected_name, expected_dia in expected_items:
            item = MarketplaceItem.objects.filter(code=code).first()
            self.assertIsNotNone(item, f"Item {code} not found in marketplace.")
            self.assertEqual(item.name, expected_name)
            self.assertEqual(item.price_diamonds, expected_dia)
            self.assertTrue(len(item.description) > 10)

    def test_purchase_game_item_success(self):
        """Verifies purchasing a shop item debits diamonds."""
        # Credit 50 diamonds to wallet
        EconomyService.credit_wallet(
            wallet=self.wallet,
            currency=CurrencyType.DIAMONDS,
            amount=Decimal('50')
        )
        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.diamonds, 50)

        # Purchase Shield (10 diamonds)
        purchase = MarketplaceService.purchase_item(
            item_code='SHIELD',
            telegram_id=self.profile.telegram_id,
            currency=CurrencyType.DIAMONDS
        )
        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.diamonds, 40)
        self.assertEqual(purchase.item.code, 'SHIELD')

    def test_purchase_game_item_insufficient_balance(self):
        """Verifies error raised when diamonds are insufficient."""
        self.wallet.diamonds = 2
        self.wallet.save(update_fields=['diamonds'])

        with self.assertRaises(InsufficientBalanceError):
            MarketplaceService.purchase_item(
                item_code='RIFLE',
                telegram_id=self.profile.telegram_id,
                currency=CurrencyType.DIAMONDS
            )
