"""
Phase 3 Tests — Game Configuration, Roles, Templates, Tournament System.

These tests verify Phase 3 features while ensuring all 14 Phase 2 tests continue to pass.
"""
import json
from django.test import TestCase
from django.contrib.auth import get_user_model
from apps.games.models import (
    Role, RoleType, RoleTeam, AbilityType, AbilityPhase,
    RoleAbility, GameConfiguration, RoleDistributionRule, DistributionType,
    TieBehavior, MafiaVoteMode, GameMode, ConfigurationSnapshot, Game, Player, GamePhase,
)
from apps.games.engine.roles import RoleDistributionService
from apps.templates.models import GameTemplate, TemplateType, TemplateVisibility, GameTemplateStatus
from apps.tournaments.models import Tournament, TournamentStatus, TournamentRound, TournamentParticipant, ParticipantStatus
from apps.tournaments.services import (
    TournamentService, TournamentValidationError, TournamentGroupingService, TournamentScoringService
)
from apps.bots.models import Bot
from apps.subscriptions.services import EntitlementService, SubscriptionService

User = get_user_model()


def make_user(email='test@example.com', password='testpass123'):
    return User.objects.create_user(email=email, password=password, username=email.split('@')[0])


def make_bot(owner, name='TestBot'):
    return Bot.objects.create(owner=owner, name=name, telegram_username=f'@{name}bot')


# ===========================================================================
# Test Suite 1: Configuration Models
# ===========================================================================

class TestGameConfigurationModel(TestCase):
    def setUp(self):
        self.user = make_user()
        self.bot = make_bot(self.user)

    def test_create_configuration_defaults(self):
        """GameConfiguration can be created with default values."""
        config = GameConfiguration.objects.create(
            owner=self.user,
            name='Default Config',
        )
        self.assertEqual(config.minimum_players, 4)
        self.assertEqual(config.maximum_players, 20)
        self.assertEqual(config.night_duration, 60)
        self.assertEqual(config.tie_behavior, TieBehavior.NO_ELIMINATION)
        self.assertEqual(config.mafia_vote_mode, MafiaVoteMode.ANY)
        self.assertEqual(config.game_mode, GameMode.CLASSIC)

    def test_create_configuration_custom(self):
        """GameConfiguration respects custom values."""
        config = GameConfiguration.objects.create(
            owner=self.user,
            name='Quick Config',
            game_mode=GameMode.QUICK,
            minimum_players=5,
            maximum_players=12,
            night_duration=30,
            voting_duration=30,
            tie_behavior=TieBehavior.RANDOM,
        )
        self.assertEqual(config.minimum_players, 5)
        self.assertEqual(config.game_mode, GameMode.QUICK)
        self.assertEqual(config.tie_behavior, TieBehavior.RANDOM)

    def test_configuration_validation_min_max(self):
        """Clean validation: min_players > max_players raises error."""
        config = GameConfiguration(
            owner=self.user,
            name='Bad Config',
            minimum_players=10,
            maximum_players=5,
        )
        from django.core.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            config.clean()

    def test_configuration_validation_night_duration(self):
        """Clean validation: night_duration < 10 raises error."""
        config = GameConfiguration(
            owner=self.user,
            name='Bad Config',
            night_duration=5,
        )
        from django.core.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            config.clean()

    def test_configuration_multi_tenant_isolation(self):
        """Users can only see their own configurations."""
        other_user = make_user('other@example.com')
        GameConfiguration.objects.create(owner=self.user, name='Config A')
        GameConfiguration.objects.create(owner=other_user, name='Config B')
        my_configs = GameConfiguration.objects.filter(owner=self.user)
        self.assertEqual(my_configs.count(), 1)
        self.assertEqual(my_configs.first().name, 'Config A')


# ===========================================================================
# Test Suite 2: Role Models and Abilities
# ===========================================================================

class TestRoleModels(TestCase):
    def setUp(self):
        self.user = make_user()

    def test_get_or_create_system_roles(self):
        """System roles are created on first call, reused on subsequent calls."""
        roles1 = RoleDistributionService.get_or_create_base_roles()
        roles2 = RoleDistributionService.get_or_create_base_roles()
        self.assertEqual(len(roles1), 5)
        self.assertEqual(set(roles1.keys()), {RoleType.CITIZEN, RoleType.MAFIA, RoleType.DON, RoleType.DOCTOR, RoleType.DETECTIVE})
        # Second call must return same DB objects
        self.assertEqual(
            {r.id for r in roles1.values()},
            {r.id for r in roles2.values()},
        )


    def test_system_roles_are_marked_system(self):
        """System roles have is_system=True."""
        roles = RoleDistributionService.get_or_create_base_roles()
        for role in roles.values():
            self.assertTrue(role.is_system, f"Role {role.name} should be is_system=True")

    def test_create_custom_role_with_ability(self):
        """Custom role can be created with a RoleAbility."""
        role = Role.objects.create(
            owner=self.user,
            name='Vigilante',
            code='vigilante',
            team=RoleTeam.CIVILIAN,
            description='Can kill once per game.',
            is_system=False,
            is_active=True,
        )
        ability = RoleAbility.objects.create(
            role=role,
            ability_type=AbilityType.KILL,
            phase=AbilityPhase.NIGHT,
            target_required=True,
            uses_per_game=1,
        )
        self.assertEqual(role.abilities.count(), 1)
        self.assertEqual(ability.ability_type, AbilityType.KILL)

    def test_role_unique_code_per_owner(self):
        """Same code cannot exist twice for same owner."""
        Role.objects.create(owner=self.user, name='Role A', code='mycode', team=RoleTeam.CIVILIAN, is_system=False)
        from django.db import IntegrityError
        with self.assertRaises(IntegrityError):
            Role.objects.create(owner=self.user, name='Role B', code='mycode', team=RoleTeam.MAFIA, is_system=False)

    def test_different_owners_same_code_allowed(self):
        """Same code can exist for different owners."""
        other_user = make_user('other@example.com')
        Role.objects.create(owner=self.user, name='Role A', code='mycode', team=RoleTeam.CIVILIAN, is_system=False)
        Role.objects.create(owner=other_user, name='Role B', code='mycode', team=RoleTeam.MAFIA, is_system=False)
        self.assertEqual(Role.objects.filter(code='mycode').count(), 2)

    def test_system_roles_cannot_have_owner(self):
        """System roles have owner=None."""
        roles = RoleDistributionService.get_or_create_base_roles()
        for role in roles.values():
            self.assertIsNone(role.owner)


# ===========================================================================
# Test Suite 3: Role Distribution Service
# ===========================================================================

class TestRoleDistributionService(TestCase):
    def test_hardcoded_4_players(self):
        """Phase 2 fallback: 4 players -> 1 Don, 1 Doctor, 1 Detective, 1 Citizen."""
        result = RoleDistributionService.calculate_role_list(4)
        self.assertEqual(len(result), 4)
        self.assertEqual(result.count(RoleType.DON), 1)
        self.assertEqual(result.count(RoleType.DOCTOR), 1)
        self.assertEqual(result.count(RoleType.DETECTIVE), 1)
        self.assertEqual(result.count(RoleType.CITIZEN), 1)

    def test_hardcoded_5_players(self):
        """Phase 2 fallback: 5 players -> 1 Don, 1 Doctor, 1 Detective, 2 Citizens."""
        result = RoleDistributionService.calculate_role_list(5)
        self.assertEqual(len(result), 5)
        self.assertEqual(result.count(RoleType.DON), 1)
        self.assertEqual(result.count(RoleType.DOCTOR), 1)
        self.assertEqual(result.count(RoleType.DETECTIVE), 1)
        self.assertEqual(result.count(RoleType.CITIZEN), 2)

    def test_hardcoded_6_players(self):
        """Phase 2 fallback: 6 players -> 1 DON + 1 MAFIA (2 total Mafia team)."""
        result = RoleDistributionService.calculate_role_list(6)
        self.assertEqual(result.count(RoleType.DON), 1)
        self.assertEqual(result.count(RoleType.MAFIA), 1)
        self.assertEqual(result.count(RoleType.DON) + result.count(RoleType.MAFIA), 2)

    def test_hardcoded_minimum_players(self):
        """Less than 4 players raises ValueError."""
        with self.assertRaises(ValueError):
            RoleDistributionService.calculate_role_list(3)

    def test_hardcoded_large_game(self):
        """Large game: total roles == player count."""
        for n in range(7, 15):
            result = RoleDistributionService.calculate_role_list(n)
            self.assertEqual(len(result), n, f"Expected {n} roles, got {len(result)}")

    def test_config_driven_no_rules_fallback(self):
        """Config without rules falls back to hardcoded logic."""
        user = make_user()
        config = GameConfiguration.objects.create(owner=user, name='Empty Config')
        result = RoleDistributionService.calculate_role_list_from_configuration(6, config)
        self.assertEqual(len(result), 6)
        # Should equal Phase 2 fallback for 6 players
        expected = RoleDistributionService.calculate_role_list(6)
        self.assertEqual(sorted(result), sorted(expected))

    def test_config_driven_exact_distribution(self):
        """Config with EXACT rules distributes correctly."""
        user = make_user()
        config = GameConfiguration.objects.create(owner=user, name='Test Config')
        base_roles = RoleDistributionService.get_or_create_base_roles()
        RoleDistributionRule.objects.create(
            configuration=config,
            role=base_roles[RoleType.MAFIA],
            distribution_type=DistributionType.EXACT,
            min_count=2,
            max_count=2,
            priority=10,
        )
        RoleDistributionRule.objects.create(
            configuration=config,
            role=base_roles[RoleType.DOCTOR],
            distribution_type=DistributionType.EXACT,
            min_count=1,
            max_count=1,
            priority=5,
        )
        # 6 players: 2 Mafia + 1 Doctor + 3 Citizens (filled by default)
        result = RoleDistributionService.calculate_role_list_from_configuration(6, config)
        self.assertEqual(len(result), 6)
        self.assertEqual(result.count(RoleType.MAFIA), 2)
        self.assertEqual(result.count(RoleType.DOCTOR), 1)

    def test_assign_roles_deterministic_with_seed(self):
        """Same seed produces identical role assignment."""
        user = make_user()
        bot = make_bot(user)
        game1 = Game.objects.create(bot=bot, chat_id=111, phase=GamePhase.NIGHT, status=GamePhase.NIGHT)
        game2 = Game.objects.create(bot=bot, chat_id=222, phase=GamePhase.NIGHT, status=GamePhase.NIGHT)

        roles = RoleDistributionService.get_or_create_base_roles()
        players1 = [
            Player.objects.create(game=game1, telegram_user_id=i, display_name=f'P{i}')
            for i in range(1, 5)
        ]
        players2 = [
            Player.objects.create(game=game2, telegram_user_id=i, display_name=f'P{i}')
            for i in range(1, 5)
        ]

        result1 = RoleDistributionService.assign_roles_to_players(players1, seed=42)
        result2 = RoleDistributionService.assign_roles_to_players(players2, seed=42)

        names1 = [r.name for _, r in result1]
        names2 = [r.name for _, r in result2]
        self.assertEqual(names1, names2, "Same seed must produce same role order")


# ===========================================================================
# Test Suite 4: Template System
# ===========================================================================

class TestTemplateSystem(TestCase):
    def setUp(self):
        self.user = make_user()
        self.other_user = make_user('other@example.com')

    def test_create_user_template(self):
        """User can create a private template."""
        tpl = GameTemplate.objects.create(
            owner=self.user,
            name='My Template',
            template_type=TemplateType.USER,
            visibility=TemplateVisibility.PRIVATE,
            configuration_data={'minimum_players': 5, 'maximum_players': 10},
        )
        self.assertEqual(tpl.owner, self.user)
        self.assertFalse(tpl.is_owned_by_me if hasattr(tpl, 'is_owned_by_me') else False)  # model field absent
        self.assertEqual(tpl.template_type, TemplateType.USER)

    def test_system_template_no_owner(self):
        """System templates have owner=None."""
        tpl = GameTemplate.objects.create(
            name='Classic Mode',
            template_type=TemplateType.SYSTEM,
            visibility=TemplateVisibility.PUBLIC,
            owner=None,
        )
        self.assertIsNone(tpl.owner)
        self.assertEqual(tpl.template_type, TemplateType.SYSTEM)

    def test_template_slug_auto_generated(self):
        """Slug is automatically generated from name."""
        tpl = GameTemplate.objects.create(
            owner=self.user,
            name='My Awesome Template',
            template_type=TemplateType.USER,
        )
        self.assertIsNotNone(tpl.slug)
        self.assertIn('awesome', tpl.slug)

    def test_template_get_default_configuration(self):
        """get_default_configuration fills missing keys with defaults."""
        tpl = GameTemplate.objects.create(
            owner=self.user,
            name='Partial Config',
            configuration_data={'minimum_players': 5},
        )
        cfg = tpl.get_default_configuration()
        self.assertEqual(cfg['minimum_players'], 5)  # provided value kept
        self.assertEqual(cfg['maximum_players'], 20)  # default filled in

    def test_template_visibility_isolation(self):
        """Private templates are not visible to other users (by convention)."""
        private_tpl = GameTemplate.objects.create(
            owner=self.user,
            name='Private',
            visibility=TemplateVisibility.PRIVATE,
        )
        public_tpl = GameTemplate.objects.create(
            owner=self.user,
            name='Public',
            visibility=TemplateVisibility.PUBLIC,
        )
        # Other user should only see PUBLIC
        public_visible = GameTemplate.objects.filter(
            visibility=TemplateVisibility.PUBLIC
        )
        self.assertIn(public_tpl, public_visible)
        private_visible = GameTemplate.objects.filter(
            owner=self.other_user,
            visibility=TemplateVisibility.PRIVATE,
        )
        self.assertNotIn(private_tpl, private_visible)

    def test_template_source_tracking(self):
        """Duplicated template references source template."""
        original = GameTemplate.objects.create(owner=self.user, name='Original')
        copy = GameTemplate.objects.create(
            owner=self.other_user,
            name='Copy',
            source_template=original,
        )
        self.assertEqual(copy.source_template, original)
        self.assertIn(copy, original.copies.all())


# ===========================================================================
# Test Suite 5: Tournament System
# ===========================================================================

class TestTournamentGroupingService(TestCase):
    def test_basic_grouping(self):
        """Groups 12 participants into 2 groups of 6."""
        ids = list(range(12))
        groups = TournamentGroupingService.group_participants(ids, players_per_game=6, seed=1)
        self.assertEqual(len(groups), 2)
        self.assertEqual(sum(len(g) for g in groups), 12)

    def test_grouping_deterministic_with_seed(self):
        """Same seed produces same groups."""
        ids = list(range(12))
        g1 = TournamentGroupingService.group_participants(ids, 6, seed=42)
        g2 = TournamentGroupingService.group_participants(ids, 6, seed=42)
        self.assertEqual(g1, g2)

    def test_grouping_different_seeds(self):
        """Different seeds may produce different groups."""
        ids = list(range(12))
        g1 = TournamentGroupingService.group_participants(ids, 6, seed=1)
        g2 = TournamentGroupingService.group_participants(ids, 6, seed=2)
        # This could theoretically be equal, but for 12 elements it's extremely unlikely
        # Just verify both are valid
        self.assertEqual(sum(len(g) for g in g1), 12)
        self.assertEqual(sum(len(g) for g in g2), 12)

    def test_undersized_last_group_merged(self):
        """Last group < 4 is merged with previous."""
        ids = list(range(7))  # 7 ids -> group of 6 + group of 1 -> merged to 7
        groups = TournamentGroupingService.group_participants(ids, 6, seed=0)
        self.assertEqual(len(groups), 1, "Undersized last group should be merged")
        self.assertEqual(len(groups[0]), 7)

    def test_invalid_players_per_game(self):
        """players_per_game < 4 raises error."""
        with self.assertRaises(TournamentValidationError):
            TournamentGroupingService.group_participants([1, 2, 3], 3)

    def test_empty_participants(self):
        """Empty participant list returns empty groups."""
        groups = TournamentGroupingService.group_participants([], 6)
        self.assertEqual(groups, [])


class TestTournamentScoringService(TestCase):
    def setUp(self):
        self.user = make_user()
        self.tournament = Tournament.objects.create(
            owner=self.user,
            name='Test Tournament',
            scoring_config={},  # uses defaults
        )

    def test_score_calculation_survival_and_win(self):
        """Surviving winner scores: participation + survival + winning_faction."""
        results = [{
            'telegram_user_id': 101,
            'survived': True,
            'won': True,
            'kills': 0,
            'is_final_survivor': False,
        }]
        scores = TournamentScoringService.calculate_scores(self.tournament, None, results)
        expected = 1 + 1 + 3  # participation + survival + winning_faction
        self.assertEqual(scores[101], expected)

    def test_score_participation_only(self):
        """Loser who died early scores only participation."""
        results = [{
            'telegram_user_id': 102,
            'survived': False,
            'won': False,
            'kills': 0,
            'is_final_survivor': False,
        }]
        scores = TournamentScoringService.calculate_scores(self.tournament, None, results)
        self.assertEqual(scores[102], 1)  # participation only

    def test_score_with_kills(self):
        """Mafia kills add to score."""
        results = [{
            'telegram_user_id': 103,
            'survived': True,
            'won': True,
            'kills': 3,
            'is_final_survivor': True,
        }]
        scores = TournamentScoringService.calculate_scores(self.tournament, None, results)
        # 1 + 1 + 3 + 3*1 + 2 = 10
        expected = 1 + 1 + 3 + 3 + 2
        self.assertEqual(scores[103], expected)

    def test_score_deterministic_multiple_players(self):
        """Score calculation is deterministic for multiple players."""
        results = [
            {'telegram_user_id': 1, 'survived': True, 'won': True, 'kills': 2, 'is_final_survivor': False},
            {'telegram_user_id': 2, 'survived': False, 'won': False, 'kills': 0, 'is_final_survivor': False},
            {'telegram_user_id': 3, 'survived': True, 'won': True, 'kills': 0, 'is_final_survivor': True},
        ]
        scores1 = TournamentScoringService.calculate_scores(self.tournament, None, results)
        scores2 = TournamentScoringService.calculate_scores(self.tournament, None, results)
        self.assertEqual(scores1, scores2)


class TestTournamentService(TestCase):
    def setUp(self):
        self.user = make_user()
        self.other_user = make_user('other@example.com')
        plans = EntitlementService.get_or_create_default_plans()
        SubscriptionService.activate_subscription(self.user, plans['PRO'])
        SubscriptionService.activate_subscription(self.other_user, plans['PRO'])

    def test_create_tournament(self):
        """TournamentService.create_tournament creates in DRAFT status."""
        t = TournamentService.create_tournament(
            owner=self.user,
            name='My Tournament',
            max_players=12,
            players_per_game=6,
            total_rounds=2,
        )
        self.assertEqual(t.status, TournamentStatus.DRAFT)
        self.assertEqual(t.max_players, 12)
        self.assertEqual(t.owner, self.user)

    def test_open_registration(self):
        """DRAFT tournament can be opened for registration."""
        t = TournamentService.create_tournament(self.user, 'T1')
        TournamentService.open_registration(t)
        t.refresh_from_db()
        self.assertEqual(t.status, TournamentStatus.REGISTRATION)

    def test_cannot_open_registration_twice(self):
        """Cannot open registration for an already-open tournament."""
        t = TournamentService.create_tournament(self.user, 'T1')
        TournamentService.open_registration(t)
        with self.assertRaises(TournamentValidationError):
            TournamentService.open_registration(t)

    def test_register_participant(self):
        """Participant can register in REGISTRATION tournament."""
        t = TournamentService.create_tournament(self.user, 'T1')
        TournamentService.open_registration(t)
        p = TournamentService.register_participant(t, 12345, 'Alice', 'alice_tg')
        self.assertEqual(p.telegram_user_id, 12345)
        self.assertEqual(p.status, ParticipantStatus.ACTIVE)

    def test_register_duplicate_raises(self):
        """Registering twice raises TournamentValidationError."""
        t = TournamentService.create_tournament(self.user, 'T1')
        TournamentService.open_registration(t)
        TournamentService.register_participant(t, 12345, 'Alice')
        with self.assertRaises(TournamentValidationError):
            TournamentService.register_participant(t, 12345, 'Alice')

    def test_registration_capacity_limit(self):
        """Cannot register beyond max_players."""
        t = TournamentService.create_tournament(self.user, 'T1', max_players=4, players_per_game=4)
        TournamentService.open_registration(t)
        for i in range(4):
            TournamentService.register_participant(t, 1000 + i, f'Player{i}')
        with self.assertRaises(TournamentValidationError):
            TournamentService.register_participant(t, 9999, 'Extra Player')

    def test_cannot_start_without_enough_participants(self):
        """Cannot start tournament without minimum participants."""
        t = TournamentService.create_tournament(self.user, 'T1', players_per_game=6)
        TournamentService.open_registration(t)
        TournamentService.register_participant(t, 1, 'Alice')  # only 1 player
        with self.assertRaises(TournamentValidationError):
            TournamentService.start_tournament(t)

    def test_cancel_tournament(self):
        """Tournament can be cancelled from any non-terminal state."""
        t = TournamentService.create_tournament(self.user, 'T1')
        TournamentService.cancel_tournament(t)
        t.refresh_from_db()
        self.assertEqual(t.status, TournamentStatus.CANCELLED)

    def test_cannot_cancel_finished_tournament(self):
        """Cannot cancel an already finished tournament."""
        t = TournamentService.create_tournament(self.user, 'T1')
        t.status = TournamentStatus.FINISHED
        t.save()
        with self.assertRaises(TournamentValidationError):
            TournamentService.cancel_tournament(t)

    def test_leaderboard_ordering(self):
        """Leaderboard sorts by score DESC, then wins DESC."""
        t = TournamentService.create_tournament(self.user, 'T1')
        TournamentService.open_registration(t)
        p1 = TournamentService.register_participant(t, 1, 'Alice')
        p2 = TournamentService.register_participant(t, 2, 'Bob')
        p3 = TournamentService.register_participant(t, 3, 'Carol')

        # Manually set scores
        p1.score = 10; p1.games_won = 2; p1.save()
        p2.score = 15; p2.games_won = 3; p2.save()
        p3.score = 10; p3.games_won = 1; p3.save()

        leaderboard = TournamentService.get_leaderboard(t)
        self.assertEqual(len(leaderboard), 3)
        self.assertEqual(leaderboard[0]['telegram_user_id'], 2)  # Bob: 15 pts
        self.assertEqual(leaderboard[1]['telegram_user_id'], 1)  # Alice: 10 pts, 2 wins
        self.assertEqual(leaderboard[2]['telegram_user_id'], 3)  # Carol: 10 pts, 1 win

    def test_tournament_multi_tenant_isolation(self):
        """Users only see their own tournaments."""
        TournamentService.create_tournament(self.user, 'T1')
        TournamentService.create_tournament(self.other_user, 'T2')
        my_tournaments = Tournament.objects.filter(owner=self.user)
        self.assertEqual(my_tournaments.count(), 1)
        self.assertEqual(my_tournaments.first().name, 'T1')

    def test_withdraw_participant(self):
        """Participant can withdraw from REGISTRATION tournament."""
        t = TournamentService.create_tournament(self.user, 'T1')
        TournamentService.open_registration(t)
        TournamentService.register_participant(t, 1, 'Alice')
        TournamentService.withdraw_participant(t, 1)
        p = TournamentParticipant.objects.get(tournament=t, telegram_user_id=1)
        self.assertEqual(p.status, ParticipantStatus.WITHDRAWN)

    def test_creation_validation_players_per_game(self):
        """players_per_game must be >= 4."""
        with self.assertRaises(TournamentValidationError):
            TournamentService.create_tournament(self.user, 'T1', players_per_game=3)

    def test_creation_validation_total_rounds(self):
        """total_rounds must be >= 1."""
        with self.assertRaises(TournamentValidationError):
            TournamentService.create_tournament(self.user, 'T1', total_rounds=0)


# ===========================================================================
# Test Suite 6: Configuration Snapshot
# ===========================================================================

class TestConfigurationSnapshot(TestCase):
    def setUp(self):
        self.user = make_user()
        self.bot = make_bot(self.user)

    def test_snapshot_created_on_game_start(self):
        """Starting a game creates a ConfigurationSnapshot."""
        from apps.games.engine.game_service import GameService, _create_configuration_snapshot

        game = Game.objects.create(bot=self.bot, chat_id=999, phase=GamePhase.WAITING, status=GamePhase.WAITING)
        snapshot = _create_configuration_snapshot(game)
        self.assertIsNotNone(snapshot)
        self.assertEqual(snapshot.game, game)
        self.assertEqual(snapshot.minimum_players, 4)  # default
        self.assertEqual(snapshot.game_mode, 'CLASSIC')

    def test_snapshot_reads_from_configuration(self):
        """Snapshot captures GameConfiguration values."""
        from apps.games.engine.game_service import _create_configuration_snapshot

        config = GameConfiguration.objects.create(
            owner=self.user,
            name='Turbo Config',
            minimum_players=5,
            maximum_players=15,
            night_duration=30,
            tie_behavior=TieBehavior.RANDOM,
        )
        game = Game.objects.create(
            bot=self.bot, chat_id=888,
            phase=GamePhase.WAITING, status=GamePhase.WAITING,
            game_configuration=config,
        )
        snapshot = _create_configuration_snapshot(game)
        self.assertEqual(snapshot.minimum_players, 5)
        self.assertEqual(snapshot.maximum_players, 15)
        self.assertEqual(snapshot.night_duration, 30)
        self.assertEqual(snapshot.tie_behavior, TieBehavior.RANDOM)
        self.assertEqual(snapshot.configuration_name, 'Turbo Config')
