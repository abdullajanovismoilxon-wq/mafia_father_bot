from django.db import models
from django.conf import settings
from apps.common.models import BaseEntityModel
from apps.common.services.encryption import TokenEncryptionService


class BotStatus(models.TextChoices):
    PENDING = 'PENDING', 'Pending Validation'
    ACTIVE = 'ACTIVE', 'Active'
    PAUSED = 'PAUSED', 'Paused'
    SUSPENDED = 'SUSPENDED', 'Suspended'
    ERROR = 'ERROR', 'Error'
    DELETED = 'DELETED', 'Deleted'


class RuntimeStatus(models.TextChoices):
    OFFLINE = 'OFFLINE', 'Offline'
    STARTING = 'STARTING', 'Starting'
    RUNNING = 'RUNNING', 'Running'
    STOPPING = 'STOPPING', 'Stopping'
    ERROR = 'ERROR', 'Runtime Error'


class BotType(models.TextChoices):
    STANDARD = 'STANDARD', 'Standart (Classic)'
    SUPER = 'SUPER', 'Super (Advanced)'
    MEGA = 'MEGA', 'Mega (Univers Pro)'


class Bot(BaseEntityModel):
    """Core Bot registry model representing a user's Telegram Mafia bot."""
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='bots',
        db_index=True
    )
    name = models.CharField(max_length=255)
    telegram_username = models.CharField(max_length=255, db_index=True)
    telegram_bot_id = models.BigIntegerField(null=True, blank=True, db_index=True)
    bot_type = models.CharField(
        max_length=20,
        choices=BotType.choices,
        default=BotType.STANDARD,
        db_index=True
    )
    status = models.CharField(
        max_length=20,
        choices=BotStatus.choices,
        default=BotStatus.PENDING,
        db_index=True
    )
    runtime_status = models.CharField(
        max_length=20,
        choices=RuntimeStatus.choices,
        default=RuntimeStatus.OFFLINE,
        db_index=True
    )
    description = models.TextField(blank=True, default='')

    class Meta:
        ordering = ['-created_at']
        unique_together = ('owner', 'telegram_username')

    def __str__(self):
        return f"{self.name} (@{self.telegram_username}) - Owner: {self.owner.email}"


class BotCredential(BaseEntityModel):
    """Encrypted store for sensitive Telegram Bot tokens."""
    bot = models.OneToOneField(Bot, on_delete=models.CASCADE, related_name='credential')
    encrypted_token = models.TextField()

    def set_token(self, plain_token: str):
        """Encrypts and sets the bot token."""
        self.encrypted_token = TokenEncryptionService.encrypt_token(plain_token)

    def get_token(self) -> str:
        """Decrypts and returns the raw bot token."""
        return TokenEncryptionService.decrypt_token(self.encrypted_token)

    def get_masked_token(self) -> str:
        """Returns masked token string for display."""
        raw_token = self.get_token()
        return TokenEncryptionService.mask_token(raw_token)

    def __str__(self):
        return f"Credential for Bot ID: {self.bot_id}"


class BotConfiguration(BaseEntityModel):
    """Configuration settings for a specific Bot instance."""
    bot = models.OneToOneField(Bot, on_delete=models.CASCADE, related_name='configuration')
    language = models.CharField(max_length=10, default='en')
    night_duration_seconds = models.PositiveIntegerField(default=60)
    day_duration_seconds = models.PositiveIntegerField(default=120)
    voting_duration_seconds = models.PositiveIntegerField(default=60)
    allow_custom_roles = models.BooleanField(default=False)
    show_roles_on_death = models.BooleanField(default=True)
    extra_settings = models.JSONField(default=dict, blank=True)

    def __str__(self):
        return f"Configuration for Bot: {self.bot.name}"


class BotGroup(BaseEntityModel):
    """Active Telegram group where a bot operates, including group owner metadata and Cabinet credentials."""
    bot = models.ForeignKey(Bot, on_delete=models.CASCADE, related_name='active_groups')
    chat_id = models.BigIntegerField(db_index=True)
    title = models.CharField(max_length=255, default='Telegram Guruh')
    username = models.CharField(max_length=255, blank=True, default='')
    owner_telegram_id = models.BigIntegerField(null=True, blank=True)
    owner_name = models.CharField(max_length=255, blank=True, default='')
    owner_username = models.CharField(max_length=255, blank=True, default='')
    
    # Cabinet Login & Password for Mini App
    cabinet_login = models.CharField(max_length=100, blank=True, default='', db_index=True)
    cabinet_password = models.CharField(max_length=100, blank=True, default='')
    
    # Custom Group-level Settings
    group_settings = models.JSONField(default=dict, blank=True)
    
    total_games_played = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    last_active_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('bot', 'chat_id')
        ordering = ['-last_active_at']

    def __str__(self):
        return f"{self.title} ({self.chat_id}) - Bot: {self.bot.name}"
