from django.db import models
from django.conf import settings
from apps.common.models import BaseEntityModel


class TournamentStatus(models.TextChoices):
    DRAFT = 'DRAFT', 'Draft'
    REGISTRATION = 'REGISTRATION', 'Registration Open'
    ACTIVE = 'ACTIVE', 'Active'
    PAUSED = 'PAUSED', 'Paused'
    FINISHED = 'FINISHED', 'Finished'
    CANCELLED = 'CANCELLED', 'Cancelled'


class TournamentRoundStatus(models.TextChoices):
    PENDING = 'PENDING', 'Pending'
    ACTIVE = 'ACTIVE', 'Active'
    FINISHED = 'FINISHED', 'Finished'
    CANCELLED = 'CANCELLED', 'Cancelled'


class ParticipantStatus(models.TextChoices):
    ACTIVE = 'ACTIVE', 'Active'
    WITHDRAWN = 'WITHDRAWN', 'Withdrawn'
    DISQUALIFIED = 'DISQUALIFIED', 'Disqualified'


class Tournament(BaseEntityModel):
    """
    A tournament is a multi-round competition using Mafia games.
    Owner has full control; other users can only join as participants.
    """
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='tournaments',
        db_index=True,
    )
    # Optional: which bot hosts this tournament's Telegram interaction
    bot = models.ForeignKey(
        'bots.Bot',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='tournaments',
        db_index=True,
    )
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, default='')
    status = models.CharField(
        max_length=20,
        choices=TournamentStatus.choices,
        default=TournamentStatus.DRAFT,
        db_index=True,
    )

    max_players = models.PositiveSmallIntegerField(default=24)
    players_per_game = models.PositiveSmallIntegerField(
        default=6,
        help_text="How many participants per individual game in a round."
    )
    total_rounds = models.PositiveSmallIntegerField(default=3)
    current_round = models.PositiveSmallIntegerField(default=0)

    # Optional game template used for all tournament games
    game_template = models.ForeignKey(
        'templates.GameTemplate',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='tournaments',
    )

    # Frozen configuration snapshot (taken when tournament starts)
    configuration_data = models.JSONField(
        default=dict,
        help_text="Frozen game configuration used for all tournament games.",
    )

    # Scoring configuration
    scoring_config = models.JSONField(
        default=dict,
        help_text=(
            "Scoring rules: {participation: 1, survival: 1, winning_faction: 3, "
            "mafia_elimination: 1, final_survivor: 2}"
        ),
    )

    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['owner', 'status']),
            models.Index(fields=['status', 'created_at']),
        ]

    def get_default_scoring(self) -> dict:
        defaults = {
            'participation': 1,
            'survival': 1,
            'winning_faction': 3,
            'mafia_elimination': 1,
            'final_survivor': 2,
        }
        defaults.update(self.scoring_config or {})
        return defaults

    def __str__(self):
        return f"Tournament '{self.name}' [{self.status}] by {self.owner.email}"


class TournamentRound(BaseEntityModel):
    """A single round within a Tournament. Contains multiple Game instances."""
    tournament = models.ForeignKey(
        Tournament,
        on_delete=models.CASCADE,
        related_name='rounds',
        db_index=True,
    )
    number = models.PositiveSmallIntegerField()
    status = models.CharField(
        max_length=20,
        choices=TournamentRoundStatus.choices,
        default=TournamentRoundStatus.PENDING,
        db_index=True,
    )
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['number']
        unique_together = [('tournament', 'number')]

    def __str__(self):
        return f"Round {self.number} of {self.tournament.name} [{self.status}]"


class TournamentParticipant(BaseEntityModel):
    """
    A participant in a Tournament. Tracks cumulative scores across all rounds.
    Separate from Game-level Player — a participant can play in multiple games
    across rounds.
    """
    tournament = models.ForeignKey(
        Tournament,
        on_delete=models.CASCADE,
        related_name='participants',
        db_index=True,
    )
    telegram_user_id = models.BigIntegerField(db_index=True)
    display_name = models.CharField(max_length=255, default='')
    username = models.CharField(max_length=255, blank=True, default='')

    # Cumulative stats (updated by TournamentScoringService after each game)
    score = models.IntegerField(default=0, db_index=True)
    games_played = models.PositiveSmallIntegerField(default=0)
    games_won = models.PositiveSmallIntegerField(default=0)
    games_lost = models.PositiveSmallIntegerField(default=0)
    kills = models.PositiveSmallIntegerField(default=0)
    survival_count = models.PositiveSmallIntegerField(default=0)

    status = models.CharField(
        max_length=20,
        choices=ParticipantStatus.choices,
        default=ParticipantStatus.ACTIVE,
        db_index=True,
    )
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [('tournament', 'telegram_user_id')]
        ordering = ['-score', '-games_won', '-survival_count', 'telegram_user_id']
        indexes = [
            models.Index(fields=['tournament', 'status', '-score']),
        ]

    def __str__(self):
        return f"{self.display_name or self.username} in {self.tournament.name} (score={self.score})"


class TournamentGame(BaseEntityModel):
    """
    Links a Game instance to a specific TournamentRound.
    A regular Game has no TournamentGame — tournaments are optional.
    """
    round = models.ForeignKey(
        TournamentRound,
        on_delete=models.CASCADE,
        related_name='tournament_games',
        db_index=True,
    )
    game = models.OneToOneField(
        'games.Game',
        on_delete=models.CASCADE,
        related_name='tournament_game',
    )
    group_number = models.PositiveSmallIntegerField(
        default=1,
        help_text="Which group within this round (e.g. Group A=1, Group B=2).",
    )
    score_applied = models.BooleanField(
        default=False,
        help_text="True after TournamentScoringService has processed this game's result.",
    )

    class Meta:
        ordering = ['group_number']
        unique_together = [('round', 'group_number')]

    def __str__(self):
        return f"TournamentGame Round#{self.round.number} Group#{self.group_number}"
