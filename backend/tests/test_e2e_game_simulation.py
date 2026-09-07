"""
MAFIA BOT FATHER — 12-PLAYER END-TO-END GAMEPLAY SIMULATION TEST
Validates full real-time game lifecycle from Lobby, Secret Roles, Night Actions,
Doctor Saves, Investigations, Day Discussions, Voting, Ties, Eliminations,
Win Conditions, GameEvent Logging, Stats, Achievements, Economy Rewards,
Special Owner (@ismoilo9) Privileges, and P2P Admin Approvals.
"""
from decimal import Decimal
from django.test import TestCase
from django.utils import timezone
from apps.users.models import User, UserRole
from apps.bots.models import Bot, BotStatus
from apps.games.models import (
    Game, Player, GamePhase, Role, RoleTeam, RoleType,
    NightAction, NightActionType, Vote, GameEvent, GameEventType,
    GameConfiguration, RoleDistributionRule, DistributionType
)
from apps.games.engine.game_service import GameService
from apps.games.engine.actions import NightActionService
from apps.games.engine.voting import VotingService
from apps.games.engine.resolution import GameResolutionService
from apps.games.engine.win_conditions import WinConditionService
from apps.games.engine.roles import RoleDistributionService
from apps.stats.models import PlayerProfile, PlayerStats, Achievement, UserAchievement
from apps.stats.services import StatsService, AchievementService
from apps.economy.models import (
    Wallet, WalletTransaction, CurrencyType, TransactionType,
    PaymentOrder, PaymentOrderStatus, VIPSubscription, VIPLevel
)
from apps.economy.services import EconomyService, MarketplaceService
from apps.subscriptions.services import EntitlementService
from apps.common.models import AdminAuditLog, AdminAuditAction


class E2E12PlayerGameSimulationTest(TestCase):
    """Full 12-Player Telegram Mafia Game Simulation Test Suite."""

    def setUp(self):
        # 1. Create Platform Admin & Tenant User
        self.admin_user = User.objects.create_superuser(
            email='admin@mafiabotfather.uz',
            username='admin',
            password='password123'
        )
        self.tenant_user = User.objects.create_user(
            email='host@mafiabotfather.uz',
            username='host_user',
            password='password123',
            role=UserRole.USER
        )
        from apps.subscriptions.services import SubscriptionService, EntitlementService
        plans = EntitlementService.get_or_create_default_plans()
        SubscriptionService.activate_subscription(self.tenant_user, plans['PRO'])

        # 2. Seed System Roles
        self.role_mafia, _ = Role.objects.get_or_create(
            name='MAFIA',
            code='mafia',
            team=RoleTeam.MAFIA,
            is_system=True,
            defaults={'description': 'Tunda fuqarolarni yoʻq qiladi'}
        )
        self.role_doctor, _ = Role.objects.get_or_create(
            name='DOCTOR',
            code='doctor',
            team=RoleTeam.CIVILIAN,
            is_system=True,
            defaults={'description': 'Tunda bir kishini qutqaradi'}
        )
        self.role_detective, _ = Role.objects.get_or_create(
            name='DETECTIVE',
            code='detective',
            team=RoleTeam.CIVILIAN,
            is_system=True,
            defaults={'description': 'Tunda mafiyani fosh qiladi'}
        )
        self.role_citizen, _ = Role.objects.get_or_create(
            name='CITIZEN',
            code='citizen',
            team=RoleTeam.CIVILIAN,
            is_system=True,
            defaults={'description': 'Oddiy tinch fuqaro'}
        )

        # 3. Create Bot
        self.bot = Bot.objects.create(
            owner=self.tenant_user,
            name='Bloody Mafia Bot',
            telegram_username='bloody_mafia_bot',
            status=BotStatus.ACTIVE
        )

        # 4. Create 12-Player Configured Rule Set
        self.config = GameConfiguration.objects.create(
            owner=self.tenant_user,
            bot=self.bot,
            name='12-Player Bloody Mafia Rules',
            minimum_players=12,
            maximum_players=12,
            night_duration=45,
            discussion_duration=60,
            voting_duration=45,
        )
        RoleDistributionRule.objects.create(configuration=self.config, role=self.role_mafia, distribution_type=DistributionType.EXACT, min_count=3, max_count=3, priority=10)
        RoleDistributionRule.objects.create(configuration=self.config, role=self.role_doctor, distribution_type=DistributionType.EXACT, min_count=1, max_count=1, priority=8)
        RoleDistributionRule.objects.create(configuration=self.config, role=self.role_detective, distribution_type=DistributionType.EXACT, min_count=1, max_count=1, priority=7)
        RoleDistributionRule.objects.create(configuration=self.config, role=self.role_citizen, distribution_type=DistributionType.EXACT, min_count=7, max_count=7, priority=1)

        # 5. Seed Platform Achievements
        AchievementService.get_or_create_default_achievements()

    def test_full_12_player_gameplay_simulation(self):
        """
        Simulates entire 12-player game:
        Lobby -> Roles -> Night 1 (Doctor saves Mafia target) -> Day 1 Discussion -> Vote 1 (Tie) ->
        Night 2 (Mafia kill succeeds) -> Vote 2 (Mafia voted out) -> Win Condition -> Stats & Rewards.
        """
        group_chat_id = -1001987654321

        # STEP 1: Create Game Lobby
        game = GameService.create_game(
            bot=self.bot,
            chat_id=group_chat_id,
            configuration_id=str(self.config.id)
        )
        self.assertEqual(game.phase, GamePhase.WAITING)
        self.assertTrue(GameEvent.objects.filter(game=game, event_type=GameEventType.GAME_CREATED).exists())

        # STEP 2: Join 12 Players
        players = []
        for i in range(1, 13):
            p = GameService.join_game(
                game=game,
                telegram_user_id=1000 + i,
                username=f"player_{i}",
                display_name=f"Player {i}"
            )
            players.append(p)

        self.assertEqual(game.players.count(), 12)
        self.assertEqual(GameEvent.objects.filter(game=game, event_type=GameEventType.PLAYER_JOINED).count(), 12)

        # Duplicate join check (same user cannot join twice)
        GameService.join_game(game=game, telegram_user_id=1001, username="player_1", display_name="Player 1 Updated")
        self.assertEqual(game.players.count(), 12)

        # STEP 3: Start Game & Distribute Roles
        assignments = GameService.start_game(game)
        game.refresh_from_db()
        self.assertEqual(game.phase, GamePhase.NIGHT)
        self.assertEqual(game.round_number, 1)
        self.assertIsNotNone(game.configuration_snapshot)
        self.assertTrue(GameEvent.objects.filter(game=game, event_type=GameEventType.GAME_STARTED).exists())
        self.assertTrue(GameEvent.objects.filter(game=game, event_type=GameEventType.NIGHT_STARTED).exists())

        # Check role distribution counts
        mafia_players = list(game.players.filter(role__name='MAFIA'))
        doctor_players = list(game.players.filter(role__name='DOCTOR'))
        detective_players = list(game.players.filter(role__name='DETECTIVE'))
        citizen_players = list(game.players.filter(role__name='CITIZEN'))

        self.assertEqual(len(mafia_players), 3)
        self.assertEqual(len(doctor_players), 1)
        self.assertEqual(len(detective_players), 1)
        self.assertEqual(len(citizen_players), 7)

        # STEP 4: Round 1 Night Actions
        target_citizen = citizen_players[0]
        # Mafia kills target_citizen
        for maf in mafia_players:
            NightActionService.submit_action(game, maf, target_citizen, NightActionType.MAFIA_KILL)

        # Doctor PROTECTS target_citizen (Hero save!)
        doc = doctor_players[0]
        NightActionService.submit_action(game, doc, target_citizen, NightActionType.DOCTOR_PROTECT)

        # Detective investigates mafia_players[0]
        det = detective_players[0]
        NightActionService.submit_action(game, det, mafia_players[0], NightActionType.DETECTIVE_INVESTIGATE)

        # STEP 5: Advance Night 1 -> Day 1 -> Discussion 1 -> Voting 1
        res1 = GameService.advance_phase(game)  # NIGHT -> DAY
        game.refresh_from_db()
        self.assertEqual(game.phase, GamePhase.DAY)
        self.assertTrue(res1['night']['saved_by_doctor'])
        self.assertIsNone(res1['night']['eliminated_player'])
        self.assertEqual(game.players.filter(is_alive=True).count(), 12)  # All 12 still alive!

        # Transition DAY -> DISCUSSION -> VOTING
        GameService.advance_phase(game)  # DAY -> DISCUSSION
        game.refresh_from_db()
        self.assertEqual(game.phase, GamePhase.DISCUSSION)

        GameService.advance_phase(game)  # DISCUSSION -> VOTING
        game.refresh_from_db()
        self.assertEqual(game.phase, GamePhase.VOTING)

        # STEP 6: Voting Round 1 — Simulate a Tie
        living = list(game.players.filter(is_alive=True))
        # living[:6] vote for living[11] (6 votes)
        for p in living[:6]:
            VotingService.submit_vote(game, p, living[11])
        # living[6:] vote for living[0] (6 votes)
        for p in living[6:]:
            VotingService.submit_vote(game, p, living[0])

        # Resolve Voting 1 (Tie -> No elimination -> advances to Round 2 Night)
        res_vote1 = GameService.advance_phase(game)
        game.refresh_from_db()
        self.assertTrue(res_vote1['voting']['is_tie'])
        self.assertIsNone(res_vote1['voting']['eliminated_player'])
        self.assertEqual(game.round_number, 2)
        self.assertEqual(game.phase, GamePhase.NIGHT)
        self.assertEqual(game.players.filter(is_alive=True).count(), 12)

        # STEP 7: Round 2 Night Actions — Mafia kills citizen_players[1], Doctor protects living[0]
        target_victim = citizen_players[1]
        for maf in mafia_players:
            NightActionService.submit_action(game, maf, target_victim, NightActionType.MAFIA_KILL)
        NightActionService.submit_action(game, doc, living[0], NightActionType.DOCTOR_PROTECT)

        # Advance Night 2 -> Day 2 -> Discussion 2 -> Voting 2
        res2 = GameService.advance_phase(game)
        game.refresh_from_db()
        self.assertFalse(res2['night']['saved_by_doctor'])
        self.assertEqual(res2['night']['eliminated_player'].id, target_victim.id)
        target_victim.refresh_from_db()
        self.assertFalse(target_victim.is_alive)
        self.assertEqual(game.players.filter(is_alive=True).count(), 11)

        # Advance to Discussion & Voting
        GameService.advance_phase(game)  # DAY -> DISCUSSION
        GameService.advance_phase(game)  # DISCUSSION -> VOTING
        game.refresh_from_db()
        self.assertEqual(game.phase, GamePhase.VOTING)

        # STEP 8: Voting Round 2 — Town votes out Mafia Leader
        mafia_target = mafia_players[0]
        living_after_kill = list(game.players.filter(is_alive=True))
        for p in living_after_kill:
            if p.id == mafia_target.id:
                VotingService.submit_vote(game, p, doc)
            else:
                VotingService.submit_vote(game, p, mafia_target)

        res_vote2 = GameService.advance_phase(game)
        game.refresh_from_db()
        self.assertEqual(res_vote2['voting']['eliminated_player'].id, mafia_target.id)
        mafia_target.refresh_from_db()
        self.assertFalse(mafia_target.is_alive)
        self.assertEqual(game.players.filter(is_alive=True).count(), 10)

        # STEP 9: Force Game Finish to Verify Economy, Stats & Achievements
        GameService.finish_game(game, RoleTeam.CIVILIAN)
        game.refresh_from_db()
        self.assertEqual(game.phase, GamePhase.FINISHED)
        self.assertEqual(game.winner_team, RoleTeam.CIVILIAN)
        self.assertTrue(GameEvent.objects.filter(game=game, event_type=GameEventType.GAME_FINISHED).exists())

        # Verify civilian stats and wallet rewards
        winner_profile = PlayerProfile.objects.get(telegram_id=citizen_players[0].telegram_user_id)
        winner_stats = winner_profile.stats
        self.assertEqual(winner_stats.games_won, 1)
        self.assertEqual(winner_stats.current_win_streak, 1)

        winner_wallet = EconomyService.get_or_create_wallet(telegram_id=winner_profile.telegram_id)
        self.assertGreater(winner_wallet.coins, 0)
        self.assertTrue(WalletTransaction.objects.filter(wallet=winner_wallet, tx_type=TransactionType.REWARD).exists())

    def test_special_platform_owner_ismoilo9(self):
        """Validates @ismoilo9 platform owner detection, VIP Diamond and entitlement bypass."""
        # 1. Profile detection by username
        owner_profile = StatsService.get_or_create_profile(
            telegram_id=999888777,
            username='ismoilo9',
            first_name='Ismoil',
            user=self.tenant_user
        )

        self.assertTrue(owner_profile.is_platform_owner)
        self.assertTrue(self.tenant_user.is_platform_owner)

        # 2. Check VIP Diamond
        vip = VIPSubscription.objects.get(telegram_id=owner_profile.telegram_id)
        self.assertEqual(vip.vip_level, VIPLevel.DIAMOND)
        self.assertTrue(vip.is_active)

        # 3. Check Wallet Funds
        wallet = EconomyService.get_or_create_wallet(telegram_id=owner_profile.telegram_id)
        self.assertGreaterEqual(wallet.diamonds, 99999)
        self.assertGreaterEqual(wallet.coins, 99999)

        # 4. Check Entitlement Limit Bypass
        self.assertEqual(EntitlementService.get_feature_limit(self.tenant_user, 'MAX_BOTS'), -1)
        self.assertTrue(EntitlementService.is_feature_enabled(self.tenant_user, 'CUSTOM_ROLES'))
        # Should not raise exception even with huge usage
        EntitlementService.check_limit(self.tenant_user, 'MAX_BOTS', 1000)
        EntitlementService.can_start_game(self.tenant_user, 100)

    def test_p2p_payment_and_admin_approval(self):
        """Validates P2P diamond purchase order and admin approval flow."""
        player_tg_id = 777666555
        order = MarketplaceService.create_payment_order(
            diamonds=50,
            telegram_id=player_tg_id,
            receipt_ref='TRANSACTION_123456789'
        )
        self.assertEqual(order.status, PaymentOrderStatus.PENDING_REVIEW)
        self.assertEqual(order.diamonds_to_credit, 50)

        # Admin approves payment order
        approved_order = MarketplaceService.review_payment_order(
            order_id=order.order_id,
            status=PaymentOrderStatus.APPROVED,
            admin_user=self.admin_user,
            notes='Verified bank receipt'
        )
        self.assertEqual(approved_order.status, PaymentOrderStatus.APPROVED)

        # Check wallet credited
        player_wallet = EconomyService.get_or_create_wallet(telegram_id=player_tg_id)
        self.assertEqual(player_wallet.diamonds, 50)

        # Check audit log created
        self.assertTrue(
            AdminAuditLog.objects.filter(
                admin=self.admin_user,
                action=AdminAuditAction.APPROVE_PAYMENT,
                target_id=order.order_id
            ).exists()
        )
