import json
from django.test import TestCase, Client
from django.urls import reverse
from apps.bots.models import Bot, BotGroup
from apps.users.models import User, UserRole
from apps.stats.models import PlayerProfile


class GroupCabinetTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='superadmin',
            email='admin@bloodymafia.uz',
            password='testpassword123',
            role=UserRole.SUPERADMIN,
            is_staff=True,
            is_superuser=True
        )
        self.bot1 = Bot.objects.create(
            owner=self.user,
            name="Mafia Bot 1",
            telegram_bot_id=111111,
            telegram_username="mafia_bot_1"
        )
        self.bot2 = Bot.objects.create(
            owner=self.user,
            name="Mafia Bot 2",
            telegram_bot_id=222222,
            telegram_username="mafia_bot_2"
        )
        self.group = BotGroup.objects.create(
            bot=self.bot1,
            chat_id=-1001987654321,
            title="Furix Mafia Asosiy Guruh",
            username="furix_mafia",
            owner_telegram_id=999888,
            owner_name="Ali Valiyev",
            owner_username="ali_valiyev",
            cabinet_login="furix_kabinet",
            cabinet_password="mafiapassword123",
            total_games_played=25
        )

    def test_unique_chat_id_in_botgroup(self):
        """Ensures chat_id is strictly unique across BotGroup."""
        with self.assertRaises(Exception):
            BotGroup.objects.create(
                bot=self.bot2,
                chat_id=-1001987654321,
                title="Duplicate Group",
                cabinet_login="duplicate_login"
            )

    def test_get_user_groups_api_deduplication_and_format(self):
        """Checks get_user_groups_api returns unique group entries."""
        resp = self.client.get(f'/webapp/api/groups/list/?tg_id={self.group.owner_telegram_id}')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data.get('ok'))
        groups = data.get('groups', [])
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0]['title'], "Furix Mafia Asosiy Guruh")
        self.assertEqual(groups[0]['cabinet_login'], "furix_kabinet")
        self.assertEqual(groups[0]['total_games'], 25)

    def test_group_cabinet_login_api_success(self):
        """Checks authentication with login and password for group cabinet."""
        payload = {
            'login': 'furix_kabinet',
            'password': 'mafiapassword123'
        }
        resp = self.client.post(
            '/webapp/api/group/login/',
            data=json.dumps(payload),
            content_type='application/json'
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data.get('ok'))
        self.assertEqual(data['group']['title'], "Furix Mafia Asosiy Guruh")
        self.assertEqual(data['group']['cabinet_login'], "furix_kabinet")

    def test_group_cabinet_login_api_invalid_creds(self):
        """Checks authentication failure with wrong password."""
        payload = {
            'login': 'furix_kabinet',
            'password': 'wrong_password'
        }
        resp = self.client.post(
            '/webapp/api/group/login/',
            data=json.dumps(payload),
            content_type='application/json'
        )
        self.assertEqual(resp.status_code, 401)
        data = resp.json()
        self.assertFalse(data.get('ok'))

    def test_superadmin_group_credentials_update(self):
        """Superadmin can update the single login and password for the group."""
        self.client.login(email='admin@bloodymafia.uz', password='testpassword123')
        url = reverse('superadmin:group_credentials_save', args=[self.group.id])
        resp = self.client.post(url, {
            'login': 'new_furix_login',
            'password': 'new_secret_pass_777'
        }, follow=True)
        self.assertEqual(resp.status_code, 200)
        
        self.group.refresh_from_db()
        self.assertEqual(self.group.cabinet_login, 'new_furix_login')
        self.assertEqual(self.group.cabinet_password, 'new_secret_pass_777')
