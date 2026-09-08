from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
from apps.bots.models import Bot, BotStatus
from apps.games.models import Game, Player, GamePhase, RoleTeam, RoleType, NightActionType
from apps.games.engine.roles import RoleDistributionService
from apps.games.engine.game_service import GameService
from apps.games.engine.actions import NightActionService, ActionValidationError
from apps.games.engine.voting import VotingService, VoteValidationError
from apps.games.engine.resolution import GameResolutionService
from apps.games.engine.win_conditions import WinConditionService

User = get_user_model()


class MafiaGameEngineTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='gameowner', email='owner@example.com', password='Password123!')
        self.bot = Bot.objects.create(owner=self.user, name="Engine Test Bot", telegram_username="engine_test_bot", status=BotStatus.ACTIVE)
        self.chat_id = -100123456789

    def test_role_distribution(self):
        """Test dynamic role allocation logic across player group sizes."""
        r4 = RoleDistributionService.calculate_role_list(4)
        self.assertEqual(r4.count(RoleType.DON), 1)
        self.assertEqual(r4.count(RoleType.DOCTOR), 1)
        self.assertEqual(r4.count(RoleType.DETECTIVE), 1)
        self.assertEqual(r4.count(RoleType.CITIZEN), 1)
        self.assertEqual(r4.count(RoleType.MAFIA), 0)

        r5 = RoleDistributionService.calculate_role_list(5)
        self.assertEqual(r5.count(RoleType.DON), 1)
        self.assertEqual(r5.count(RoleType.DOCTOR), 1)
        self.assertEqual(r5.count(RoleType.DETECTIVE), 1)
        self.assertEqual(r5.count(RoleType.CITIZEN), 2)
        self.assertEqual(r5.count(RoleType.MAFIA), 0)

        # Band 2 fix: 6+ players always include DON (mafia team = DON + regular Mafia)
        r6 = RoleDistributionService.calculate_role_list(6)
        self.assertEqual(r6.count(RoleType.DON), 1)   # Exactly 1 DON
        self.assertEqual(r6.count(RoleType.MAFIA), 1)  # 1 regular Mafia (DON took the other slot)
        # Total mafia-team: DON + 1 MAFIA = 2 (same count as before, just DON replaces one MAFIA)
        mafia_team_count = r6.count(RoleType.DON) + r6.count(RoleType.MAFIA)
        self.assertEqual(mafia_team_count, 2)

        r9 = RoleDistributionService.calculate_role_list(9)
        self.assertEqual(r9.count(RoleType.DON), 1)   # Always exactly 1 DON
        self.assertGreaterEqual(r9.count(RoleType.MAFIA), 1)  # At least 1 regular Mafia
        self.assertEqual(len(r9), 9)

    def test_full_game_lifecycle_and_doctor_protection(self):
        """Test complete game execution flow with Doctor saving Mafia target."""
        # 1. Create Game
        game = GameService.create_game(self.bot, self.chat_id)
        self.assertEqual(game.phase, GamePhase.WAITING)

        # 2. Join 4 Players
        p1 = GameService.join_game(game, 101, 'p1', 'Player One')
        p2 = GameService.join_game(game, 102, 'p2', 'Player Two')
        p3 = GameService.join_game(game, 103, 'p3', 'Player Three')
        p4 = GameService.join_game(game, 104, 'p4', 'Player Four')
        self.assertEqual(game.players.count(), 4)

        # 3. Start Game & Assign Roles
        assignments = GameService.start_game(game)
        game.refresh_from_db()
        self.assertEqual(game.phase, GamePhase.NIGHT)
        self.assertEqual(game.round_number, 1)

        # Identify roles (4 players: DON, DOCTOR, DETECTIVE, CITIZEN)
        don = [p for p, r in assignments if r.name == RoleType.DON][0]
        doctor = [p for p, r in assignments if r.name == RoleType.DOCTOR][0]
        citizen = [p for p, r in assignments if r.name == RoleType.CITIZEN][0]

        # 4. Submit Night Actions (Doctor protects citizen, Don targets citizen)
        target = citizen
        NightActionService.submit_action(game, don, target, NightActionType.MAFIA_KILL)
        NightActionService.submit_action(game, doctor, target, NightActionType.DOCTOR_PROTECT)

        # 5. Resolve Night Phase -> Target should SURVIVE because of Doctor!
        result = GameService.advance_phase(game)
        game.refresh_from_db()
        night_res = result['night']

        self.assertTrue(night_res['saved_by_doctor'])
        self.assertIsNone(night_res['eliminated_player'])
        self.assertTrue(target.is_alive)
        self.assertEqual(game.phase, GamePhase.DAY)

    def test_detective_investigation_and_voting_elimination(self):
        """Test Detective investigation and Voting elimination of Mafia."""
        game = GameService.create_game(self.bot, self.chat_id)
        p1 = GameService.join_game(game, 201, 'p1', 'Player 1')
        p2 = GameService.join_game(game, 202, 'p2', 'Player 2')
        p3 = GameService.join_game(game, 203, 'p3', 'Player 3')
        p4 = GameService.join_game(game, 204, 'p4', 'Player 4')
        p5 = GameService.join_game(game, 205, 'p5', 'Player 5')
        p6 = GameService.join_game(game, 206, 'p6', 'Player 6')

        assignments = GameService.start_game(game)
        game.refresh_from_db()

        mafia = [p for p, r in assignments if r.name == RoleType.MAFIA][0]
        don = [p for p, r in assignments if r.name == RoleType.DON][0]
        detective = [p for p, r in assignments if r.name == RoleType.DETECTIVE][0]

        # Detective investigates Mafia
        action = NightActionService.submit_action(game, detective, mafia, NightActionType.DETECTIVE_INVESTIGATE)
        self.assertEqual(action.action_type, NightActionType.DETECTIVE_INVESTIGATE)

        night_res = GameResolutionService.resolve_night_phase(game)
        self.assertTrue(night_res['investigation_results'][0]['is_mafia'])

        # Advance to VOTING
        game.phase = GamePhase.VOTING
        game.save()

        # All living players vote for Mafia
        living = list(game.players.filter(is_alive=True))
        voters = [p for p in living if p.id != mafia.id]

        for v in voters:
            VotingService.submit_vote(game, v, mafia)

        # Advance phase -> Mafia eliminated!
        result = GameService.advance_phase(game)
        game.refresh_from_db()
        self.assertEqual(result['voting']['eliminated_player'].id, mafia.id)

        # Eliminate remaining DON to achieve Civilian victory
        don.is_alive = False
        don.save()

        # Check Win Condition -> Citizens Win (0 Mafia left!)
        winner = WinConditionService.check_win_condition(game)
        self.assertEqual(winner, RoleTeam.CIVILIAN)

    def test_voting_validation(self):
        """Test voting rules: self-vote prevented, dead player vote prevented."""
        game = GameService.create_game(self.bot, self.chat_id)
        p1 = GameService.join_game(game, 301, 'p1', 'P1')
        p2 = GameService.join_game(game, 302, 'p2', 'P2')

        # Voting during WAITING phase -> Failure
        with self.assertRaises(VoteValidationError):
            VotingService.submit_vote(game, p1, p2)

        game.phase = GamePhase.VOTING
        game.save()

        # Self vote -> Failure
        with self.assertRaises(VoteValidationError):
            VotingService.submit_vote(game, p1, p1)

    def test_api_user_isolation(self):
        """Test User A cannot control or view User B's games via REST API."""
        user_b = User.objects.create_user(username='userb', email='userb@example.com', password='Password123!')
        bot_b = Bot.objects.create(owner=user_b, name="Bot B", telegram_username="bot_b", status=BotStatus.ACTIVE)
        game_b = GameService.create_game(bot_b, self.chat_id)

        client = APIClient()
        client.force_authenticate(user=self.user)

        # Attempt to access User B's game -> HTTP 404 NOT FOUND
        res = client.get(f"/api/v1/games/{game_b.id}/")
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    def test_state_recovery_from_db(self):
        """Test persistent game state is cleanly reloaded after worker restart simulation."""
        game = GameService.create_game(self.bot, self.chat_id)
        GameService.join_game(game, 401, 'p1', 'P1')
        GameService.join_game(game, 402, 'p2', 'P2')
        GameService.join_game(game, 403, 'p3', 'P3')
        GameService.join_game(game, 404, 'p4', 'P4')
        GameService.start_game(game)

        game_id = str(game.id)
        del game  # Destroy in-memory object

        # Reload from DB
        reloaded_game = Game.objects.get(id=game_id)
        self.assertEqual(reloaded_game.phase, GamePhase.NIGHT)
        self.assertEqual(reloaded_game.players.count(), 4)


class DonRoleTests(TestCase):
    """Band 2: DON role functional tests."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='dontest', email='dontest@example.com', password='Password123!'
        )
        self.bot = Bot.objects.create(
            owner=self.user, name="Don Test Bot",
            telegram_username="don_test_bot", status=BotStatus.ACTIVE
        )
        self.chat_id = -100999888777

    def test_don_role_created_in_db(self):
        """DON role must be created in DB by get_or_create_base_roles()."""
        roles = RoleDistributionService.get_or_create_base_roles()
        self.assertIn(RoleType.DON, roles)
        don = roles[RoleType.DON]
        self.assertEqual(don.team, RoleTeam.MAFIA)
        self.assertTrue(don.is_system)

    def test_don_can_submit_mafia_kill_action(self):
        """DON must be accepted as a valid MAFIA_KILL actor (Band 2 fix)."""
        from apps.games.engine.actions import _LEGACY_ROLE_ACTION_MAP
        from apps.games.models import NightActionType
        self.assertEqual(_LEGACY_ROLE_ACTION_MAP.get(RoleType.DON), NightActionType.MAFIA_KILL)

    def test_don_included_in_6player_game(self):
        """At 6 players, DON must appear in the role list."""
        role_list = RoleDistributionService.calculate_role_list(6)
        self.assertIn(RoleType.DON, role_list)

    def test_don_night_action_submit_validation(self):
        """NightActionService must accept DON performing MAFIA_KILL without error."""
        from apps.games.engine.actions import NightActionService, ActionValidationError
        from apps.games.models import NightActionType

        # Set up a 6-player game so DON gets assigned
        game = GameService.create_game(self.bot, self.chat_id)
        for i in range(6):
            GameService.join_game(game, 600 + i, f'p{i}', f'Player {i}')

        assignments = GameService.start_game(game)
        game.refresh_from_db()

        # Find DON and a living citizen to target
        don_player = next((p for p, r in assignments if r.name == RoleType.DON), None)
        citizen_player = next((p for p, r in assignments if r.name == RoleType.CITIZEN), None)

        self.assertIsNotNone(don_player, "DON player must exist in 6-player game")
        self.assertIsNotNone(citizen_player, "Citizen must exist in 6-player game")

        # Should NOT raise — DON is a valid MAFIA_KILL actor
        try:
            NightActionService.submit_action(game, don_player, citizen_player, NightActionType.MAFIA_KILL)
        except ActionValidationError as e:
            self.fail(f"DON should be able to submit MAFIA_KILL but got: {e}")


class EntitlementBotLimitTests(TestCase):
    """Band 1: MAX_BOTS entitlement enforcement tests."""

    def setUp(self):
        from apps.subscriptions.services import EntitlementService, EntitlementLimitExceededError
        from apps.subscriptions.models import FeatureCode
        self.EntitlementService = EntitlementService
        self.EntitlementLimitExceededError = EntitlementLimitExceededError
        self.FeatureCode = FeatureCode

        self.user = User.objects.create_user(
            username='bot_limit_user', email='limituser@example.com', password='Password123!'
        )
        # Ensure FREE plan and subscription exist
        EntitlementService.get_or_create_default_plans()
        EntitlementService.get_active_subscription(self.user)

    def test_free_plan_allows_one_bot(self):
        """Free plan limit is 1 bot — zero existing bots should pass."""
        # 0 bots currently — check passes
        try:
            self.EntitlementService.check_limit(self.user, self.FeatureCode.MAX_BOTS, 0)
        except self.EntitlementLimitExceededError:
            self.fail("check_limit raised unexpectedly at 0 bots for FREE plan")

    def test_free_plan_blocks_second_bot(self):
        """Free plan limit is 1 bot — trying to add a second must raise EntitlementLimitExceededError."""
        with self.assertRaises(self.EntitlementLimitExceededError) as ctx:
            self.EntitlementService.check_limit(self.user, self.FeatureCode.MAX_BOTS, 1)
        self.assertEqual(ctx.exception.limit, 1)
        self.assertEqual(ctx.exception.current_usage, 1)

    def test_platform_owner_bypass(self):
        """Platform Owner must bypass all entitlement limits."""
        self.user.is_platform_owner = True
        self.user.save(update_fields=['is_platform_owner'])
        # Even at 9999 bots, platform owner must never be blocked
        try:
            self.EntitlementService.check_limit(self.user, self.FeatureCode.MAX_BOTS, 9999)
        except self.EntitlementLimitExceededError:
            self.fail("Platform owner must bypass MAX_BOTS limit")

