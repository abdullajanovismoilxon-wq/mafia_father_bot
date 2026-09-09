import uuid
from decimal import Decimal
from django.db import models
from django.conf import settings
from apps.common.models import BaseEntityModel


class CurrencyType(models.TextChoices):
    MONEY = 'MONEY', 'Money ($)'
    DIAMONDS = 'DIAMONDS', 'Diamonds (💎)'
    COINS = 'COINS', 'Coins (🪙)'


class TransactionType(models.TextChoices):
    TRANSFER = 'TRANSFER', 'Transfer'
    PURCHASE = 'PURCHASE', 'Purchase'
    REWARD = 'REWARD', 'Game Reward'
    GIFT = 'GIFT', 'Gift'
    REFUND = 'REFUND', 'Refund'
    ADMIN_ADJUSTMENT = 'ADMIN_ADJUSTMENT', 'Admin Adjustment'
    DEPOSIT = 'DEPOSIT', 'Deposit / Payment'


class Wallet(BaseEntityModel):
    """Server-authoritative virtual wallet for a user or Telegram player."""
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='wallet'
    )
    telegram_id = models.BigIntegerField(unique=True, null=True, blank=True, db_index=True)
    money = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))
    diamonds = models.PositiveIntegerField(default=0)
    coins = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        owner_repr = self.user.email if self.user else f"TG:{self.telegram_id}"
        return f"Wallet({owner_repr} | ${self.money}, 💎{self.diamonds}, 🪙{self.coins})"


class WalletTransaction(BaseEntityModel):
    """Immutable ledger of all wallet credit and debit operations."""
    wallet = models.ForeignKey(Wallet, on_delete=models.CASCADE, related_name='transactions')
    tx_type = models.CharField(max_length=30, choices=TransactionType.choices, db_index=True)
    currency = models.CharField(max_length=20, choices=CurrencyType.choices)
    amount = models.DecimalField(max_digits=14, decimal_places=2)  # Positive for credit, negative for debit
    balance_after = models.DecimalField(max_digits=14, decimal_places=2)
    reference_id = models.CharField(max_length=100, blank=True, db_index=True)
    description = models.CharField(max_length=255, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['wallet', 'created_at']),
            models.Index(fields=['tx_type', 'created_at']),
        ]

    def __str__(self):
        return f"Tx({self.wallet_id}: {self.tx_type} {self.amount} {self.currency})"


class CurrencyRate(BaseEntityModel):
    """Configurable currency exchange rates (e.g. USD to UZS)."""
    currency_code = models.CharField(max_length=10, unique=True, db_index=True)
    rate_to_usd = models.DecimalField(max_digits=14, decimal_places=4, default=Decimal('1.0000'))
    name = models.CharField(max_length=50, default='')

    def __str__(self):
        return f"1 USD = {self.rate_to_usd} {self.currency_code}"


class MarketplaceCategory(BaseEntityModel):
    """Catalog category for marketplace items."""
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=50, unique=True, db_index=True)
    icon = models.CharField(max_length=20, default='💎')
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['order', 'name']

    def __str__(self):
        return f"{self.icon} {self.name}"


class MarketplaceItemType(models.TextChoices):
    DIAMONDS_PACK = 'DIAMONDS_PACK', 'Diamonds Pack'
    VIP_PACK = 'VIP_PACK', 'VIP Subscription Pack'
    COSMETIC = 'COSMETIC', 'Cosmetic / Theme'
    BADGE = 'BADGE', 'Profile Badge'
    ROLE = 'ROLE', 'Special Role'
    BONUS = 'BONUS', 'Game Bonus'
    GIFT_ITEM = 'GIFT_ITEM', 'Gift Item'


class MarketplaceItem(BaseEntityModel):
    """Items available for purchase in marketplace."""
    category = models.ForeignKey(
        MarketplaceCategory,
        on_delete=models.CASCADE,
        related_name='items'
    )
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=50, unique=True, db_index=True)
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=20, default='🎁')
    item_type = models.CharField(max_length=30, choices=MarketplaceItemType.choices, db_index=True)
    price_diamonds = models.PositiveIntegerField(default=0)
    price_money_usd = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    diamond_amount = models.PositiveIntegerField(default=0, help_text="Amount of diamonds credited if item is DIAMONDS_PACK")
    vip_days = models.PositiveIntegerField(default=0, help_text="Number of VIP days granted if item is VIP_PACK")
    is_active = models.BooleanField(default=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['category__order', 'price_diamonds', 'name']

    def __str__(self):
        return f"{self.icon} {self.name} ({self.price_diamonds} 💎 / ${self.price_money_usd})"


class Purchase(BaseEntityModel):
    """User purchase transaction record."""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='purchases'
    )
    telegram_id = models.BigIntegerField(null=True, blank=True, db_index=True)
    item = models.ForeignKey(MarketplaceItem, on_delete=models.PROTECT, related_name='purchases')
    amount_paid = models.DecimalField(max_digits=14, decimal_places=2)
    currency_paid = models.CharField(max_length=20, choices=CurrencyType.choices)
    status = models.CharField(max_length=20, default='COMPLETED')

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Purchase #{self.id}: {self.item.name} ({self.amount_paid} {self.currency_paid})"


class Inventory(BaseEntityModel):
    """Owned items and cosmetics per player."""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='inventory'
    )
    telegram_id = models.BigIntegerField(null=True, blank=True, db_index=True)
    item = models.ForeignKey(MarketplaceItem, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    acquired_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = [['user', 'item'], ['telegram_id', 'item']]
        ordering = ['-acquired_at']

    def __str__(self):
        return f"Inventory: {self.item.name} x{self.quantity}"


class GiftRecord(BaseEntityModel):
    """Record of gifts sent between players."""
    sender_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sent_gifts'
    )
    sender_telegram_id = models.BigIntegerField(null=True, blank=True, db_index=True)
    recipient_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='received_gifts'
    )
    recipient_telegram_id = models.BigIntegerField(null=True, blank=True, db_index=True)
    item = models.ForeignKey(MarketplaceItem, on_delete=models.PROTECT)
    message = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Gift: {self.sender_telegram_id} -> {self.recipient_telegram_id} ({self.item.name})"


class VIPLevel(models.TextChoices):
    BRONZE = 'BRONZE', 'VIP Bronze 🥉'
    SILVER = 'SILVER', 'VIP Silver 🥈'
    GOLD = 'GOLD', 'VIP Gold 🥇'
    DIAMOND = 'DIAMOND', 'VIP Diamond 💎'


class VIPSubscription(BaseEntityModel):
    """Player VIP status and duration tracking."""
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='vip_subscription'
    )
    telegram_id = models.BigIntegerField(unique=True, null=True, blank=True, db_index=True)
    vip_level = models.CharField(max_length=20, choices=VIPLevel.choices, default=VIPLevel.GOLD)
    starts_at = models.DateTimeField()
    expires_at = models.DateTimeField()
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['-expires_at']

    def __str__(self):
        return f"VIP({self.vip_level} | expires {self.expires_at})"


class PaymentOrderStatus(models.TextChoices):
    PENDING_REVIEW = 'PENDING_REVIEW', 'Pending Review'
    APPROVED = 'APPROVED', 'Approved'
    REJECTED = 'REJECTED', 'Rejected'
    CANCELLED = 'CANCELLED', 'Cancelled'


class PaymentOrder(BaseEntityModel):
    """Manual/P2P payment order requiring administrative review."""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='payment_orders'
    )
    telegram_id = models.BigIntegerField(null=True, blank=True, db_index=True)
    order_id = models.CharField(max_length=50, unique=True, db_index=True)
    amount_usd = models.DecimalField(max_digits=10, decimal_places=2)
    amount_uzs = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))
    diamonds_to_credit = models.PositiveIntegerField(default=0)
    payment_method = models.CharField(max_length=50, default='P2P_CARD')
    status = models.CharField(
        max_length=20,
        choices=PaymentOrderStatus.choices,
        default=PaymentOrderStatus.PENDING_REVIEW,
        db_index=True
    )
    receipt_reference = models.CharField(max_length=255, blank=True)
    receipt_image_url = models.URLField(max_length=500, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_orders'
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    admin_notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Order #{self.order_id} ({self.status} - 💎{self.diamonds_to_credit})"


class PlayerHero(BaseEntityModel):
    """
    Player's personal customized Hero (Geroy).
    - Can only be used in-game when player's role is DON or KOMISSAR (DETECTIVE).
    - Enables daytime shooting using 1 charge per shot.
    - Power/damage scales with level (Level 1: 50-60%, Level 10: 100% Instant Kill).
    - Max defense scales with level (Level 1: 15, +10 per level up) and gives bonus HP.
    - Universal 🖤 Himoya shields player from all other lethal deaths (+10 per level up).
    - Recharging costs diamonds.
    - Gaining score from kills allows leveling up.
    - Can be transferred / given to another player.
    """
    telegram_id = models.BigIntegerField(unique=True, db_index=True)
    owner_name = models.CharField(max_length=100, default="O'yinchi")
    name = models.CharField(max_length=100, default="Mening Geroyim")
    level = models.PositiveIntegerField(default=1)
    score = models.PositiveIntegerField(default=0)
    charges = models.PositiveIntegerField(default=20)
    is_active = models.BooleanField(default=True)
    current_defense = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['-level', '-score']

    def __str__(self):
        return f"Hero {self.name} (Lvl {self.level}, {self.owner_name} - {self.telegram_id})"

    @property
    def power_min(self) -> int:
        if self.level >= 10:
            return 100
        return min(100, int(50 + (self.level - 1) * 5))

    @property
    def min_damage_percent(self) -> int:
        return self.power_min

    @property
    def power_max(self) -> int:
        if self.level >= 10:
            return 100
        return min(100, int(60 + (self.level - 1) * 5))

    @property
    def max_damage_percent(self) -> int:
        return self.power_max

    @property
    def max_defense(self) -> int:
        # Level 1: 15, Level 2: 25, ... (+10 per level)
        return int(15 + (self.level - 1) * 10)

    @property
    def recharge_cost_diamonds(self) -> int:
        from apps.superadmin.services import SettingService
        return SettingService.get_int('price_hero_recharge', 1)

    @property
    def next_level_score(self) -> int:
        # Level 1 -> 2: 1980, Level 2 -> 3: 2970, Level 9 -> 10: 9900 ball
        return (self.level + 1) * 990

    def add_kill_score(self, points: int = 150) -> bool:
        self.score += points
        leveled_up = False
        while self.level < 10 and self.score >= self.next_level_score:
            self.level += 1
            self.current_defense += 10  # +10 🖤 Himoya per level up
            leveled_up = True
        self.save(update_fields=['score', 'level', 'current_defense'])
        return leveled_up


