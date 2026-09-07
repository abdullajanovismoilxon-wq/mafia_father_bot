"""
Entitlement and Subscription Service Layer.

EntitlementService — Centralized authority for feature gates, resource limits, and usage checks.
SubscriptionService — Subscription lifecycle management (activation, cancellation, expiration).
"""
import logging
from typing import Dict, Any, Optional
from datetime import timedelta
from django.db import transaction
from django.utils import timezone
from apps.subscriptions.models import (
    Plan, PlanFeature, Subscription, SubscriptionStatus, SubscriptionProvider,
    FeatureCode, BillingInterval, PlanTier
)

logger = logging.getLogger(__name__)


class EntitlementLimitExceededError(Exception):
    """
    Raised when a user attempts to create a resource exceeding their active Plan limit.
    Carries structured metadata for HTTP 402/403 machine-readable API responses.
    """
    def __init__(self, feature_code: str, limit: int, current_usage: int):
        self.feature_code = feature_code
        self.limit = limit
        self.current_usage = current_usage
        super().__init__(
            f"Plan limit reached for '{feature_code}'. Limit: {limit}, Current Usage: {current_usage}."
        )


class EntitlementService:
    """
    Centralized Entitlement Service enforcing SaaS monetization limits.
    Prevents scattering subscription check logic throughout views.
    """

    @classmethod
    def get_or_create_default_plans(cls) -> Dict[str, Plan]:
        """Ensures default SaaS plans and feature rules exist in DB."""
        plans = {}

        # 1. FREE Plan
        free, _ = Plan.objects.get_or_create(
            code='free',
            defaults={
                'name': 'Free Tier',
                'description': 'Basic plan for hobbyists and trial games.',
                'price': 0.00,
                'billing_interval': BillingInterval.MONTHLY,
                'display_order': 1,
            }
        )
        PlanFeature.objects.get_or_create(plan=free, feature_code=FeatureCode.MAX_BOTS, defaults={'limit_value': 1, 'enabled': True})
        PlanFeature.objects.get_or_create(plan=free, feature_code=FeatureCode.MAX_ACTIVE_GAMES, defaults={'limit_value': 2, 'enabled': True})
        PlanFeature.objects.get_or_create(plan=free, feature_code=FeatureCode.MAX_PLAYERS_PER_GAME, defaults={'limit_value': 8, 'enabled': True})
        PlanFeature.objects.get_or_create(plan=free, feature_code=FeatureCode.MAX_TOURNAMENTS, defaults={'limit_value': 0, 'enabled': False})
        PlanFeature.objects.get_or_create(plan=free, feature_code=FeatureCode.MAX_TEMPLATES, defaults={'limit_value': 2, 'enabled': True})
        PlanFeature.objects.get_or_create(plan=free, feature_code=FeatureCode.CUSTOM_ROLES, defaults={'limit_value': 0, 'enabled': False})
        PlanFeature.objects.get_or_create(plan=free, feature_code=FeatureCode.TOURNAMENT_MODE, defaults={'limit_value': 0, 'enabled': False})
        plans['FREE'] = free

        # 2. STARTER Plan
        starter, _ = Plan.objects.get_or_create(
            code='starter',
            defaults={
                'name': 'Starter',
                'description': 'Ideal for small Telegram channels and communities.',
                'price': 9.99,
                'billing_interval': BillingInterval.MONTHLY,
                'display_order': 2,
            }
        )
        PlanFeature.objects.get_or_create(plan=starter, feature_code=FeatureCode.MAX_BOTS, defaults={'limit_value': 3, 'enabled': True})
        PlanFeature.objects.get_or_create(plan=starter, feature_code=FeatureCode.MAX_ACTIVE_GAMES, defaults={'limit_value': 5, 'enabled': True})
        PlanFeature.objects.get_or_create(plan=starter, feature_code=FeatureCode.MAX_PLAYERS_PER_GAME, defaults={'limit_value': 12, 'enabled': True})
        PlanFeature.objects.get_or_create(plan=starter, feature_code=FeatureCode.MAX_TOURNAMENTS, defaults={'limit_value': 1, 'enabled': True})
        PlanFeature.objects.get_or_create(plan=starter, feature_code=FeatureCode.MAX_TEMPLATES, defaults={'limit_value': 5, 'enabled': True})
        PlanFeature.objects.get_or_create(plan=starter, feature_code=FeatureCode.CUSTOM_ROLES, defaults={'limit_value': 5, 'enabled': True})
        PlanFeature.objects.get_or_create(plan=starter, feature_code=FeatureCode.TOURNAMENT_MODE, defaults={'limit_value': 1, 'enabled': True})
        plans['STARTER'] = starter

        # 3. PRO Plan
        pro, _ = Plan.objects.get_or_create(
            code='pro',
            defaults={
                'name': 'Pro',
                'description': 'Full power for active gaming communities and tournaments.',
                'price': 29.99,
                'billing_interval': BillingInterval.MONTHLY,
                'display_order': 3,
            }
        )
        PlanFeature.objects.get_or_create(plan=pro, feature_code=FeatureCode.MAX_BOTS, defaults={'limit_value': 10, 'enabled': True})
        PlanFeature.objects.get_or_create(plan=pro, feature_code=FeatureCode.MAX_ACTIVE_GAMES, defaults={'limit_value': 20, 'enabled': True})
        PlanFeature.objects.get_or_create(plan=pro, feature_code=FeatureCode.MAX_PLAYERS_PER_GAME, defaults={'limit_value': 20, 'enabled': True})
        PlanFeature.objects.get_or_create(plan=pro, feature_code=FeatureCode.MAX_TOURNAMENTS, defaults={'limit_value': 10, 'enabled': True})
        PlanFeature.objects.get_or_create(plan=pro, feature_code=FeatureCode.MAX_TEMPLATES, defaults={'limit_value': 20, 'enabled': True})
        PlanFeature.objects.get_or_create(plan=pro, feature_code=FeatureCode.CUSTOM_ROLES, defaults={'limit_value': 20, 'enabled': True})
        PlanFeature.objects.get_or_create(plan=pro, feature_code=FeatureCode.TOURNAMENT_MODE, defaults={'limit_value': 1, 'enabled': True})
        PlanFeature.objects.get_or_create(plan=pro, feature_code=FeatureCode.ADVANCED_ANALYTICS, defaults={'limit_value': 1, 'enabled': True})
        plans['PRO'] = pro

        return plans

    @classmethod
    def get_active_subscription(cls, user) -> Subscription:
        """
        Returns active Subscription for user.
        If user has no subscription, creates a FREE plan subscription.
        """
        cls.get_or_create_default_plans()

        sub = Subscription.objects.filter(
            user=user,
            status__in=[SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIALING]
        ).select_related('plan').first()

        if not sub or not sub.is_valid():
            free_plan = Plan.objects.get(code='free')
            sub, _ = Subscription.objects.get_or_create(
                user=user,
                status=SubscriptionStatus.ACTIVE,
                defaults={
                    'plan': free_plan,
                    'plan_tier': PlanTier.FREE,
                    'current_period_start': timezone.now(),
                    'current_period_end': timezone.now() + timedelta(days=3650),
                }
            )
            if sub.plan != free_plan and not sub.is_valid():
                sub.plan = free_plan
                sub.status = SubscriptionStatus.ACTIVE
                sub.save(update_fields=['plan', 'status'])

        return sub

    @classmethod
    def get_active_plan(cls, user) -> Plan:
        sub = cls.get_active_subscription(user)
        return sub.plan or Plan.objects.get(code='free')

    @classmethod
    def get_feature_limit(cls, user, feature_code: str) -> int:
        """
        Returns feature limit for user:
        -1 = unlimited
        >=0 = numeric limit
        0 (with enabled=False) = disabled
        """
        if getattr(user, 'is_platform_owner', False):
            return -1  # Platform Owner has unlimited access to everything

        plan = cls.get_active_plan(user)
        try:
            pf = plan.features.get(feature_code=feature_code)
            if not pf.enabled:
                return 0
            return pf.limit_value
        except PlanFeature.DoesNotExist:
            return 0

    @classmethod
    def is_feature_enabled(cls, user, feature_code: str) -> bool:
        if getattr(user, 'is_platform_owner', False):
            return True
        limit = cls.get_feature_limit(user, feature_code)
        return limit != 0

    @classmethod
    def check_limit(cls, user, feature_code: str, current_usage: int) -> None:
        """
        Validates whether current_usage is under limit.
        Raises EntitlementLimitExceededError if limit is reached.
        """
        if getattr(user, 'is_platform_owner', False):
            return  # Platform Owner bypass

        limit = cls.get_feature_limit(user, feature_code)
        if limit == -1:
            return  # Unlimited
        if current_usage >= limit:
            raise EntitlementLimitExceededError(
                feature_code=feature_code,
                limit=limit,
                current_usage=current_usage,
            )

    @classmethod
    def can_create_bot(cls, user) -> None:
        """Checks MAX_BOTS against current active bots count."""
        from apps.bots.models import Bot
        current_bots = Bot.objects.filter(owner=user).exclude(status='DELETED').count()
        cls.check_limit(user, FeatureCode.MAX_BOTS, current_bots)

    @classmethod
    def can_start_game(cls, user, player_count: int = 4) -> None:
        """Checks MAX_ACTIVE_GAMES and MAX_PLAYERS_PER_GAME."""
        from apps.games.models import Game, GamePhase
        active_games = Game.objects.filter(
            bot__owner=user,
            phase__in=[GamePhase.STARTING, GamePhase.NIGHT, GamePhase.DAY, GamePhase.DISCUSSION, GamePhase.VOTING, GamePhase.ELIMINATION]
        ).count()
        cls.check_limit(user, FeatureCode.MAX_ACTIVE_GAMES, active_games)

        max_players = cls.get_feature_limit(user, FeatureCode.MAX_PLAYERS_PER_GAME)
        if max_players != -1 and player_count > max_players:
            raise EntitlementLimitExceededError(
                feature_code=FeatureCode.MAX_PLAYERS_PER_GAME,
                limit=max_players,
                current_usage=player_count,
            )

    @classmethod
    def can_create_tournament(cls, user) -> None:
        """Checks TOURNAMENT_MODE and MAX_TOURNAMENTS."""
        if not cls.is_feature_enabled(user, FeatureCode.TOURNAMENT_MODE):
            raise EntitlementLimitExceededError(
                feature_code=FeatureCode.TOURNAMENT_MODE, limit=0, current_usage=1
            )
        from apps.tournaments.models import Tournament, TournamentStatus
        current_tournaments = Tournament.objects.filter(
            owner=user, status__in=[TournamentStatus.REGISTRATION, TournamentStatus.ACTIVE]
        ).count()
        cls.check_limit(user, FeatureCode.MAX_TOURNAMENTS, current_tournaments)

    @classmethod
    def can_use_custom_roles(cls, user) -> None:
        """Checks CUSTOM_ROLES entitlement."""
        if not cls.is_feature_enabled(user, FeatureCode.CUSTOM_ROLES):
            raise EntitlementLimitExceededError(
                feature_code=FeatureCode.CUSTOM_ROLES, limit=0, current_usage=1
            )

    @classmethod
    def can_create_template(cls, user) -> None:
        """Checks MAX_TEMPLATES entitlement."""
        from apps.templates.models import GameTemplate
        current_templates = GameTemplate.objects.filter(owner=user, status='ACTIVE').count()
        cls.check_limit(user, FeatureCode.MAX_TEMPLATES, current_templates)

    @classmethod
    def get_usage_summary(cls, user) -> Dict[str, Any]:
        """Returns comprehensive resource usage vs plan limits summary for UI dashboard."""
        from apps.bots.models import Bot
        from apps.games.models import Game, GamePhase
        from apps.tournaments.models import Tournament, TournamentStatus
        from apps.templates.models import GameTemplate

        plan = cls.get_active_plan(user)

        bots_count = Bot.objects.filter(owner=user).exclude(status='DELETED').count()
        active_games_count = Game.objects.filter(
            bot__owner=user,
            phase__in=[GamePhase.STARTING, GamePhase.NIGHT, GamePhase.DAY, GamePhase.DISCUSSION, GamePhase.VOTING, GamePhase.ELIMINATION]
        ).count()
        tournaments_count = Tournament.objects.filter(
            owner=user, status__in=[TournamentStatus.REGISTRATION, TournamentStatus.ACTIVE]
        ).count()
        templates_count = GameTemplate.objects.filter(owner=user, status='ACTIVE').count()

        return {
            'plan_name': plan.name,
            'plan_code': plan.code,
            'billing_interval': plan.billing_interval,
            'usage': {
                'bots': {'current': bots_count, 'limit': cls.get_feature_limit(user, FeatureCode.MAX_BOTS)},
                'active_games': {'current': active_games_count, 'limit': cls.get_feature_limit(user, FeatureCode.MAX_ACTIVE_GAMES)},
                'max_players_per_game': {'limit': cls.get_feature_limit(user, FeatureCode.MAX_PLAYERS_PER_GAME)},
                'tournaments': {'current': tournaments_count, 'limit': cls.get_feature_limit(user, FeatureCode.MAX_TOURNAMENTS)},
                'templates': {'current': templates_count, 'limit': cls.get_feature_limit(user, FeatureCode.MAX_TEMPLATES)},
                'custom_roles_enabled': cls.is_feature_enabled(user, FeatureCode.CUSTOM_ROLES),
                'tournament_mode_enabled': cls.is_feature_enabled(user, FeatureCode.TOURNAMENT_MODE),
            }
        }


class SubscriptionService:
    """High-level Subscription lifecycle service."""

    @classmethod
    def activate_subscription(
        cls,
        user,
        plan: Plan,
        provider: str = 'MANUAL',
        provider_sub_id: str = '',
        period_days: int = 30,
    ) -> Subscription:
        """
        Activates or upgrades user subscription under atomic transaction.
        """
        now = timezone.now()
        period_end = now + timedelta(days=period_days)

        with transaction.atomic():
            sub, created = Subscription.objects.select_for_update().get_or_create(
                user=user,
                defaults={
                    'plan': plan,
                    'plan_tier': plan.code.upper(),
                    'status': SubscriptionStatus.ACTIVE,
                    'provider': provider,
                    'provider_subscription_id': provider_sub_id,
                    'current_period_start': now,
                    'current_period_end': period_end,
                }
            )
            if not created:
                sub.plan = plan
                sub.plan_tier = plan.code.upper()
                sub.status = SubscriptionStatus.ACTIVE
                sub.provider = provider
                sub.provider_subscription_id = provider_sub_id or sub.provider_subscription_id
                sub.current_period_start = now
                sub.current_period_end = period_end
                sub.cancel_at_period_end = False
                sub.save()

            logger.info(f"Subscription activated for {user.email}: Plan '{plan.name}' [{provider}]")
            return sub

    @classmethod
    def cancel_subscription(cls, subscription: Subscription) -> Subscription:
        """Schedules subscription for cancellation at period end."""
        with transaction.atomic():
            subscription.cancel_at_period_end = True
            subscription.canceled_at = timezone.now()
            subscription.save(update_fields=['cancel_at_period_end', 'canceled_at'])
            logger.info(f"Subscription #{subscription.id} scheduled for cancellation.")
            return subscription

    @classmethod
    def resume_subscription(cls, subscription: Subscription) -> Subscription:
        """Resumes a subscription scheduled for cancellation."""
        with transaction.atomic():
            subscription.cancel_at_period_end = False
            subscription.canceled_at = None
            subscription.save(update_fields=['cancel_at_period_end', 'canceled_at'])
            logger.info(f"Subscription #{subscription.id} resumed.")
            return subscription

    @classmethod
    def check_expired_subscriptions(cls) -> int:
        """
        Background reconciliation task expiring subscriptions whose period has ended.
        """
        now = timezone.now()
        expired_count = 0
        qs = Subscription.objects.filter(
            status=SubscriptionStatus.ACTIVE,
            current_period_end__lt=now,
        )
        for sub in qs:
            with transaction.atomic():
                sub.status = SubscriptionStatus.EXPIRED
                sub.save(update_fields=['status'])
                expired_count += 1
                logger.info(f"Subscription #{sub.id} for user {sub.user.email} marked EXPIRED.")
        return expired_count
