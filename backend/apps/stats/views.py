from rest_framework import permissions, status
from rest_framework.views import APIView
from rest_framework.response import Response
from apps.stats.models import PlayerProfile, PlayerStats, Achievement, UserAchievement
from apps.stats.services import StatsService, AchievementService
from apps.economy.models import Wallet, Inventory, VIPSubscription
from apps.economy.services import EconomyService


class MyProfileView(APIView):
    """Retrieve full player profile, gameplay statistics, achievements, and inventory."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        telegram_id = user.telegram_id or 1000000 + int(user.id.int % 1000000)
        profile = StatsService.get_or_create_profile(
            telegram_id=telegram_id,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name,
            user=user
        )
        stats = profile.stats
        wallet = EconomyService.get_or_create_wallet(user=user, telegram_id=telegram_id)
        vip = getattr(user, 'vip_subscription', None)
        if not vip and telegram_id:
            vip = VIPSubscription.objects.filter(telegram_id=telegram_id, is_active=True).first()

        # Achievements
        AchievementService.get_or_create_default_achievements()
        all_ach = Achievement.objects.filter(is_active=True)
        user_ach_map = {
            ua.achievement_id: ua.unlocked_at
            for ua in UserAchievement.objects.filter(player_profile=profile)
        }

        achievements_data = []
        for a in all_ach:
            unlocked = a.id in user_ach_map
            achievements_data.append({
                'id': str(a.id),
                'code': a.code,
                'title': a.title,
                'description': a.description,
                'badge_icon': a.badge_icon,
                'diamond_reward': a.diamond_reward,
                'is_unlocked': unlocked,
                'unlocked_at': user_ach_map[a.id].isoformat() if unlocked else None,
            })

        # Inventory
        inv_items = Inventory.objects.filter(user=user, is_active=True).select_related('item')
        inventory_data = []
        for inv in inv_items:
            inventory_data.append({
                'item_name': inv.item.name,
                'item_code': inv.item.code,
                'icon': inv.item.icon,
                'quantity': inv.quantity,
                'acquired_at': inv.acquired_at.isoformat(),
            })

        return Response({
            'profile': {
                'telegram_id': profile.telegram_id,
                'username': profile.telegram_username or user.username,
                'full_name': profile.full_name,
                'email': user.email,
                'role': getattr(user, 'role', 'USER'),
                'group_name': user.group_name or user.effective_group_name if hasattr(user, 'effective_group_name') else '',
                'language_code': profile.language_code,
            },
            'wallet': {
                'money': str(wallet.money),
                'diamonds': wallet.diamonds,
                'coins': wallet.coins,
            },
            'vip': {
                'is_active': vip.is_active if vip else False,
                'level': vip.vip_level if vip else None,
                'expires_at': vip.expires_at.isoformat() if (vip and vip.expires_at) else None,
            },
            'stats': {
                'games_played': stats.games_played,
                'games_won': stats.games_won,
                'games_lost': stats.games_lost,
                'win_rate': stats.win_rate,
                'mafia_wins': stats.mafia_wins,
                'civilian_wins': stats.civilian_wins,
                'doctor_saves': stats.doctor_saves,
                'detective_investigations': stats.detective_investigations,
                'successful_kills': stats.successful_kills,
                'successful_votes': stats.successful_votes,
                'survival_count': stats.survival_count,
                'best_win_streak': stats.best_win_streak,
                'current_win_streak': stats.current_win_streak,
                'mvp_count': stats.mvp_count,
            },
            'achievements': achievements_data,
            'inventory': inventory_data,
        })


class LeaderboardView(APIView):
    """Retrieve global leaderboards across multiple categories."""
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        category = request.query_params.get('category', 'wins')
        limit = int(request.query_params.get('limit', 20))
        limit = min(max(limit, 1), 100)

        results = StatsService.get_leaderboard(category=category, limit=limit)
        return Response({
            'category': category,
            'leaderboard': results
        })


class GroupTop20PlayersView(APIView):
    """Retrieve top 20 best players in the group."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        top20_stats = PlayerStats.objects.select_related('player_profile').order_by('-games_won', '-win_rate', '-mvp_count')[:20]
        results = []
        for idx, ps in enumerate(top20_stats, 1):
            prof = ps.player_profile
            results.append({
                'rank': idx,
                'full_name': prof.full_name,
                'username': prof.telegram_username or f"user_{prof.telegram_id}",
                'games_played': ps.games_played,
                'games_won': ps.games_won,
                'win_rate': ps.win_rate,
                'mvp_count': ps.mvp_count,
            })
        return Response({
            'group_name': request.user.effective_owner.group_name or f"{request.user.effective_owner.username}'s Group",
            'top20_players': results
        })
