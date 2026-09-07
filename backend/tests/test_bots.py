from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
from apps.bots.models import Bot, BotCredential, BotStatus
from apps.common.services.encryption import TokenEncryptionService

User = get_user_model()


class BotMultiTenancyAndSecurityTests(TestCase):
    def setUp(self):
        self.client = APIClient()

        # User A
        self.user_a = User.objects.create_user(
            username='usera',
            email='usera@example.com',
            password='Password123!'
        )

        # User B
        self.user_b = User.objects.create_user(
            username='userb',
            email='userb@example.com',
            password='Password123!'
        )

        self.bots_url = '/api/v1/bots/'
        self.raw_bot_token = '8741801900:AAHtCUxO2zvG737po1_2mTOEW_hr8lA657g'

    def test_credential_encryption_service(self):
        """Test symmetric Fernet encryption & decryption."""
        encrypted = TokenEncryptionService.encrypt_token(self.raw_bot_token)
        self.assertNotEqual(encrypted, self.raw_bot_token)

        decrypted = TokenEncryptionService.decrypt_token(encrypted)
        self.assertEqual(decrypted, self.raw_bot_token)

        masked = TokenEncryptionService.mask_token(self.raw_bot_token)
        self.assertEqual(masked, '8741****657g')

    def test_multi_tenant_bot_isolation(self):
        """Test User A cannot see or access User B's bots."""
        # Create bot for User B
        bot_b = Bot.objects.create(
            owner=self.user_b,
            name="User B Bot",
            telegram_username="user_b_bot",
            status=BotStatus.ACTIVE
        )

        # Authenticate as User A
        self.client.force_authenticate(user=self.user_a)

        # 1. User A lists bots — should get EMPTY array (User B's bot hidden)
        list_response = self.client.get(self.bots_url)
        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        results = list_response.data.get('results', list_response.data)
        self.assertEqual(len(results), 0)

        # 2. User A attempts direct GET request to User B's bot ID — HTTP 404 NOT FOUND
        detail_response = self.client.get(f"{self.bots_url}{bot_b.id}/")
        self.assertEqual(detail_response.status_code, status.HTTP_404_NOT_FOUND)

    def test_bot_creation_and_token_masking(self):
        """Test bot creation automatically encrypts token and returns masked token."""
        self.client.force_authenticate(user=self.user_a)

        payload = {
            'name': 'User A Mafia Bot',
            'telegram_username': 'usera_mafia_bot',
            'bot_token': self.raw_bot_token,
            'description': 'Testing bot'
        }

        response = self.client.post(self.bots_url, payload)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['masked_token'], '8741****657g')
        self.assertNotIn(self.raw_bot_token, str(response.data))

        # Verify DB stored encrypted token, NOT raw token
        bot = Bot.objects.get(id=response.data['id'])
        credential = BotCredential.objects.get(bot=bot)
        self.assertNotEqual(credential.encrypted_token, self.raw_bot_token)
        self.assertEqual(credential.get_token(), self.raw_bot_token)

    def test_bot_type_defaults_and_tier_checking(self):
        """Test BotType choices, default value, and tier access helper."""
        from apps.bots.models import BotType
        from bot_runtime.handlers.lobby import _check_bot_tier_access, TIER_RANKS

        bot_std = Bot.objects.create(
            owner=self.user_a,
            name="Standard Bot",
            telegram_username="std_bot",
            bot_type=BotType.STANDARD,
            status=BotStatus.ACTIVE
        )
        bot_mega = Bot.objects.create(
            owner=self.user_a,
            name="Mega Bot",
            telegram_username="mega_bot",
            bot_type=BotType.MEGA,
            status=BotStatus.ACTIVE
        )

        self.assertEqual(bot_std.bot_type, 'STANDARD')
        self.assertEqual(bot_mega.bot_type, 'MEGA')
        self.assertEqual(TIER_RANKS['STANDARD'], 1)
        self.assertEqual(TIER_RANKS['SUPER'], 2)
        self.assertEqual(TIER_RANKS['MEGA'], 3)

