import uuid
from decimal import Decimal
from django.utils import timezone
from django.db.models import Sum, Count, Q
from django.contrib.auth import get_user_model
from rest_framework import viewsets, permissions, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.decorators import action

from apps.common.permissions import IsAdminOrStaffUser
from apps.common.models import AdminAuditLog, AdminAuditAction
from apps.bots.models import Bot, BotStatus, RuntimeStatus
from apps.games.models import Game, GamePhase, Player
from apps.subscriptions.models import Subscription, SubscriptionStatus, Plan
from apps.subscriptions.services import SubscriptionService
from apps.payments.models import Payment, PaymentStatus
from apps.economy.models import (
    Wallet, WalletTransaction, CurrencyType, TransactionType,
    MarketplaceItem, MarketplaceCategory, PaymentOrder, PaymentOrderStatus,
    VIPSubscription, VIPLevel
)
from apps.economy.services import EconomyService, MarketplaceService
from apps.stats.models import PlayerProfile, PlayerStats

User = get_user_model()


class AdminOverviewView(APIView):
    """Provides high-level platform health, revenue, bots, and gameplay statistics."""
    permission_classes = [IsAdminOrStaffUser]

    def get(self, request):
        now = timezone.now()
        start_of_today = now.replace(hour=0, minute=0, second=0, microsecond=0)
        start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        # Users
        total_users = User.objects.count()
        active_users = User.objects.filter(is_active=True, is_suspended=False).count()
        suspended_users = User.objects.filter(is_suspended=True).count()

        # Bots
        total_bots = Bot.objects.count()
        running_bots = Bot.objects.filter(runtime_status=RuntimeStatus.RUNNING).count()
        offline_bots = Bot.objects.filter(runtime_status=RuntimeStatus.OFFLINE).count()
        error_bots = Bot.objects.filter(Q(status=BotStatus.ERROR) | Q(runtime_status=RuntimeStatus.ERROR)).count()
        suspended_bots = Bot.objects.filter(status=BotStatus.SUSPENDED).count()

        # Games
        active_phases = [GamePhase.STARTING, GamePhase.NIGHT, GamePhase.DAY, GamePhase.DISCUSSION, GamePhase.VOTING, GamePhase.ELIMINATION]
        total_games = Game.objects.count()
        active_games = Game.objects.filter(phase__in=active_phases).count()
        finished_games = Game.objects.filter(phase=GamePhase.FINISHED).count()
        games_today = Game.objects.filter(created_at__gte=start_of_today).count()

        # Players
        total_players = PlayerProfile.objects.count()
        online_players = Player.objects.filter(game__phase__in=active_phases).count()

        # Financials / Revenue
        total_rev_agg = Payment.objects.filter(status=PaymentStatus.SUCCEEDED).aggregate(Sum('amount'))
        total_revenue = float(total_rev_agg['amount__sum'] or 0)

        today_rev_agg = Payment.objects.filter(
            status=PaymentStatus.SUCCEEDED,
            paid_at__gte=start_of_today
        ).aggregate(Sum('amount'))
        today_revenue = float(today_rev_agg['amount__sum'] or 0)

        monthly_rev_agg = Payment.objects.filter(
            status=PaymentStatus.SUCCEEDED,
            paid_at__gte=start_of_month
        ).aggregate(Sum('amount'))
        monthly_revenue = float(monthly_rev_agg['amount__sum'] or 0)

        # Economy in circulation
        wallets_agg = Wallet.objects.aggregate(
            total_money=Sum('money'),
            total_diamonds=Sum('diamonds'),
            total_coins=Sum('coins')
        )
        money_in_circ = float(wallets_agg['total_money'] or 0)
        diamonds_in_circ = int(wallets_agg['total_diamonds'] or 0)
        coins_in_circ = int(wallets_agg['total_coins'] or 0)

        # Subscriptions & VIP
        active_subscriptions = Subscription.objects.filter(
            status__in=[SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIALING]
        ).exclude(plan__code='FREE').count()
        vip_users = VIPSubscription.objects.filter(is_active=True, expires_at__gt=now).count()

        return Response({
            'users': {
                'total': total_users,
                'active': active_users,
                'suspended': suspended_users,
            },
            'bots': {
                'total': total_bots,
                'running': running_bots,
                'offline': offline_bots,
                'error': error_bots,
                'suspended': suspended_bots,
            },
            'games': {
                'total': total_games,
                'active': active_games,
                'finished': finished_games,
                'today': games_today,
            },
            'players': {
                'total': total_players,
                'online': online_players,
            },
            'revenue': {
                'total_usd': total_revenue,
                'today_usd': today_revenue,
                'monthly_usd': monthly_revenue,
            },
            'economy': {
                'money_in_circulation': money_in_circ,
                'diamonds_in_circulation': diamonds_in_circ,
                'coins_in_circulation': coins_in_circ,
            },
            'subscriptions': {
                'active_paid_subscriptions': active_subscriptions,
                'vip_users': vip_users,
            },
            'system_health': 'OPERATIONAL',
            'timestamp': now.isoformat(),
        })


class AdminBotViewSet(viewsets.ViewSet):
    """Lists and manages all Telegram bot runtimes across the platform."""
    permission_classes = [IsAdminOrStaffUser]

    def list(self, request):
        status_filter = request.query_params.get('status')
        qs = Bot.objects.select_related('owner').all()
        if status_filter:
            qs = qs.filter(status=status_filter)

        active_phases = [GamePhase.STARTING, GamePhase.NIGHT, GamePhase.DAY, GamePhase.DISCUSSION, GamePhase.VOTING, GamePhase.ELIMINATION]
        results = []
        for bot in qs:
            active_games_count = Game.objects.filter(bot=bot, phase__in=active_phases).count()
            results.append({
                'id': str(bot.id),
                'name': bot.name,
                'username': bot.telegram_username,
                'owner_email': bot.owner.email if bot.owner else 'None',
                'status': bot.status,
                'runtime_status': bot.runtime_status,
                'active_games': active_games_count,
                'created_at': bot.created_at.isoformat() if bot.created_at else None,
                'updated_at': bot.updated_at.isoformat() if bot.updated_at else None,
            })
        return Response(results)

    @action(detail=True, methods=['post'])
    def suspend(self, request, pk=None):
        try:
            bot = Bot.objects.get(id=pk)
            bot.status = BotStatus.SUSPENDED
            bot.runtime_status = RuntimeStatus.OFFLINE
            bot.save(update_fields=['status', 'runtime_status'])
            AdminAuditLog.objects.create(
                admin=request.user,
                action=AdminAuditAction.SUSPEND_BOT,
                target_type='BOT',
                target_id=str(bot.id),
                metadata={'bot_name': bot.name, 'username': bot.telegram_username}
            )
            return Response({'status': 'suspended', 'bot_id': str(bot.id)})
        except Bot.DoesNotExist:
            return Response({'detail': 'Bot not found.'}, status=status.HTTP_404_NOT_FOUND)

    @action(detail=True, methods=['post'])
    def resume(self, request, pk=None):
        try:
            bot = Bot.objects.get(id=pk)
            bot.status = BotStatus.ACTIVE
            bot.save(update_fields=['status'])
            AdminAuditLog.objects.create(
                admin=request.user,
                action=AdminAuditAction.RESUME_BOT,
                target_type='BOT',
                target_id=str(bot.id),
                metadata={'bot_name': bot.name, 'username': bot.telegram_username}
            )
            return Response({'status': 'resumed', 'bot_id': str(bot.id)})
        except Bot.DoesNotExist:
            return Response({'detail': 'Bot not found.'}, status=status.HTTP_404_NOT_FOUND)

    @action(detail=True, methods=['post'])
    def restart(self, request, pk=None):
        try:
            bot = Bot.objects.get(id=pk)
            bot.status = BotStatus.ACTIVE
            bot.runtime_status = RuntimeStatus.RUNNING
            bot.save(update_fields=['status', 'runtime_status'])
            AdminAuditLog.objects.create(
                admin=request.user,
                action=AdminAuditAction.RESTART_BOT,
                target_type='BOT',
                target_id=str(bot.id),
                metadata={'bot_name': bot.name, 'username': bot.telegram_username}
            )
            return Response({'status': 'restarted', 'bot_id': str(bot.id)})
        except Bot.DoesNotExist:
            return Response({'detail': 'Bot not found.'}, status=status.HTTP_404_NOT_FOUND)

    @action(detail=True, methods=['post'])
    def stop(self, request, pk=None):
        try:
            bot = Bot.objects.get(id=pk)
            bot.runtime_status = RuntimeStatus.OFFLINE
            bot.save(update_fields=['runtime_status'])
            return Response({'status': 'stopped', 'bot_id': str(bot.id)})
        except Bot.DoesNotExist:
            return Response({'detail': 'Bot not found.'}, status=status.HTTP_404_NOT_FOUND)


class AdminGameViewSet(viewsets.ViewSet):
    """Provides monitoring across all active and finished Mafia games."""
    permission_classes = [IsAdminOrStaffUser]

    def list(self, request):
        status_filter = request.query_params.get('status')
        qs = Game.objects.select_related('bot', 'owner').prefetch_related('players').all()
        if status_filter:
            qs = qs.filter(status=status_filter)

        results = []
        for g in qs[:100]:
            players = list(g.players.all())
            alive_count = sum(1 for p in players if p.is_alive)
            results.append({
                'id': str(g.id),
                'bot_username': g.bot.username if g.bot else 'Unknown',
                'owner_email': g.owner.email if g.owner else 'Unknown',
                'chat_id': g.chat_id,
                'chat_title': g.chat_title or f"Chat {g.chat_id}",
                'phase': g.phase,
                'round_number': g.round_number,
                'status': g.status,
                'players_count': len(players),
                'alive_count': alive_count,
                'created_at': g.created_at.isoformat() if g.created_at else None,
            })
        return Response(results)


class AdminUserViewSet(viewsets.ViewSet):
    """Administrative user management, wallet balance adjustments, and plan grants."""
    permission_classes = [IsAdminOrStaffUser]

    def list(self, request):
        search = request.query_params.get('search')
        qs = User.objects.prefetch_related('wallet', 'vip_subscription', 'subscription__plan').all()
        if search:
            qs = qs.filter(Q(email__icontains=search) | Q(username__icontains=search))

        results = []
        for u in qs[:100]:
            wallet = getattr(u, 'wallet', None)
            vip = getattr(u, 'vip_subscription', None)
            sub = getattr(u, 'subscription', None)
            results.append({
                'id': str(u.id),
                'email': u.email,
                'username': u.username,
                'role': getattr(u, 'role', 'USER'),
                'is_active': u.is_active,
                'is_suspended': getattr(u, 'is_suspended', False),
                'wallet': {
                    'money': str(wallet.money) if wallet else '0.00',
                    'diamonds': wallet.diamonds if wallet else 0,
                    'coins': wallet.coins if wallet else 0,
                },
                'vip': {
                    'is_active': vip.is_active if vip else False,
                    'level': vip.vip_level if vip else None,
                    'expires_at': vip.expires_at.isoformat() if (vip and vip.expires_at) else None,
                },
                'subscription': {
                    'plan': sub.plan.name if (sub and sub.plan) else 'FREE',
                    'status': sub.status if sub else 'ACTIVE',
                },
                'created_at': u.created_at.isoformat() if u.created_at else None,
            })
        return Response(results)

    @action(detail=True, methods=['post'])
    def suspend(self, request, pk=None):
        try:
            user = User.objects.get(id=pk)
            user.is_suspended = True
            user.is_active = False
            user.save(update_fields=['is_suspended', 'is_active'])
            AdminAuditLog.objects.create(
                admin=request.user,
                action=AdminAuditAction.SUSPEND_USER,
                target_type='USER',
                target_id=str(user.id),
                metadata={'email': user.email}
            )
            return Response({'status': 'suspended', 'user_id': str(user.id)})
        except User.DoesNotExist:
            return Response({'detail': 'User not found.'}, status=status.HTTP_404_NOT_FOUND)

    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        try:
            user = User.objects.get(id=pk)
            user.is_suspended = False
            user.is_active = True
            user.save(update_fields=['is_suspended', 'is_active'])
            AdminAuditLog.objects.create(
                admin=request.user,
                action=AdminAuditAction.ACTIVATE_USER,
                target_type='USER',
                target_id=str(user.id),
                metadata={'email': user.email}
            )
            return Response({'status': 'activated', 'user_id': str(user.id)})
        except User.DoesNotExist:
            return Response({'detail': 'User not found.'}, status=status.HTTP_404_NOT_FOUND)

    @action(detail=True, methods=['post'])
    def grant_vip(self, request, pk=None):
        try:
            user = User.objects.get(id=pk)
            level = request.data.get('vip_level', VIPLevel.GOLD)
            days = int(request.data.get('duration_days', 30))
            vip = MarketplaceService.grant_vip(
                user=user,
                vip_level=level,
                duration_days=days,
                admin_user=request.user
            )
            return Response({
                'status': 'granted',
                'vip_level': vip.vip_level,
                'expires_at': vip.expires_at.isoformat()
            })
        except User.DoesNotExist:
            return Response({'detail': 'User not found.'}, status=status.HTTP_404_NOT_FOUND)

    @action(detail=True, methods=['post'])
    def adjust_balance(self, request, pk=None):
        try:
            user = User.objects.get(id=pk)
            currency = request.data.get('currency', CurrencyType.DIAMONDS)
            amount = Decimal(str(request.data.get('amount', 0)))
            reason = request.data.get('reason', 'Admin adjustment')
            wallet = EconomyService.get_or_create_wallet(user=user)

            if amount > 0:
                tx = EconomyService.credit_wallet(
                    wallet=wallet,
                    currency=currency,
                    amount=amount,
                    tx_type=TransactionType.ADMIN_ADJUSTMENT,
                    description=reason,
                    metadata={'admin': str(request.user.email)}
                )
            elif amount < 0:
                tx = EconomyService.debit_wallet(
                    wallet=wallet,
                    currency=currency,
                    amount=-amount,
                    tx_type=TransactionType.ADMIN_ADJUSTMENT,
                    description=reason,
                    metadata={'admin': str(request.user.email)}
                )
            else:
                return Response({'detail': 'Amount cannot be zero.'}, status=status.HTTP_400_BAD_REQUEST)

            AdminAuditLog.objects.create(
                admin=request.user,
                action=AdminAuditAction.ADJUST_BALANCE,
                target_type='WALLET',
                target_id=str(wallet.id),
                metadata={'user': user.email, 'currency': currency, 'amount': str(amount), 'reason': reason}
            )

            return Response({
                'status': 'success',
                'currency': currency,
                'amount': str(amount),
                'balance_after': str(tx.balance_after)
            })
        except User.DoesNotExist:
            return Response({'detail': 'User not found.'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class AdminPaymentOrderViewSet(viewsets.ViewSet):
    """Review and approve/reject manual P2P payments."""
    permission_classes = [IsAdminOrStaffUser]

    def list(self, request):
        status_filter = request.query_params.get('status')
        qs = PaymentOrder.objects.select_related('user', 'reviewed_by').all()
        if status_filter:
            qs = qs.filter(status=status_filter)

        results = []
        for order in qs[:100]:
            results.append({
                'id': str(order.id),
                'order_id': order.order_id,
                'user_email': order.user.email if order.user else f"TG:{order.telegram_id}",
                'amount_usd': str(order.amount_usd),
                'amount_uzs': str(order.amount_uzs),
                'diamonds_to_credit': order.diamonds_to_credit,
                'payment_method': order.payment_method,
                'status': order.status,
                'receipt_reference': order.receipt_reference,
                'receipt_image_url': order.receipt_image_url,
                'reviewed_by': order.reviewed_by.email if order.reviewed_by else None,
                'reviewed_at': order.reviewed_at.isoformat() if order.reviewed_at else None,
                'admin_notes': order.admin_notes,
                'created_at': order.created_at.isoformat(),
            })
        return Response(results)

    @action(detail=True, methods=['post'])
    def review(self, request, pk=None):
        approve = request.data.get('approve', False)
        admin_notes = request.data.get('admin_notes', '')
        try:
            order = MarketplaceService.review_payment_order(
                order_id=pk,
                admin_user=request.user,
                approve=approve,
                admin_notes=admin_notes
            )
            return Response({
                'order_id': order.order_id,
                'status': order.status,
                'diamonds_credited': order.diamonds_to_credit if approve else 0
            })
        except Exception as e:
            return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class AdminMarketplaceViewSet(viewsets.ModelViewSet):
    """CRUD operations for marketplace items."""
    permission_classes = [IsAdminOrStaffUser]
    queryset = MarketplaceItem.objects.select_related('category').all()

    def list(self, request, *args, **kwargs):
        MarketplaceService.get_or_create_default_categories_and_items()
        qs = self.get_queryset()
        results = []
        for it in qs:
            results.append({
                'id': str(it.id),
                'category': it.category.name,
                'category_code': it.category.code,
                'name': it.name,
                'code': it.code,
                'description': it.description,
                'icon': it.icon,
                'item_type': it.item_type,
                'price_diamonds': it.price_diamonds,
                'price_money_usd': str(it.price_money_usd),
                'diamond_amount': it.diamond_amount,
                'vip_days': it.vip_days,
                'is_active': it.is_active,
            })
        return Response(results)


class AdminAuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    """Immutable audit trail inspection for administrators."""
    permission_classes = [IsAdminOrStaffUser]
    queryset = AdminAuditLog.objects.select_related('admin').all()

    def list(self, request, *args, **kwargs):
        action_filter = request.query_params.get('action')
        qs = self.get_queryset()
        if action_filter:
            qs = qs.filter(action=action_filter)

        results = []
        for log in qs[:100]:
            results.append({
                'id': str(log.id),
                'admin': log.admin.email if log.admin else 'System',
                'action': log.action,
                'target_type': log.target_type,
                'target_id': log.target_id,
                'metadata': log.metadata,
                'result': log.result,
                'created_at': log.created_at.isoformat(),
            })
        return Response(results)
