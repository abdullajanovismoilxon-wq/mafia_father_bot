import json
from django.db import models
from django.conf import settings
from django.utils.text import slugify
from apps.common.models import BaseEntityModel


class TemplateType(models.TextChoices):
    SYSTEM = 'SYSTEM', 'System Template'
    USER = 'USER', 'User Template'


class TemplateVisibility(models.TextChoices):
    PRIVATE = 'PRIVATE', 'Private (Owner Only)'
    PUBLIC = 'PUBLIC', 'Public (All Users)'


class GameTemplateStatus(models.TextChoices):
    ACTIVE = 'ACTIVE', 'Active'
    ARCHIVED = 'ARCHIVED', 'Archived'
    DRAFT = 'DRAFT', 'Draft'


class GameTemplate(BaseEntityModel):
    """
    Reusable game configuration template.

    System templates (owner=None, template_type=SYSTEM) are created by platform admins.
    User templates (owner=<User>, template_type=USER) belong to specific tenants.
    Public templates can be copied by other users but not directly modified.

    IMPORTANT: Changing a template never affects games that already started —
    those games use a ConfigurationSnapshot taken at start time.
    """
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='game_templates',
        db_index=True,
        help_text="null = system template, non-null = user-owned template",
    )
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, blank=True, db_index=True)
    description = models.TextField(blank=True, default='')

    template_type = models.CharField(
        max_length=10,
        choices=TemplateType.choices,
        default=TemplateType.USER,
        db_index=True,
    )
    visibility = models.CharField(
        max_length=10,
        choices=TemplateVisibility.choices,
        default=TemplateVisibility.PRIVATE,
        db_index=True,
    )
    status = models.CharField(
        max_length=10,
        choices=GameTemplateStatus.choices,
        default=GameTemplateStatus.ACTIVE,
        db_index=True,
    )
    version = models.PositiveIntegerField(default=1)

    # Source template (if this was copied from another template)
    source_template = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='copies',
        help_text="Original template this was duplicated from.",
    )

    # Game mode for this template
    game_mode = models.CharField(
        max_length=20,
        choices=[
            ('CLASSIC', 'Classic'),
            ('QUICK', 'Quick'),
            ('CUSTOM', 'Custom'),
            ('TOURNAMENT', 'Tournament'),
        ],
        default='CLASSIC',
    )

    # Structured configuration data (frozen snapshot of GameConfiguration fields)
    configuration_data = models.JSONField(
        default=dict,
        help_text=(
            "Serialized game configuration: minimum_players, maximum_players, "
            "night_duration, discussion_duration, voting_duration, allow_self_vote, "
            "allow_self_protection, reveal_role_on_elimination, tie_behavior, "
            "mafia_vote_mode, automatic_phase_transition, day_discussion_enabled"
        ),
    )

    # Role distribution rules snapshot
    role_distribution_data = models.JSONField(
        default=list,
        help_text=(
            "List of role distribution rules: "
            "[{role_code, role_name, team, min_count, max_count, distribution_type}, ...]"
        ),
    )

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['owner', 'status', 'visibility']),
            models.Index(fields=['template_type', 'visibility', 'status']),
        ]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)[:255]
        super().save(*args, **kwargs)

    def get_default_configuration(self) -> dict:
        """Returns configuration_data with sane defaults for missing fields."""
        defaults = {
            'minimum_players': 4,
            'maximum_players': 20,
            'night_duration': 60,
            'discussion_duration': 120,
            'voting_duration': 60,
            'allow_self_vote': False,
            'allow_self_protection': False,
            'reveal_role_on_elimination': True,
            'tie_behavior': 'NO_ELIMINATION',
            'mafia_vote_mode': 'ANY',
            'automatic_phase_transition': True,
            'day_discussion_enabled': True,
        }
        defaults.update(self.configuration_data or {})
        return defaults

    def __str__(self):
        owner_label = self.owner.email if self.owner else 'SYSTEM'
        return f"[{owner_label}] {self.name} ({self.template_type}/{self.visibility})"


class BotTemplate(BaseEntityModel):
    """
    Preset Bot setup template that bundles a language and default game template.
    Extended in Phase 3 to support ownership and game template linkage.
    """
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='bot_templates',
        db_index=True,
    )
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, default='')
    default_language = models.CharField(max_length=10, default='en')
    default_game_template = models.ForeignKey(
        GameTemplate,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='bot_templates',
    )
    game_mode = models.CharField(
        max_length=20,
        choices=[
            ('CLASSIC', 'Classic'),
            ('QUICK', 'Quick'),
            ('CUSTOM', 'Custom'),
            ('TOURNAMENT', 'Tournament'),
        ],
        default='CLASSIC',
    )
    # Legacy field for backward compat
    config_preset = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} (lang={self.default_language})"
