from django.db import models
from django.conf import settings
from apps.common.models import BaseEntityModel


class PlayerProfile(BaseEntityModel):
    """Rich player profile representation for Telegram and Web dashboard."""
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='player_profile'
    )
    telegram_id = models.BigIntegerField(unique=True, db_index=True)
    telegram_username = models.CharField(max_length=100, blank=True, null=True, db_index=True)
    first_name = models.CharField(max_length=150, blank=True)
    last_name = models.CharField(max_length=150, blank=True)
    custom_title = models.CharField(max_length=100, blank=True)
    language_code = models.CharField(
        max_length=10,
        choices=[('uz', "O'zbek"), ('ru', 'Русский'), ('en', 'English')],
        default='uz'
    )
    avatar_url = models.URLField(max_length=500, blank=True)
    is_platform_owner = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Platform Owner status (e.g. @ismoilo9) granting unrestricted features and VIP Diamond."
    )
    is_channel_bonus_claimed = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Whether player has received the 2x dollar bonus for joining @MafiaBotFather channel."
    )

    class Meta:
        ordering = ['-created_at']

    @property
    def full_name(self) -> str:
        name = f"{self.first_name} {self.last_name}".strip()
        return name or self.telegram_username or f"Player {self.telegram_id}"

    def __str__(self):
        return f"Profile({self.telegram_id}: @{self.telegram_username or self.full_name})"


class PlayerStats(BaseEntityModel):
    """Detailed Mafia gameplay statistics calculated from verified game history."""
    player_profile = models.OneToOneField(
        PlayerProfile,
        on_delete=models.CASCADE,
        related_name='stats'
    )
    games_played = models.PositiveIntegerField(default=0)
    games_won = models.PositiveIntegerField(default=0)
    games_lost = models.PositiveIntegerField(default=0)
    mafia_wins = models.PositiveIntegerField(default=0)
    civilian_wins = models.PositiveIntegerField(default=0)
    doctor_saves = models.PositiveIntegerField(default=0)
    detective_investigations = models.PositiveIntegerField(default=0)
    successful_kills = models.PositiveIntegerField(default=0)
    successful_votes = models.PositiveIntegerField(default=0)
    survival_count = models.PositiveIntegerField(default=0)
    best_win_streak = models.PositiveIntegerField(default=0)
    current_win_streak = models.PositiveIntegerField(default=0)
    mvp_count = models.PositiveIntegerField(default=0)

    # Reference card statistics
    protection_count = models.PositiveIntegerField(default=0)
    investigation_count = models.PositiveIntegerField(default=0)
    voting_count = models.PositiveIntegerField(default=0)
    doctor_count = models.PositiveIntegerField(default=0)
    mask_count = models.PositiveIntegerField(default=0)
    defense_count = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['-games_won', '-games_played']

    @property
    def win_rate(self) -> float:
        if self.games_played == 0:
            return 0.0
        return round((self.games_won / self.games_played) * 100, 1)

    def __str__(self):
        return f"Stats({self.player_profile.telegram_id} | {self.games_won}/{self.games_played} wins, {self.win_rate}%)"


class AchievementCategory(models.TextChoices):
    VICTORY = 'VICTORY', 'Victories & Wins'
    ROLE_MASTERY = 'ROLE_MASTERY', 'Role Mastery'
    SURVIVAL = 'SURVIVAL', 'Survival'
    WEALTH = 'WEALTH', 'Wealth & Collection'
    SOCIAL = 'SOCIAL', 'Social & Tournaments'


class Achievement(BaseEntityModel):
    """Platform achievements unlockable through game events."""
    code = models.CharField(max_length=50, unique=True, db_index=True)
    title = models.CharField(max_length=100)
    description = models.TextField()
    badge_icon = models.CharField(max_length=20, default='🏆')
    category = models.CharField(
        max_length=30,
        choices=AchievementCategory.choices,
        default=AchievementCategory.VICTORY
    )
    diamond_reward = models.PositiveIntegerField(default=0)
    coin_reward = models.PositiveIntegerField(default=0)
    target_count = models.PositiveIntegerField(default=1)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['category', 'target_count']

    def __str__(self):
        return f"{self.badge_icon} {self.title} (+{self.diamond_reward} 💎)"


class UserAchievement(BaseEntityModel):
    """Records which achievements a player has unlocked."""
    player_profile = models.ForeignKey(
        PlayerProfile,
        on_delete=models.CASCADE,
        related_name='unlocked_achievements'
    )
    achievement = models.ForeignKey(Achievement, on_delete=models.CASCADE)
    unlocked_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [['player_profile', 'achievement']]
        ordering = ['-unlocked_at']

    def __str__(self):
        return f"{self.player_profile} unlocked {self.achievement.title}"


class PlayerCouple(BaseEntityModel):
    """
    Fun couple / marriage system for Mafia groups (/para, /dpara, /mypara).
    """
    user1_id = models.BigIntegerField(db_index=True)
    user1_name = models.CharField(max_length=255, default='')
    user2_id = models.BigIntegerField(db_index=True)
    user2_name = models.CharField(max_length=255, default='')
    chat_id = models.BigIntegerField(null=True, blank=True, help_text="Group chat where couple was formed")
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = "O'yinchi Parasi"
        verbose_name_plural = "O'yinchilar Paralari"

    def __str__(self):
        return f"Couple({self.user1_id} [{self.user1_name}] & {self.user2_id} [{self.user2_name}])"
