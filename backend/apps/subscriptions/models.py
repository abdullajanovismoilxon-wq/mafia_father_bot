from django.db import models
from django.conf import settings
from apps.common.models import BaseEntityModel


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class PlanTier(models.TextChoices):
    """Legacy choices for backward compat."""
    FREE = 'FREE', 'Free'
    STARTER = 'STARTER', 'Starter'
    PRO = 'PRO', 'Pro'
    BUSINESS = 'BUSINESS', 'Business'
    ENTERPRISE = 'ENTERPRISE', 'Enterprise'


class BillingInterval(models.TextChoices):
    MONTHLY = 'MONTHLY', 'Monthly'
    YEARLY = 'YEARLY', 'Yearly'


class SubscriptionStatus(models.TextChoices):
    TRIALING = 'TRIALING', 'Trialing'
    ACTIVE = 'ACTIVE', 'Active'
    PAST_DUE = 'PAST_DUE', 'Past Due'
    CANCELED = 'CANCELED', 'Canceled'
    EXPIRED = 'EXPIRED', 'Expired'
    PAUSED = 'PAUSED', 'Paused'


class SubscriptionProvider(models.TextChoices):
    MANUAL = 'MANUAL', 'Manual'
    STRIPE = 'STRIPE', 'Stripe'
    PAYME = 'PAYME', 'Payme'
    CLICK = 'CLICK', 'Click'


class FeatureCode(models.TextChoices):
    MAX_BOTS = 'MAX_BOTS', 'Maximum Active Bots'
    MAX_ACTIVE_GAMES = 'MAX_ACTIVE_GAMES', 'Maximum Concurrent Games'
    MAX_PLAYERS_PER_GAME = 'MAX_PLAYERS_PER_GAME', 'Maximum Players Per Game'
    MAX_TOURNAMENTS = 'MAX_TOURNAMENTS', 'Maximum Tournaments'
    MAX_TEMPLATES = 'MAX_TEMPLATES', 'Maximum Saved Templates'
    CUSTOM_ROLES = 'CUSTOM_ROLES', 'Custom Role Builder'
    ADVANCED_ANALYTICS = 'ADVANCED_ANALYTICS', 'Advanced Analytics'
    TOURNAMENT_MODE = 'TOURNAMENT_MODE', 'Tournament Mode Access'
    CUSTOM_GAME_CONFIGURATION = 'CUSTOM_GAME_CONFIGURATION', 'Custom Game Configuration'
    PRIORITY_SUPPORT = 'PRIORITY_SUPPORT', 'Priority Support'
    API_ACCESS = 'API_ACCESS', 'Direct API Access'


class DiscountType(models.TextChoices):
    PERCENTAGE = 'PERCENTAGE', 'Percentage'
    FIXED_AMOUNT = 'FIXED_AMOUNT', 'Fixed Amount'


# ---------------------------------------------------------------------------
# Domain Models
# ---------------------------------------------------------------------------

class Plan(BaseEntityModel):
    """
    SaaS Subscription Plan entity.
    Not hardcoded — configurable by platform admins.
    """
    name = models.CharField(max_length=100)
    code = models.SlugField(max_length=50, unique=True, db_index=True)
    description = models.TextField(blank=True, default='')
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    currency = models.CharField(max_length=3, default='USD')
    billing_interval = models.CharField(
        max_length=20, choices=BillingInterval.choices, default=BillingInterval.MONTHLY
    )
    is_active = models.BooleanField(default=True, db_index=True)
    display_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ['display_order', 'price']

    def __str__(self):
        return f"{self.name} (${self.price}/{self.billing_interval})"


class PlanFeature(BaseEntityModel):
    """
    A single feature or limit attached to a Plan.
    limit_value: -1 means unlimited, 0+ represents numeric cap.
    """
    plan = models.ForeignKey(Plan, on_delete=models.CASCADE, related_name='features')
    feature_code = models.CharField(max_length=50, choices=FeatureCode.choices, db_index=True)
    limit_value = models.IntegerField(
        default=0,
        help_text="-1 = unlimited, >=0 = numeric limit"
    )
    enabled = models.BooleanField(default=True)

    class Meta:
        unique_together = ('plan', 'feature_code')
        ordering = ['feature_code']

    def __str__(self):
        val = "Unlimited" if self.limit_value == -1 else str(self.limit_value)
        return f"{self.plan.code} → {self.feature_code}: {val} (enabled={self.enabled})"


class Subscription(BaseEntityModel):
    """
    User Subscription entity.
    Connects a User to a Plan with period dates and provider reference.
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='subscriptions',
        db_index=True,
    )
    plan = models.ForeignKey(
        Plan,
        on_delete=models.PROTECT,
        related_name='subscriptions',
        null=True,
        blank=True,
    )
    # Legacy field preserved for backward compat
    plan_tier = models.CharField(
        max_length=20,
        choices=PlanTier.choices,
        default=PlanTier.FREE
    )
    status = models.CharField(
        max_length=20,
        choices=SubscriptionStatus.choices,
        default=SubscriptionStatus.ACTIVE,
        db_index=True,
    )
    provider = models.CharField(
        max_length=20,
        choices=SubscriptionProvider.choices,
        default=SubscriptionProvider.MANUAL,
    )
    provider_subscription_id = models.CharField(max_length=255, blank=True, default='', db_index=True)

    current_period_start = models.DateTimeField(null=True, blank=True)
    current_period_end = models.DateTimeField(null=True, blank=True)
    cancel_at_period_end = models.BooleanField(default=False)
    canceled_at = models.DateTimeField(null=True, blank=True)

    trial_start = models.DateTimeField(null=True, blank=True)
    trial_end = models.DateTimeField(null=True, blank=True)

    # Legacy field preserved for backward compat
    max_bots = models.PositiveIntegerField(default=1)
    expires_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['status', 'current_period_end']),
        ]

    def is_valid(self) -> bool:
        """Returns True if subscription grants active access."""
        from django.utils import timezone
        if self.status not in (SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIALING):
            return False
        if self.current_period_end and self.current_period_end < timezone.now():
            return False
        return True

    def __str__(self):
        plan_name = self.plan.name if self.plan else self.plan_tier
        return f"Subscription [{plan_name}] ({self.status}) for {self.user.email}"


class Coupon(BaseEntityModel):
    """Discount Coupon for subscriptions."""
    code = models.CharField(max_length=50, unique=True, db_index=True)
    discount_type = models.CharField(
        max_length=20, choices=DiscountType.choices, default=DiscountType.PERCENTAGE
    )
    discount_value = models.DecimalField(max_digits=10, decimal_places=2)
    valid_from = models.DateTimeField(null=True, blank=True)
    valid_until = models.DateTimeField(null=True, blank=True)
    max_redemptions = models.PositiveIntegerField(default=0, help_text="0 = unlimited")
    used_count = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        ordering = ['-created_at']

    def is_valid(self) -> bool:
        from django.utils import timezone
        now = timezone.now()
        if not self.is_active:
            return False
        if self.valid_from and self.valid_from > now:
            return False
        if self.valid_until and self.valid_until < now:
            return False
        if self.max_redemptions > 0 and self.used_count >= self.max_redemptions:
            return False
        return True

    def __str__(self):
        return f"Coupon '{self.code}' ({self.discount_value} {self.discount_type})"


class CouponRedemption(BaseEntityModel):
    """Tracks which users have redeemed a Coupon."""
    coupon = models.ForeignKey(Coupon, on_delete=models.CASCADE, related_name='redemptions')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='coupon_redemptions')
    redeemed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('coupon', 'user')

    def __str__(self):
        return f"{self.user.email} redeemed {self.coupon.code}"
