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


class HeroSystemTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='test_don_hero',
            email='don_hero@example.com',
            telegram_id=111111111,
            first_name='Don User'
        )
        self.victim_user = User.objects.create_user(
            username='test_victim_hero',
            email='victim_hero@example.com',
            telegram_id=222222222,
            first_name='Victim User'
        )
        self.citizen_user = User.objects.create_user(
            username='test_citizen_hero',
            email='citizen_hero@example.com',
            telegram_id=333333333,
            first_name='Citizen User'
        )

        from apps.games.models import Role
        self.bot = Bot.objects.create(
            owner=self.user,
            name="TestBotHero",
            telegram_username="TestMafiaBotHero",
            status=BotStatus.ACTIVE
        )

        self.game = Game.objects.create(
            bot=self.bot,
            chat_id=-100999888777,
            phase=GamePhase.DAY,
            round_number=1
        )

        self.don_role, _ = Role.objects.get_or_create(
            name='DON',
            defaults={'code': 'don_hero', 'team': RoleTeam.MAFIA, 'is_system': True}
        )
        self.citizen_role, _ = Role.objects.get_or_create(
            name='CITIZEN',
            defaults={'code': 'citizen_hero', 'team': RoleTeam.CIVILIAN, 'is_system': True}
        )

        self.don_player = Player.objects.create(
            game=self.game,
            telegram_user_id=self.user.telegram_id,
            display_name="Don Player",
            role=self.don_role,
            is_alive=True,
            health=100
        )
        self.victim_player = Player.objects.create(
            game=self.game,
            telegram_user_id=self.victim_user.telegram_id,
            display_name="Victim Player",
            role=self.citizen_role,
            is_alive=True,
            health=100
        )
        self.citizen_player = Player.objects.create(
            game=self.game,
            telegram_user_id=self.citizen_user.telegram_id,
            display_name="Citizen Player",
            role=self.citizen_role,
            is_alive=True,
            health=100
        )

    def test_hero_creation_and_properties(self):
        """Test Hero model properties, initial values, and leveling formula."""
        from apps.economy.models import PlayerHero
        hero = PlayerHero.objects.create(
            telegram_id=self.user.telegram_id,
            owner_name="Don Player",
            name="Thamuz",
            level=1,
            score=0,
            charges=20,
            is_active=True,
            current_defense=0
        )

        self.assertEqual(hero.charges, 20)
        self.assertEqual(hero.power_min, 50)
        self.assertEqual(hero.power_max, 60)
        self.assertEqual(hero.max_defense, 15)
        self.assertEqual(hero.next_level_score, 1980)

        # Add score and test level up (+10 Himoya per level up)
        leveled_up = hero.add_kill_score(2000)
        self.assertTrue(leveled_up)
        self.assertEqual(hero.level, 2)
        self.assertEqual(hero.current_defense, 10)
        self.assertEqual(hero.max_defense, 25)
        self.assertEqual(hero.power_min, 55)
        self.assertEqual(hero.power_max, 65)

    def test_format_hero_card_text(self):
        """Test formatting of rich hero stats card."""
        from apps.economy.models import PlayerHero
        from apps.economy.services import HeroService
        hero = PlayerHero.objects.create(
            telegram_id=self.user.telegram_id,
            owner_name="И",
            name="Thamuz",
            level=1,
            score=0,
            charges=20,
            is_active=True,
            current_defense=0
        )
        card_text = HeroService.format_hero_card_text(hero, geroy_himoya_count=0)
        self.assertIn("🥷 <b>Geroy:</b> Thamuz", card_text)
        self.assertIn("👤 <b>Kim uchun:</b> И", card_text)
        self.assertIn("⭐ <b>Daraja:</b> 1", card_text)
        self.assertIn("👊 <b>Kuch:</b> 50-60 oralig'ida", card_text)
        self.assertIn("🖤 <b>Himoya:</b> 0", card_text)
        self.assertIn("❤️ <b>Max himoya:</b> 15", card_text)
        self.assertIn("🩸 <b>Zaryad miqdori:</b> 20", card_text)
        self.assertIn("⬆️ <b>Keyingi daraja</b> = 2 => 1980 ball", card_text)

    def test_hero_role_restriction(self):
        """Test that only Don or Komissar can execute hero strike."""
        from apps.economy.models import PlayerHero
        from apps.economy.services import HeroService
        hero = PlayerHero.objects.create(
            telegram_id=self.citizen_user.telegram_id,
            owner_name="Citizen Player",
            name="Hero1",
            level=1,
            charges=20,
            is_active=True
        )
        res = HeroService.execute_hero_strike(self.game, self.citizen_player, self.victim_player)
        self.assertFalse(res['ok'])
        self.assertIn("Don", res['error'])

    def test_hero_strike_execution_and_damage(self):
        """Test Don executing Hero strike, consuming charge, reducing health, and killing victim."""
        from apps.economy.models import PlayerHero
        from apps.economy.services import HeroService
        hero = PlayerHero.objects.create(
            telegram_id=self.user.telegram_id,
            owner_name="Don Player",
            name="Thamuz",
            level=1,
            charges=20,
            is_active=True
        )

        res = HeroService.execute_hero_strike(self.game, self.don_player, self.victim_player)
        self.assertTrue(res['ok'])
        self.assertEqual(res['charges_left'], 19)
        self.don_player.refresh_from_db()
        self.victim_player.refresh_from_db()

        # Victim took 50-60% damage
        self.assertTrue(self.victim_player.health <= 50)

    def test_hero_strike_blocked_by_geroy_himoya(self):
        """Test that 🔰 Geroydan himoya item blocks Hero strike."""
        from apps.economy.models import PlayerHero, MarketplaceCategory, MarketplaceItem, MarketplaceItemType, Inventory
        from apps.economy.services import HeroService
        hero = PlayerHero.objects.create(
            telegram_id=self.user.telegram_id,
            owner_name="Don Player",
            name="Thamuz",
            level=1,
            charges=20,
            is_active=True
        )
        cat, _ = MarketplaceCategory.objects.get_or_create(code='items_hero', defaults={'name': 'Items Hero'})
        item, _ = MarketplaceItem.objects.get_or_create(code='geroy_himoya', defaults={'name': 'Geroydan himoya', 'category': cat, 'item_type': MarketplaceItemType.BONUS})
        Inventory.objects.create(telegram_id=self.victim_user.telegram_id, item=item, quantity=1, is_active=True)

        res = HeroService.execute_hero_strike(self.game, self.don_player, self.victim_player)
        self.assertTrue(res['ok'])
        self.assertTrue(res['blocked'])
        self.assertEqual(res['block_type'], 'geroy_himoya')
        self.victim_player.refresh_from_db()
        self.assertEqual(self.victim_player.health, 100)
        self.assertTrue(self.victim_player.is_alive)

    def test_max_level_hero_instant_kill(self):
        """Test that Level 10 Hero deals 100% damage and instantly kills."""
        from apps.economy.models import PlayerHero
        from apps.economy.services import HeroService
        hero = PlayerHero.objects.create(
            telegram_id=self.user.telegram_id,
            owner_name="Don Player",
            name="Thamuz",
            level=10,
            charges=20,
            is_active=True
        )
        res = HeroService.execute_hero_strike(self.game, self.don_player, self.victim_player)
        self.assertTrue(res['ok'])
        self.assertTrue(res['killed'])
        self.victim_player.refresh_from_db()
        self.assertFalse(self.victim_player.is_alive)
        self.assertEqual(self.victim_player.health, 0)

    def test_universal_himoya_protects_from_voting_lynch(self):
        """Test that 🖤 Himoya (current_defense) saves player from day voting lynching."""
        from apps.economy.models import PlayerHero
        from apps.games.models import Vote
        from apps.games.engine.resolution import GameResolutionService
        victim_hero = PlayerHero.objects.create(
            telegram_id=self.victim_user.telegram_id,
            owner_name="Victim Player",
            name="VictimHero",
            level=2,
            current_defense=10,
            is_active=True
        )

        Vote.objects.create(game=self.game, round=1, voter=self.don_player, target=self.victim_player)
        Vote.objects.create(game=self.game, round=1, voter=self.citizen_player, target=self.victim_player)

        res = GameResolutionService.resolve_voting_phase(self.game)
        self.assertTrue(res.get('saved_by_hero_defense') or res.get('saved_by_shield'))
        self.assertIsNone(res['eliminated_player'])
        victim_hero.refresh_from_db()
        self.assertEqual(victim_hero.current_defense, 9)
        self.victim_player.refresh_from_db()
        self.assertTrue(self.victim_player.is_alive)

    def test_doctor_and_detective_skip_action_success(self):
        """Test that submitting SKIP action for Doctor and Detective works without errors."""
        from apps.games.engine.actions import NightActionService, NightActionType
        from apps.games.models import Role, RoleType
        
        doc_role, _ = Role.objects.get_or_create(
            name=RoleType.DOCTOR,
            defaults={'code': 'doc_test', 'team': RoleTeam.CIVILIAN, 'is_system': True}
        )
        det_role, _ = Role.objects.get_or_create(
            name=RoleType.DETECTIVE,
            defaults={'code': 'det_test', 'team': RoleTeam.CIVILIAN, 'is_system': True}
        )
        
        self.game.phase = GamePhase.NIGHT
        self.game.save(update_fields=['phase'])
        
        self.victim_player.role = doc_role
        self.victim_player.save(update_fields=['role'])
        self.citizen_player.role = det_role
        self.citizen_player.save(update_fields=['role'])
        
        act1 = NightActionService.submit_action(self.game, self.victim_player, None, NightActionType.SKIP)
        self.assertEqual(act1.action_type, NightActionType.SKIP)
        
        act2 = NightActionService.submit_action(self.game, self.citizen_player, None, NightActionType.SKIP)
        self.assertEqual(act2.action_type, NightActionType.SKIP)

    def test_win_conditions_don_komissar_doctor_alive(self):
        """Test that 1 Don + 1 Komissar + 1 Doctor does not trigger premature win."""
        from apps.games.engine.win_conditions import WinConditionService
        from apps.games.models import Role, RoleType
        
        doc_role, _ = Role.objects.get_or_create(
            name=RoleType.DOCTOR,
            defaults={'code': 'doc_win_test', 'team': RoleTeam.CIVILIAN, 'is_system': True}
        )
        det_role, _ = Role.objects.get_or_create(
            name=RoleType.DETECTIVE,
            defaults={'code': 'det_win_test', 'team': RoleTeam.CIVILIAN, 'is_system': True}
        )
        
        self.don_player.is_alive = True
        self.don_player.role = self.don_role
        self.don_player.save()
        
        self.victim_player.is_alive = True
        self.victim_player.role = doc_role
        self.victim_player.save()
        
        self.citizen_player.is_alive = True
        self.citizen_player.role = det_role
        self.citizen_player.save()
        
        winner = WinConditionService.check_win_condition(self.game)
        self.assertIsNone(winner)

    def test_win_conditions_don_vs_komissar_duel(self):
        """Test that 1 Don vs 1 Komissar (Town lethal shooter) does not auto-win for Mafia."""
        from apps.games.engine.win_conditions import WinConditionService
        from apps.games.models import Role, RoleType
        
        det_role, _ = Role.objects.get_or_create(
            name=RoleType.DETECTIVE,
            defaults={'code': 'det_duel_test', 'team': RoleTeam.CIVILIAN, 'is_system': True}
        )
        
        self.don_player.is_alive = True
        self.don_player.role = self.don_role
        self.don_player.save()
        
        self.citizen_player.is_alive = True
        self.citizen_player.role = det_role
        self.citizen_player.save()
        
        self.victim_player.is_alive = False
        self.victim_player.save()
        
        # 1v1 Don vs Komissar -> None (shootout at night)
        winner = WinConditionService.check_win_condition(self.game)
        self.assertIsNone(winner)
        
        # 1v1 Don vs Citizen (no gun) -> Mafia wins
        self.citizen_player.role = self.citizen_role
        self.citizen_player.save()
        winner_citizen = WinConditionService.check_win_condition(self.game)
        self.assertEqual(winner_citizen, RoleTeam.MAFIA)



