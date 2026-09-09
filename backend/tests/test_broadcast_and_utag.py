"""
Tests for SuperAdmin Single-User Broadcast, User-Bots API, and @utag member collection.
"""
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from unittest.mock import patch, MagicMock

from apps.users.models import UserRole
from apps.bots.models import Bot, BotStatus, BotType, BotUser
from apps.stats.models import PlayerProfile
from apps.superadmin.models import BroadcastMessage
from apps.superadmin.services import BroadcastService

User = get_user_model()


class TestBroadcastAndUserBots(TestCase):
    def setUp(self):
        self.superadmin = User.objects.create_superuser(
            username='admin_test',
            email='admin@test.com',
            password='Password123!',
            role=UserRole.SUPERADMIN
        )
        self.client = Client()
        self.client.force_login(self.superadmin)

        # Create Bots
        self.bot1 = Bot.objects.create(
            owner=self.superadmin,
            name="Alpha Mafia",
            bot_type=BotType.STANDARD,
            status=BotStatus.ACTIVE,
            telegram_bot_id=100001,
            telegram_username="AlphaMafiaBot"
        )
        from apps.bots.models import BotCredential
        cred1 = BotCredential(bot=self.bot1)
        cred1.set_token("123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11")
        cred1.save()

        self.bot2 = Bot.objects.create(
            owner=self.superadmin,
            name="Beta Mafia",
            bot_type=BotType.SUPER,
            status=BotStatus.ACTIVE,
            telegram_bot_id=100002,
            telegram_username="BetaMafiaBot"
        )
        cred2 = BotCredential(bot=self.bot2)
        cred2.set_token("654321:XYZ-DEF1234ghIkl-zyx57W2v1u123ew22")
        cred2.save()

        # Create PlayerProfile
        self.profile = PlayerProfile.objects.create(
            telegram_id=999888777,
            telegram_username="ismoil_dev",
            first_name="Ismoiljon"
        )

        # Create BotUser connecting to bot1
        self.bot_user = BotUser.objects.create(
            bot=self.bot1,
            telegram_id=999888777,
            username="ismoil_dev",
            first_name="Ismoiljon",
            is_bot_started=True
        )

    def test_user_bots_api_by_username(self):
        """Test user_bots_api finds user and returns user_bots and all_bots."""
        response = self.client.get('/superadmin/api/user-bots/?query=@ismoil_dev')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['found'])
        self.assertEqual(data['user']['telegram_id'], 999888777)
        self.assertEqual(data['user']['username'], 'ismoil_dev')
        self.assertEqual(len(data['user_bots']), 1)
        self.assertEqual(data['user_bots'][0]['id'], str(self.bot1.id))
        self.assertGreaterEqual(len(data['all_bots']), 2)

    def test_user_bots_api_by_id(self):
        """Test user_bots_api finds user by numeric telegram ID."""
        response = self.client.get('/superadmin/api/user-bots/?query=999888777')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['found'])
        self.assertEqual(data['user']['telegram_id'], 999888777)

    def test_user_bots_api_not_found(self):
        """Test user_bots_api returns found=False with fallback all_bots."""
        response = self.client.get('/superadmin/api/user-bots/?query=@nonexistent_user_xyz')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertFalse(data['found'])
        self.assertGreaterEqual(len(data['all_bots']), 2)

    @patch('apps.superadmin.services.requests.post')
    def test_broadcast_specific_user_delivery(self, mock_post):
        """Test execute_broadcast delivers to SPECIFIC_USER using target user's bot."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"ok": True, "result": {"message_id": 123}}
        mock_post.return_value = mock_response

        broadcast = BroadcastMessage.objects.create(
            title="Maxsus Xabar",
            content="Assalomu alaykum!",
            target_audience="SPECIFIC_USER",
            target_user_id="ismoil_dev",
            target_bot=self.bot1,
            sender_bot_type="SPECIFIC_BOT"
        )

        success = BroadcastService.execute_broadcast(broadcast)
        self.assertTrue(success)
        broadcast.refresh_from_db()
        self.assertEqual(broadcast.status, "COMPLETED")
        self.assertEqual(broadcast.sent_success, 1)
        self.assertEqual(broadcast.sent_failed, 0)
        self.assertTrue(mock_post.called)
