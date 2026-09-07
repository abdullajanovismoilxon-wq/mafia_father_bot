import uuid
from django.contrib.auth.models import AbstractUser
from django.db import models


class UserRole(models.TextChoices):
    SUPERADMIN = 'SUPERADMIN', 'SuperAdmin'
    ADMIN = 'ADMIN', 'Group Owner / Admin'
    MODERATOR = 'MODERATOR', 'Group Co-Admin / Moderator'
    SUPPORT = 'SUPPORT', 'Support'
    USER = 'USER', 'User'


class User(AbstractUser):
    """Custom User model with UUID primary key and extended profile fields."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True, db_index=True)
    telegram_id = models.BigIntegerField(null=True, blank=True, unique=True, db_index=True)
    group_name = models.CharField(
        max_length=255,
        blank=True,
        default='',
        help_text="Name of the Telegram Group managed by this admin."
    )
    parent_admin = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='co_admins',
        help_text="Parent Group Owner if this account is a co-admin."
    )
    role = models.CharField(
        max_length=20,
        choices=UserRole.choices,
        default=UserRole.USER,
        db_index=True,
        help_text="User authorization role on the platform."
    )
    is_suspended = models.BooleanField(
        default=False,
        help_text="Whether the user account is suspended by administrator."
    )
    is_platform_owner = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Platform Owner account with unrestricted privileges (e.g. @ismoilo9)."
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']

    class Meta:
        ordering = ['-created_at']

    @property
    def is_admin_or_staff(self) -> bool:
        return self.is_superuser or self.is_staff or self.role in [UserRole.SUPERADMIN, UserRole.ADMIN]

    @property
    def is_moderator_or_higher(self) -> bool:
        return self.is_admin_or_staff or self.role == UserRole.MODERATOR

    @property
    def effective_owner(self):
        """Returns the primary Group Owner user instance for multi-admin group sharing."""
        return self.parent_admin if self.parent_admin else self

    def __str__(self):
        return f"{self.email} ({self.username}) [{self.role}]"
