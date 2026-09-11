from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from apps.stats.models import (
    PlayerProfile, PlayerStats, Achievement, UserAchievement, AchievementCategory
)
from apps.economy.services import EconomyService
from apps.economy.models import CurrencyType, TransactionType


class AchievementService:
    """Manages platform achievements and automatic reward distribution."""

    @classmethod
    def get_or_create_default_achievements(cls):
        """Seed standard achievements if not present."""
        achievements_data = [
            ('FIRST_WIN', '🏆 Birinchi Gʻalaba', 'Mafia o\'yinida birinchi g\'alabaga erishing', '🏆', AchievementCategory.VICTORY, 5, 50, 1),
            ('WINS_10', '🎯 10 Gʻalaba', '10 ta o\'yinda g\'alaba qozoning', '🎯', AchievementCategory.VICTORY, 15, 200, 10),
            ('WINS_50', '👑 Mafia Qiroli', '50 ta o\'yinda g\'alaba qozoning', '👑', AchievementCategory.VICTORY, 50, 1000, 50),
            ('STREAK_5', '🔥 5 Gʻalabali Seriya', 'Ketma-ket 5 marta g\'alaba qozoning', '🔥', AchievementCategory.VICTORY, 20, 300, 5),
            ('DOCTOR_HERO', '💊 Hayot Qutqaruvchisi', 'Doktor sifatida 5 marta fuqaroni qutqaring', '💊', AchievementCategory.ROLE_MASTERY, 10, 150, 5),
            ('DETECTIVE_SHERLOCK', '🕵 Detektiv Sherlock', 'Komissar sifatida 5 marta mafiyani fosh qiling', '🕵', AchievementCategory.ROLE_MASTERY, 10, 150, 5),
            ('SURVIVOR', '🛡 Omon Qoluvchi', '10 ta o\'yinda tirik holda yakunlang', '🛡', AchievementCategory.SURVIVAL, 15, 200, 10),
            ('GAMES_100', '🎲 100 ta Oʻyin', 'Jami 100 ta Mafia o\'yinida ishtirok eting', '🎲', AchievementCategory.SOCIAL, 30, 500, 100),
        ]
        for code, title, desc, icon, cat, dia_rew, coin_rew, target in achievements_data:
            Achievement.objects.get_or_create(
                code=code,
                defaults={
                    'title': title,
                    'description': desc,
                    'badge_icon': icon,
                    'category': cat,
                    'diamond_reward': dia_rew,
                    'coin_reward': coin_rew,
                    'target_count': target,
                    'is_active': True
                }
            )

    @classmethod
    def check_and_unlock_achievements(cls, profile: PlayerProfile):
        """Evaluates stats and unlocks any newly achieved milestones."""
        cls.get_or_create_default_achievements()
        stats = profile.stats
        all_achievements = Achievement.objects.filter(is_active=True)
        unlocked_codes = set(
            UserAchievement.objects.filter(player_profile=profile).values_list('achievement__code', flat=True)
        )

        for ach in all_achievements:
            if ach.code in unlocked_codes:
                continue

            qualified = False
            if ach.code == 'FIRST_WIN' and stats.games_won >= 1:
                qualified = True
            elif ach.code == 'WINS_10' and stats.games_won >= 10:
                qualified = True
            elif ach.code == 'WINS_50' and stats.games_won >= 50:
                qualified = True
            elif ach.code == 'STREAK_5' and stats.best_win_streak >= 5:
                qualified = True
            elif ach.code == 'DOCTOR_HERO' and stats.doctor_saves >= 5:
                qualified = True
            elif ach.code == 'DETECTIVE_SHERLOCK' and stats.detective_investigations >= 5:
                qualified = True
            elif ach.code == 'SURVIVOR' and stats.survival_count >= 10:
                qualified = True
            elif ach.code == 'GAMES_100' and stats.games_played >= 100:
                qualified = True

            if qualified:
                with transaction.atomic():
                    UserAchievement.objects.create(
                        player_profile=profile,
                        achievement=ach
                    )
                    wallet = EconomyService.get_or_create_wallet(
                        user=profile.user,
                        telegram_id=profile.telegram_id
                    )
                    if ach.diamond_reward > 0:
                        EconomyService.credit_wallet(
                            wallet=wallet,
                            currency=CurrencyType.DIAMONDS,
                            amount=Decimal(ach.diamond_reward),
                            tx_type=TransactionType.REWARD,
                            description=f"Achievement reward: {ach.title}",
                            reference_id=ach.code
                        )
                    if ach.coin_reward > 0:
                        EconomyService.credit_wallet(
                            wallet=wallet,
                            currency=CurrencyType.COINS,
                            amount=Decimal(ach.coin_reward),
                            tx_type=TransactionType.REWARD,
                            description=f"Achievement reward: {ach.title}",
                            reference_id=ach.code
                        )


class StatsService:
    """Manages player profiles and computes verified gameplay statistics."""

    @classmethod
    def get_or_create_profile(
        cls,
        telegram_id: int,
        username: str = '',
        first_name: str = '',
        last_name: str = '',
        user=None
    ) -> PlayerProfile:
        """Finds or creates a player profile and ensures associated stats and wallet exist."""
        profile, created = PlayerProfile.objects.get_or_create(
            telegram_id=telegram_id,
            defaults={
                'user': user,
                'telegram_username': username,
                'first_name': first_name,
                'last_name': last_name,
            }
        )
        if not created:
            updated = False
            if username and profile.telegram_username != username:
                profile.telegram_username = username
                updated = True
            if first_name and profile.first_name != first_name:
                profile.first_name = first_name
                updated = True
        # Special Platform Owner Detection (@ismoilo9)
        uname = (username or profile.telegram_username or '').lower().lstrip('@')
        if uname == 'ismoilo9' or profile.is_platform_owner:
            if not profile.is_platform_owner:
                profile.is_platform_owner = True
                profile.save(update_fields=['is_platform_owner'])

            if profile.user and not profile.user.is_platform_owner:
                profile.user.is_platform_owner = True
                profile.user.save(update_fields=['is_platform_owner'])

            # Grant VIP Diamond
            try:
                from apps.economy.models import VIPSubscription, VIPLevel
                from datetime import timedelta
                now = timezone.now()
                VIPSubscription.objects.update_or_create(
                    telegram_id=profile.telegram_id,
                    defaults={
                        'user': profile.user,
                        'vip_level': VIPLevel.DIAMOND,
                        'starts_at': now,
                        'expires_at': now + timedelta(days=3650),
                        'is_active': True,
                    }
                )
            except Exception as e:
                pass

        # Ensure PlayerStats exists
        PlayerStats.objects.get_or_create(player_profile=profile)
        # Ensure Wallet exists
        wallet = EconomyService.get_or_create_wallet(user=profile.user, telegram_id=profile.telegram_id)

        # Seed owner funds if needed
        if profile.is_platform_owner and wallet.diamonds < 10000:
            EconomyService.credit_wallet(
                wallet=wallet,
                currency=CurrencyType.DIAMONDS,
                amount=Decimal('99999'),
                tx_type=TransactionType.ADMIN_ADJUSTMENT,
                description="Platform Owner Diamond Allocation",
                reference_id="OWNER_SEED"
            )
            EconomyService.credit_wallet(
                wallet=wallet,
                currency=CurrencyType.COINS,
                amount=Decimal('99999'),
                tx_type=TransactionType.ADMIN_ADJUSTMENT,
                description="Platform Owner Coin Allocation",
                reference_id="OWNER_SEED"
            )

        return profile

    @classmethod
    def record_game_player_result(
        cls,
        telegram_id: int,
        won: bool,
        role_team: str = 'CITIZEN',
        role_type: str = 'CITIZEN',
        survived: bool = False,
        kills: int = 0,
        saves: int = 0,
        investigations: int = 0,
        votes: int = 0,
        is_mvp: bool = False,
        username: str = '',
        first_name: str = '',
        custom_reward_coins: int = None,
        custom_reward_diamonds: int = None
    ):
        """Updates player statistics after game finish, awards coins, and checks achievements."""
        profile = cls.get_or_create_profile(
            telegram_id=telegram_id,
            username=username,
            first_name=first_name
        )

        with transaction.atomic():
            stats = PlayerStats.objects.select_for_update().get(player_profile=profile)
            stats.games_played += 1

            if won:
                stats.games_won += 1
                stats.current_win_streak += 1
                if stats.current_win_streak > stats.best_win_streak:
                    stats.best_win_streak = stats.current_win_streak

                if role_team == 'MAFIA':
                    stats.mafia_wins += 1
                else:
                    stats.civilian_wins += 1
            else:
                stats.games_lost += 1
                stats.current_win_streak = 0

            if survived:
                stats.survival_count += 1
            if is_mvp:
                stats.mvp_count += 1

            stats.successful_kills += kills
            stats.doctor_saves += saves
            stats.detective_investigations += investigations
            stats.successful_votes += votes

            stats.save()

            # Award game reward coins & diamonds dynamically from SuperAdmin SettingService or custom tiered amount
            from apps.superadmin.services import SettingService
            if custom_reward_coins is not None:
                reward_coins = custom_reward_coins
            elif won:
                reward_coins = SettingService.get_int('victory_reward_coins', SettingService.get_int('reward_win_coins', 50))
            else:
                reward_coins = SettingService.get_int('participation_reward_coins', SettingService.get_int('reward_participation_coins', 15))

            if custom_reward_diamonds is not None:
                reward_diamonds = custom_reward_diamonds
            elif won:
                reward_diamonds = SettingService.get_int('victory_reward_diamonds', SettingService.get_int('reward_win_diamonds', 0))
            else:
                reward_diamonds = SettingService.get_int('participation_reward_diamonds', SettingService.get_int('reward_participation_diamonds', 0))

            wallet = EconomyService.get_or_create_wallet(
                user=profile.user,
                telegram_id=profile.telegram_id
            )
            if reward_coins > 0:
                EconomyService.credit_wallet(
                    wallet=wallet,
                    currency=CurrencyType.COINS,
                    amount=Decimal(reward_coins),
                    tx_type=TransactionType.REWARD,
                    description="Mafia Game Victory Reward" if won else "Mafia Game Participation Reward"
                )
            if reward_diamonds > 0:
                EconomyService.credit_wallet(
                    wallet=wallet,
                    currency=CurrencyType.DIAMONDS,
                    amount=Decimal(reward_diamonds),
                    tx_type=TransactionType.REWARD,
                    description="Mafia Game Victory Diamond Reward"
                )

        # Check and unlock achievements
        AchievementService.check_and_unlock_achievements(profile)

    @classmethod
    def get_leaderboard(cls, category: str = 'wins', limit: int = 20) -> list[dict]:
        """Returns ordered leaderboard records."""
        qs = PlayerStats.objects.select_related('player_profile')

        if category == 'wins':
            qs = qs.order_by('-games_won', '-games_played')
        elif category == 'streak':
            qs = qs.order_by('-best_win_streak', '-games_won')
        elif category == 'games':
            qs = qs.order_by('-games_played', '-games_won')
        elif category == 'diamonds':
            # Order by wallet diamonds
            from apps.economy.models import Wallet
            wallets = Wallet.objects.filter(diamonds__gt=0).order_by('-diamonds')[:limit]
            results = []
            for rank, w in enumerate(wallets, start=1):
                name = w.user.email if w.user else f"Telegram ID {w.telegram_id}"
                results.append({
                    'rank': rank,
                    'name': name,
                    'value': w.diamonds,
                    'label': '💎 Olmoslar'
                })
            return results
        else:
            qs = qs.order_by('-games_won')

        results = []
        for rank, s in enumerate(qs[:limit], start=1):
            results.append({
                'rank': rank,
                'name': s.player_profile.full_name,
                'username': s.player_profile.telegram_username or '',
                'games_played': s.games_played,
                'games_won': s.games_won,
                'win_rate': s.win_rate,
                'streak': s.best_win_streak,
            })
        return results


class CoupleService:
    """Service managing player couples (/para, /dpara, /mypara)."""

    @classmethod
    def get_couple(cls, telegram_id: int):
        from apps.stats.models import PlayerCouple
        from django.db.models import Q
        return PlayerCouple.objects.filter(
            Q(user1_id=telegram_id) | Q(user2_id=telegram_id),
            is_active=True
        ).first()

    @classmethod
    def get_partner_info(cls, telegram_id: int):
        couple = cls.get_couple(telegram_id)
        if not couple:
            return None
        if couple.user1_id == telegram_id:
            return {
                'partner_id': couple.user2_id,
                'partner_name': couple.user2_name or f"User {couple.user2_id}",
                'created_at': couple.created_at,
                'couple': couple
            }
        else:
            return {
                'partner_id': couple.user1_id,
                'partner_name': couple.user1_name or f"User {couple.user1_id}",
                'created_at': couple.created_at,
                'couple': couple
            }

    @classmethod
    def create_couple(cls, user1_id: int, user1_name: str, user2_id: int, user2_name: str, chat_id: int = None):
        from apps.stats.models import PlayerCouple
        cls.break_couple(user1_id)
        cls.break_couple(user2_id)
        return PlayerCouple.objects.create(
            user1_id=user1_id,
            user1_name=user1_name,
            user2_id=user2_id,
            user2_name=user2_name,
            chat_id=chat_id,
            is_active=True
        )

    @classmethod
    def break_couple(cls, telegram_id: int):
        from apps.stats.models import PlayerCouple
        from django.db.models import Q
        couples = list(PlayerCouple.objects.filter(
            Q(user1_id=telegram_id) | Q(user2_id=telegram_id),
            is_active=True
        ))
        for c in couples:
            c.is_active = False
            c.save(update_fields=['is_active'])
        return couples
