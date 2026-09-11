from django.db import models
from django.conf import settings
from apps.common.models import BaseEntityModel
from apps.bots.models import Bot


# ---------------------------------------------------------------------------
# Phase 2 Choices (preserved)
# ---------------------------------------------------------------------------

class GamePhase(models.TextChoices):
    WAITING = 'WAITING', 'Waiting for Players'
    STARTING = 'STARTING', 'Starting'
    NIGHT = 'NIGHT', 'Night'
    DAY = 'DAY', 'Day'
    DISCUSSION = 'DISCUSSION', 'Discussion'
    VOTING = 'VOTING', 'Voting'
    ELIMINATION = 'ELIMINATION', 'Elimination'
    FINISHED = 'FINISHED', 'Finished'
    CANCELED = 'CANCELED', 'Canceled'


class RoleTeam(models.TextChoices):
    CIVILIAN = 'CIVILIAN', 'Civilian'
    MAFIA = 'MAFIA', 'Mafia'
    NEUTRAL = 'NEUTRAL', 'Neutral'
    SOLO = 'SOLO', 'Solo'
    ZOMBIE = 'ZOMBIE', 'Zombie'


class RoleType(models.TextChoices):
    CITIZEN = 'CITIZEN', 'Citizen'
    MAFIA = 'MAFIA', 'Mafia'
    DOCTOR = 'DOCTOR', 'Doctor'
    DETECTIVE = 'DETECTIVE', 'Detective'
    DON = 'DON', 'Don'
    QOTIL = 'QOTIL', 'Qotil'
    KEZUVCHI = 'KEZUVCHI', 'Kezuvchi'
    SERJANT = 'SERJANT', 'Serjant'
    DAYDI = 'DAYDI', 'Daydi'
    ADVOKAT = 'ADVOKAT', 'Advokat'
    SUIDSID = 'SUIDSID', 'Suidsid'
    UBIYTSA = 'UBIYTSA', 'Ubiytsa'
    AFSUNGAR = 'AFSUNGAR', 'Afsungar'
    TUZOQCHI = 'TUZOQCHI', 'Tuzoqchi'
    ZOMBI = 'ZOMBI', 'Zombi'
    KIMYOGAR = 'KIMYOGAR', 'Kimyogar'
    AXMOQ = 'AXMOQ', 'Axmoq'
    BUQALAMUN = 'BUQALAMUN', 'Buqalamun'
    RAIS = 'RAIS', 'Rais'
    HAMSHIRA = 'HAMSHIRA', 'Hamshira'
    JOKER = 'JOKER', 'Joker'
    OMADLI = 'OMADLI', 'Omadli'
    JANOB = 'JANOB', 'Janob'
    BORI = 'BORI', 'Bori'
    AFERIST = 'AFERIST', 'Aferist'
    GAZABKOR = 'GAZABKOR', 'Gazabkor'
    SEHRGAR = 'SEHRGAR', 'Sehrgar'
    JURNALIST = 'JURNALIST', 'Jurnalist'
    SOTQIN = 'SOTQIN', 'Sotqin'
    ADMIRAL = 'ADMIRAL', 'Admiral'
    ROBINGUD = 'ROBINGUD', 'Robin Gud'
    AYGOQCHI = 'AYGOQCHI', 'Aygoqchi'
    KONCHI = 'KONCHI', 'Konchi'
    FOTOPARATCHI = 'FOTOPARATCHI', 'Fotoparatchi'
    QAROQCHI = 'QAROQCHI', 'Qaroqchi'
    LABORANT = 'LABORANT', 'Laborant'
    QORBOBO = 'QORBOBO', 'Qorbobo'
    OSHPAZ = 'OSHPAZ', 'Oshpaz'


# ---------------------------------------------------------------------------
# Phase 3 — Role Ability System
# ---------------------------------------------------------------------------

class AbilityType(models.TextChoices):
    KILL = 'KILL', 'Kill'
    PROTECT = 'PROTECT', 'Protect'
    INVESTIGATE = 'INVESTIGATE', 'Investigate'
    NONE = 'NONE', 'None (Passive)'


class AbilityPhase(models.TextChoices):
    NIGHT = 'NIGHT', 'Night'
    DAY = 'DAY', 'Day'
    ANY = 'ANY', 'Any Phase'


# ---------------------------------------------------------------------------
# Phase 3 — Extended Role Model
# ---------------------------------------------------------------------------

class Role(BaseEntityModel):
    """
    Mafia Role model — extended in Phase 3 to support configurable abilities
    and user-owned custom roles.
    """
    # Existing Phase 2 fields
    name = models.CharField(max_length=100, db_index=True)
    team = models.CharField(max_length=20, choices=RoleTeam.choices, default=RoleTeam.CIVILIAN)
    description = models.TextField(blank=True)

    # Phase 3 additions
    code = models.SlugField(
        max_length=50,
        db_index=True,
        help_text="Unique machine-readable identifier (e.g. 'mafia', 'doctor')."
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='custom_roles',
        help_text="null = system role, non-null = user-owned custom role",
        db_index=True,
    )
    is_active = models.BooleanField(default=True, db_index=True)
    is_system = models.BooleanField(
        default=False,
        help_text="True for built-in platform roles that cannot be deleted."
    )
    priority = models.PositiveSmallIntegerField(
        default=0,
        help_text="Display and processing order priority."
    )

    class Meta:
        ordering = ['priority', 'name']
        # Unique: same code cannot exist twice for same owner (null owner = system)
        unique_together = [('code', 'owner')]
        indexes = [
            models.Index(fields=['owner', 'is_active']),
            models.Index(fields=['is_system', 'is_active']),
        ]

    def __str__(self):
        prefix = "SYS" if self.is_system else (self.owner.email if self.owner else "?")
        return f"[{prefix}] {self.name} ({self.team})"


class RoleAbility(BaseEntityModel):
    """
    Declarative ability attached to a Role. Defines what action the role
    can perform during a given phase.
    Never executes user-provided code — purely data-driven.
    """
    role = models.ForeignKey(Role, on_delete=models.CASCADE, related_name='abilities')
    ability_type = models.CharField(max_length=20, choices=AbilityType.choices, default=AbilityType.NONE)
    phase = models.CharField(max_length=10, choices=AbilityPhase.choices, default=AbilityPhase.NIGHT)
    target_required = models.BooleanField(default=True)
    uses_per_game = models.PositiveSmallIntegerField(
        default=0, help_text="0 = unlimited uses per game."
    )
    cooldown_rounds = models.PositiveSmallIntegerField(
        default=0, help_text="0 = no cooldown between rounds."
    )
    allowed_targets = models.CharField(
        max_length=20,
        choices=RoleTeam.choices + [('ANY', 'Any Living Player')],  # type: ignore
        default='ANY',
        help_text="Which faction can be targeted. ANY = all living players.",
    )

    class Meta:
        ordering = ['phase', 'ability_type']

    def __str__(self):
        return f"{self.role.name} → {self.ability_type} (phase={self.phase})"


# ---------------------------------------------------------------------------
# Phase 3 — Game Configuration
# ---------------------------------------------------------------------------

class TieBehavior(models.TextChoices):
    NO_ELIMINATION = 'NO_ELIMINATION', 'No Elimination on Tie'
    RANDOM = 'RANDOM', 'Random Elimination on Tie'


class MafiaVoteMode(models.TextChoices):
    MAJORITY = 'MAJORITY', 'Majority Vote Required'
    ANY = 'ANY', 'Any Single Mafia Can Choose'


class GameMode(models.TextChoices):
    CLASSIC = 'CLASSIC', 'Classic'
    BLOODY = 'BLOODY', 'Bloody Mafia'
    BLOODY_MEGA = 'BLOODY_MEGA', 'Bloody Mafia Mega'
    FAST = 'FAST', 'Fast'
    QUICK = 'QUICK', 'Quick'
    CUSTOM = 'CUSTOM', 'Custom'
    TOURNAMENT = 'TOURNAMENT', 'Tournament'


class GameConfiguration(BaseEntityModel):
    """
    Reusable configurable game rules attached to a Bot or Template.
    The Game Engine reads configuration at game start and creates an immutable
    ConfigurationSnapshot — this object can change without affecting running games.
    """
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='game_configurations',
        db_index=True,
    )
    bot = models.ForeignKey(
        Bot,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='game_configurations',
        db_index=True,
    )
    name = models.CharField(max_length=255, default='Default Configuration')
    game_mode = models.CharField(max_length=20, choices=GameMode.choices, default=GameMode.CLASSIC)

    # Player limits
    minimum_players = models.PositiveSmallIntegerField(default=4)
    maximum_players = models.PositiveSmallIntegerField(default=20)

    # Phase durations (seconds)
    night_duration = models.PositiveIntegerField(default=60)
    discussion_duration = models.PositiveIntegerField(default=120)
    voting_duration = models.PositiveIntegerField(default=60)

    # Game rules
    allow_self_vote = models.BooleanField(default=False)
    allow_self_protection = models.BooleanField(default=False)
    reveal_role_on_elimination = models.BooleanField(default=True)
    tie_behavior = models.CharField(
        max_length=20, choices=TieBehavior.choices, default=TieBehavior.NO_ELIMINATION
    )
    mafia_vote_mode = models.CharField(
        max_length=20, choices=MafiaVoteMode.choices, default=MafiaVoteMode.ANY
    )
    allow_player_rejoin = models.BooleanField(default=False)
    automatic_phase_transition = models.BooleanField(default=True)
    day_discussion_enabled = models.BooleanField(default=True)

    # Atmosphere & Media settings
    night_media_url = models.CharField(max_length=500, blank=True, default='')
    day_media_url = models.CharField(max_length=500, blank=True, default='')
    elimination_media_url = models.CharField(max_length=500, blank=True, default='')
    victory_media_url = models.CharField(max_length=500, blank=True, default='')
    custom_theme = models.CharField(max_length=50, blank=True, default='default')

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['owner', 'game_mode']),
        ]

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.minimum_players > self.maximum_players:
            raise ValidationError("minimum_players cannot exceed maximum_players.")
        if self.minimum_players < 2:
            raise ValidationError("minimum_players must be at least 2.")
        if self.night_duration < 10:
            raise ValidationError("night_duration must be at least 10 seconds.")
        if self.voting_duration < 10:
            raise ValidationError("voting_duration must be at least 10 seconds.")

    def __str__(self):
        return f"Config '{self.name}' by {self.owner.email} [{self.game_mode}]"


class DistributionType(models.TextChoices):
    EXACT = 'EXACT', 'Exact Count'
    RANGE = 'RANGE', 'Range (min-max)'
    PERCENTAGE = 'PERCENTAGE', 'Percentage of Players'


class RoleDistributionRule(BaseEntityModel):
    """
    A single role allocation rule inside a GameConfiguration.
    Defines how many of each Role should appear given a player count.
    """
    configuration = models.ForeignKey(
        GameConfiguration,
        on_delete=models.CASCADE,
        related_name='distribution_rules',
    )
    role = models.ForeignKey(Role, on_delete=models.CASCADE, related_name='distribution_rules')
    distribution_type = models.CharField(
        max_length=20, choices=DistributionType.choices, default=DistributionType.EXACT
    )
    # EXACT or RANGE min count
    min_count = models.PositiveSmallIntegerField(default=1)
    # RANGE max count (ignored for EXACT)
    max_count = models.PositiveSmallIntegerField(default=1)
    # PERCENTAGE (0-100, ignored for EXACT/RANGE)
    percentage = models.PositiveSmallIntegerField(default=0)
    priority = models.PositiveSmallIntegerField(
        default=0,
        help_text="Processing order; higher priority roles are allocated first."
    )

    class Meta:
        ordering = ['-priority', 'role__name']
        unique_together = [('configuration', 'role')]

    def __str__(self):
        return f"{self.role.name} x{self.min_count}-{self.max_count} in Config #{self.configuration_id}"


class ConfigurationSnapshot(BaseEntityModel):
    """
    Immutable freeze of GameConfiguration + RoleDistributionRules at the moment
    a game starts. Ensures template/config edits never corrupt active games.
    """
    game = models.OneToOneField(
        'Game',
        on_delete=models.CASCADE,
        related_name='configuration_snapshot',
    )
    configuration_name = models.CharField(max_length=255, default='Default')
    game_mode = models.CharField(max_length=20, choices=GameMode.choices, default=GameMode.CLASSIC)

    # Frozen rule values
    minimum_players = models.PositiveSmallIntegerField(default=4)
    maximum_players = models.PositiveSmallIntegerField(default=20)
    night_duration = models.PositiveIntegerField(default=60)
    discussion_duration = models.PositiveIntegerField(default=120)
    voting_duration = models.PositiveIntegerField(default=60)
    allow_self_vote = models.BooleanField(default=False)
    allow_self_protection = models.BooleanField(default=False)
    reveal_role_on_elimination = models.BooleanField(default=True)
    tie_behavior = models.CharField(
        max_length=20, choices=TieBehavior.choices, default=TieBehavior.NO_ELIMINATION
    )
    mafia_vote_mode = models.CharField(
        max_length=20, choices=MafiaVoteMode.choices, default=MafiaVoteMode.ANY
    )
    automatic_phase_transition = models.BooleanField(default=True)
    day_discussion_enabled = models.BooleanField(default=True)

    # Atmosphere & Media settings
    night_media_url = models.CharField(max_length=500, blank=True, default='')
    day_media_url = models.CharField(max_length=500, blank=True, default='')
    elimination_media_url = models.CharField(max_length=500, blank=True, default='')
    victory_media_url = models.CharField(max_length=500, blank=True, default='')
    custom_theme = models.CharField(max_length=50, blank=True, default='default')

    # Frozen role distribution as JSON list of dicts
    role_distribution_snapshot = models.JSONField(
        default=list,
        help_text="Frozen list of {role_code, role_name, team, min_count, max_count, distribution_type}"
    )

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Snapshot for Game #{self.game_id} [{self.configuration_name}]"


# ---------------------------------------------------------------------------
# Game & Player Models (Phase 2 preserved, Phase 3 extended)
# ---------------------------------------------------------------------------

class Game(BaseEntityModel):
    """Game instance managed by a specific Bot instance in a Telegram Chat."""
    bot = models.ForeignKey(Bot, on_delete=models.CASCADE, related_name='games', db_index=True)
    chat_id = models.BigIntegerField(db_index=True, help_text="Telegram Group Chat ID")
    status = models.CharField(max_length=20, choices=GamePhase.choices, default=GamePhase.WAITING, db_index=True)
    phase = models.CharField(max_length=20, choices=GamePhase.choices, default=GamePhase.WAITING, db_index=True)
    mode = models.CharField(max_length=20, default='CLASSIC', choices=[('CLASSIC', 'Classic'), ('TEAM', 'Team')], db_index=True)
    round_number = models.PositiveIntegerField(default=1)
    phase_ends_at = models.DateTimeField(null=True, blank=True)
    winner_team = models.CharField(max_length=20, choices=RoleTeam.choices, null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    lobby_message_id = models.BigIntegerField(
        null=True,
        blank=True,
        help_text="Telegram Message ID of the active lobby message in group chat"
    )

    # Phase 3: optional link to pre-start configuration
    game_configuration = models.ForeignKey(
        GameConfiguration,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='games',
        help_text="Optional configuration used before game start. Snapshot is created on start.",
    )

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['bot', 'chat_id', 'status']),
        ]

    def __str__(self):
        return f"Game #{self.id} on Bot {self.bot.name} [{self.phase}]"


class Player(BaseEntityModel):
    """Player participant in a Game."""
    game = models.ForeignKey(Game, on_delete=models.CASCADE, related_name='players', db_index=True)
    telegram_user_id = models.BigIntegerField(db_index=True)
    username = models.CharField(max_length=255, blank=True, default='')
    display_name = models.CharField(max_length=255, blank=True, default='')
    role = models.ForeignKey(Role, on_delete=models.SET_NULL, null=True, blank=True, related_name='players')
    is_alive = models.BooleanField(default=True, db_index=True)
    health = models.PositiveIntegerField(default=100, help_text="Player health percentage")
    is_ready = models.BooleanField(default=False)
    eliminated_at = models.DateTimeField(null=True, blank=True)
    eliminated_reason = models.CharField(max_length=50, blank=True, default='')
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        unique_together = ('game', 'telegram_user_id')
        ordering = ['created_at']

    def __str__(self):
        return f"Player {self.display_name or self.username} ({'Alive' if self.is_alive else 'Dead'}, {self.health}% HP) in Game #{self.game_id}"

    @property
    def max_health(self) -> int:
        """Base 100% HP + bonus HP from Hero's max_defense."""
        from apps.economy.models import PlayerHero
        hero = PlayerHero.objects.filter(telegram_id=self.telegram_user_id, is_active=True).first()
        bonus = hero.max_defense if hero else 0
        return 100 + bonus



# ---------------------------------------------------------------------------
# Night Action & Vote Models (Phase 2 preserved)
# ---------------------------------------------------------------------------

class NightActionType(models.TextChoices):
    MAFIA_KILL = 'MAFIA_KILL', 'Mafia Kill'
    DOCTOR_PROTECT = 'DOCTOR_PROTECT', 'Doctor Protect'
    DETECTIVE_INVESTIGATE = 'DETECTIVE_INVESTIGATE', 'Detective Investigate'
    DETECTIVE_SHOOT = 'DETECTIVE_SHOOT', 'Detective Shoot'
    QOTIL_KILL = 'QOTIL_KILL', 'Qotil Kill'
    KEZUVCHI_VISIT = 'KEZUVCHI_VISIT', 'Kezuvchi Visit'
    DAYDI_VISIT = 'DAYDI_VISIT', 'Daydi Visit'
    ADVOKAT_PROTECT = 'ADVOKAT_PROTECT', 'Advokat Protect'
    UBIYTSA_KILL = 'UBIYTSA_KILL', 'Ubiytsa Kill'
    TUZOQCHI_TRAP = 'TUZOQCHI_TRAP', 'Tuzoqchi Trap'
    ZOMBI_BITE = 'ZOMBI_BITE', 'Zombi Bite'
    KIMYOGAR_POTION = 'KIMYOGAR_POTION', 'Kimyogar Potion'
    AXMOQ_VISIT = 'AXMOQ_VISIT', 'Axmoq Visit'
    BUQALAMUN_MORPH = 'BUQALAMUN_MORPH', 'Buqalamun Morph'
    RAIS_GIFT = 'RAIS_GIFT', 'Rais Gift'
    JOKER_BOXES = 'JOKER_BOXES', 'Joker Boxes'
    AFERIST_STEAL = 'AFERIST_STEAL', 'Aferist Steal'
    GAZABKOR_MARK = 'GAZABKOR_MARK', 'Gazabkor Mark'
    SEHRGAR_CHOICE = 'SEHRGAR_CHOICE', 'Sehrgar Choice'
    JURNALIST_INVESTIGATE = 'JURNALIST_INVESTIGATE', 'Jurnalist Investigate'
    SOTQIN_CHECK = 'SOTQIN_CHECK', 'Sotqin Check'
    ROBINGUD_SHOOT = 'ROBINGUD_SHOOT', 'Robin Gud Shoot'
    AYGOQCHI_SPY = 'AYGOQCHI_SPY', 'Aygoqchi Spy'
    KONCHI_MINE = 'KONCHI_MINE', 'Konchi Mine'
    FOTOPARATCHI_SNAP = 'FOTOPARATCHI_SNAP', 'Fotoparatchi Snap'
    QAROQCHI_ROB = 'QAROQCHI_ROB', 'Qaroqchi Rob'
    LABORANT_ACTION = 'LABORANT_ACTION', 'Laborant Action'
    QORBOBO_GIFT = 'QORBOBO_GIFT', 'Qorbobo Gift'
    OSHPAZ_FEED = 'OSHPAZ_FEED', 'Oshpaz Feed'
    SKIP = 'SKIP', 'Skip / Pass'


class NightAction(BaseEntityModel):
    """Persistent Night action record submitted by a player during NIGHT phase."""
    game = models.ForeignKey(Game, on_delete=models.CASCADE, related_name='night_actions', db_index=True)
    round = models.PositiveIntegerField()
    actor = models.ForeignKey(Player, on_delete=models.CASCADE, related_name='submitted_actions')
    target = models.ForeignKey(Player, on_delete=models.CASCADE, related_name='targeted_actions', null=True, blank=True)
    action_type = models.CharField(max_length=50, choices=NightActionType.choices)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        unique_together = ('game', 'round', 'actor')
        indexes = [
            models.Index(fields=['game', 'round', 'action_type']),
        ]

    def __str__(self):
        return f"[{self.action_type}] Actor: {self.actor.display_name} -> Target: {self.target.display_name if self.target else 'None'}"


class Vote(BaseEntityModel):
    """Persistent Vote record cast by a player during VOTING phase."""
    game = models.ForeignKey(Game, on_delete=models.CASCADE, related_name='votes', db_index=True)
    round = models.PositiveIntegerField()
    voter = models.ForeignKey(Player, on_delete=models.CASCADE, related_name='cast_votes')
    target = models.ForeignKey(Player, on_delete=models.CASCADE, related_name='received_votes')

    class Meta:
        unique_together = ('game', 'round', 'voter')
        indexes = [
            models.Index(fields=['game', 'round']),
        ]

    def __str__(self):
        return f"Vote Round {self.round}: {self.voter.display_name} -> {self.target.display_name}"


# ---------------------------------------------------------------------------
# Game Event Log Model (Immutable Persistent Lifecycle Trail)
# ---------------------------------------------------------------------------

class GameEventType(models.TextChoices):
    GAME_CREATED = 'GAME_CREATED', 'Game Created'
    PLAYER_JOINED = 'PLAYER_JOINED', 'Player Joined'
    PLAYER_LEFT = 'PLAYER_LEFT', 'Player Left'
    GAME_STARTED = 'GAME_STARTED', 'Game Started'
    ROLE_ASSIGNED = 'ROLE_ASSIGNED', 'Role Assigned'
    NIGHT_STARTED = 'NIGHT_STARTED', 'Night Started'
    NIGHT_ACTION = 'NIGHT_ACTION', 'Night Action'
    NIGHT_RESOLVED = 'NIGHT_RESOLVED', 'Night Resolved'
    DAY_STARTED = 'DAY_STARTED', 'Day Started'
    DISCUSSION_STARTED = 'DISCUSSION_STARTED', 'Discussion Started'
    VOTE_STARTED = 'VOTE_STARTED', 'Vote Started'
    VOTE_CAST = 'VOTE_CAST', 'Vote Cast'
    VOTE_RESOLVED = 'VOTE_RESOLVED', 'Vote Resolved'
    PLAYER_ELIMINATED = 'PLAYER_ELIMINATED', 'Player Eliminated'
    ROUND_COMPLETED = 'ROUND_COMPLETED', 'Round Completed'
    GAME_FINISHED = 'GAME_FINISHED', 'Game Finished'
    GAME_CANCELED = 'GAME_CANCELED', 'Game Canceled'


class GameEvent(BaseEntityModel):
    """Immutable persistent event log for game lifecycle, analytics, and replay."""
    game = models.ForeignKey(Game, on_delete=models.CASCADE, related_name='events', db_index=True)
    event_type = models.CharField(max_length=40, choices=GameEventType.choices, db_index=True)
    round = models.PositiveIntegerField(default=1)
    phase = models.CharField(max_length=20, default=GamePhase.WAITING)
    actor = models.ForeignKey(Player, on_delete=models.SET_NULL, null=True, blank=True, related_name='actor_events')
    target = models.ForeignKey(Player, on_delete=models.SET_NULL, null=True, blank=True, related_name='target_events')
    message = models.TextField(blank=True, default='')
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['game', 'event_type', 'round']),
            models.Index(fields=['game', 'created_at']),
        ]

    def __str__(self):
        return f"Event({self.game_id} | R{self.round} {self.phase}: {self.event_type} - {self.message[:40]})"

