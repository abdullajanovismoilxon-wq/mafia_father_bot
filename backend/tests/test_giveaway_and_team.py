'''
Tests for Giveaway Drops (/changegive, /changemoney) and Team Game Mode (/team).
'''
from django.test import TestCase
from django.contrib.auth import get_user_model
from apps.users.models import UserRole
from apps.bots.models import Bot, BotStatus, BotType
from apps.economy.models import Wallet, CurrencyType, GiveawayDrop, GiveawayClaim
from apps.economy.giveaway_service import GiveawayService
from apps.economy.services import EconomyService
from apps.games.models import Game, Player, GamePhase
from apps.games.engine.game_service import GameService
from apps.games.engine.win_conditions import WinConditionService
from bot_runtime.keyboards.inline import _player_team_badge, build_team_lobby_keyboard

User = get_user_model()


class TestGiveawayService(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='sender_user',
            telegram_id=111222333,
            role=UserRole.USER
        )
        self.wallet = EconomyService.get_or_create_wallet(telegram_id=111222333)
        self.wallet.diamonds = 200
        self.wallet.money = 5000
        self.wallet.save()

    def test_commission_calculation(self):
        fee = GiveawayService.calculate_commission(100, CurrencyType.DIAMONDS)
        self.assertEqual(fee, 3)

        fee_small = GiveawayService.calculate_commission(10, CurrencyType.DIAMONDS)
        self.assertEqual(fee_small, 1)

    def test_create_giveaway_drop_success(self):
        success, msg, drop = GiveawayService.create_drop(
            chat_id=-100123456789,
            sender_telegram_id=111222333,
            sender_name="Ali",
            currency=CurrencyType.DIAMONDS,
            amount=100
        )
        self.assertTrue(success)
        self.assertIsNotNone(drop)
        self.assertEqual(drop.total_amount, 100)
        self.assertEqual(drop.commission_amount, 3)
        self.assertEqual(drop.claimed_amount, 0)
        self.assertTrue(drop.is_active)

        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.diamonds, 97)

    def test_create_giveaway_insufficient_funds(self):
        success, msg, drop = GiveawayService.create_drop(
            chat_id=-100123456789,
            sender_telegram_id=111222333,
            sender_name="Ali",
            currency=CurrencyType.DIAMONDS,
            amount=500
        )
        self.assertFalse(success)
        self.assertIsNone(drop)
        self.assertIn("yetarli emas", msg)

    def test_claim_giveaway_drop(self):
        _, _, drop = GiveawayService.create_drop(
            chat_id=-100123456789,
            sender_telegram_id=111222333,
            sender_name="Ali",
            currency=CurrencyType.MONEY,
            amount=2
        )

        success, msg, remaining, total = GiveawayService.claim_drop(
            drop_id=drop.id,
            user_telegram_id=555666777,
            user_name="Vali"
        )
        self.assertTrue(success)
        self.assertEqual(remaining, 1)
        self.assertEqual(total, 2)

        r1_wallet = EconomyService.get_or_create_wallet(telegram_id=555666777)
        self.assertEqual(r1_wallet.money, 1)

        success2, msg2, _, _ = GiveawayService.claim_drop(
            drop_id=drop.id,
            user_telegram_id=555666777,
            user_name="Vali"
        )
        self.assertFalse(success2)
        self.assertIn("allaqachon", msg2.lower())

        success3, msg3, remaining3, _ = GiveawayService.claim_drop(
            drop_id=drop.id,
            user_telegram_id=888999000,
            user_name="G'ani"
        )
        self.assertTrue(success3)
        self.assertEqual(remaining3, 0)

        success4, msg4, _, _ = GiveawayService.claim_drop(
            drop_id=drop.id,
            user_telegram_id=123123123,
            user_name="Sami"
        )
        self.assertFalse(success4)


class TestTeamGameMode(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            username='admin_team',
            telegram_id=100000001,
            role=UserRole.SUPERADMIN
        )
        self.bot = Bot.objects.create(
            owner=self.admin,
            name="Team Mafia Bot",
            bot_type=BotType.STANDARD,
            status=BotStatus.ACTIVE,
            telegram_bot_id=999001,
            telegram_username="TeamMafiaBot"
        )

    def test_team_lobby_creation_and_joining(self):
        game = GameService.create_game(
            bot=self.bot,
            chat_id=-100987654321,
            mode="TEAM"
        )
        self.assertEqual(game.mode, "TEAM")

        p1, c1 = GameService.join_lobby(
            game=game,
            telegram_user_id=101,
            username="red_player1",
            display_name="Red 1",
            team_side="RED"
        )
        self.assertTrue(c1)
        self.assertEqual(p1.metadata.get('team_side'), 'RED')
        self.assertEqual(_player_team_badge(p1), '🔴 ')

        p2, c2 = GameService.join_lobby(
            game=game,
            telegram_user_id=102,
            username="blue_player1",
            display_name="Blue 1",
            team_side="BLUE"
        )
        self.assertTrue(c2)
        self.assertEqual(p2.metadata.get('team_side'), 'BLUE')
        self.assertEqual(_player_team_badge(p2), '🔵 ')

        p1_updated, c1_updated = GameService.join_lobby(
            game=game,
            telegram_user_id=101,
            username="red_player1",
            display_name="Red 1",
            team_side="BLUE"
        )
        self.assertFalse(c1_updated)
        self.assertEqual(p1_updated.metadata.get('team_side'), 'BLUE')
        self.assertEqual(_player_team_badge(p1_updated), '🔵 ')

    def test_team_win_condition(self):
        game = GameService.create_game(
            bot=self.bot,
            chat_id=-100987654321,
            mode="TEAM"
        )

        p_red1, _ = GameService.join_lobby(game, 201, "r1", "Red 1", team_side="RED")
        p_red2, _ = GameService.join_lobby(game, 202, "r2", "Red 2", team_side="RED")
        p_blue1, _ = GameService.join_lobby(game, 203, "b1", "Blue 1", team_side="BLUE")
        p_blue2, _ = GameService.join_lobby(game, 204, "b2", "Blue 2", team_side="BLUE")

        game.phase = GamePhase.NIGHT
        game.save()

        winner = WinConditionService.check_win_condition(game)
        self.assertIsNone(winner)

        p_blue1.is_alive = False
        p_blue1.save()
        p_blue2.is_alive = False
        p_blue2.save()

        winner = WinConditionService.check_win_condition(game)
        self.assertEqual(winner, 'TEAM_RED')
