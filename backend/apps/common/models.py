import uuid
from django.db import models
from django.conf import settings


class UUIDModel(models.Model):
    """Abstract base model supplying UUID primary key."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    class Meta:
        abstract = True


class TimeStampedModel(models.Model):
    """Abstract base model supplying created_at and updated_at timestamps."""
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class BaseEntityModel(UUIDModel, TimeStampedModel):
    """Combined base model with UUID primary key and timestamps."""
    class Meta:
        abstract = True


class AuditLog(BaseEntityModel):
    """Structured audit log model for security, credential changes, and system operations."""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='audit_logs'
    )
    action = models.CharField(max_length=100, db_index=True)
    resource_type = models.CharField(max_length=100, db_index=True)
    resource_id = models.CharField(max_length=255, null=True, blank=True)
    details = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['resource_type', 'resource_id']),
            models.Index(fields=['user', 'action']),
        ]

    def __str__(self):
        return f"[{self.created_at}] {self.action} by {self.user or 'System'}"


class AdminAuditAction(models.TextChoices):
    GRANT_VIP = 'GRANT_VIP', 'Grant VIP'
    REVOKE_VIP = 'REVOKE_VIP', 'Revoke VIP'
    SUSPEND_USER = 'SUSPEND_USER', 'Suspend User'
    ACTIVATE_USER = 'ACTIVATE_USER', 'Activate User'
    SUSPEND_BOT = 'SUSPEND_BOT', 'Suspend Bot'
    RESUME_BOT = 'RESUME_BOT', 'Resume Bot'
    RESTART_BOT = 'RESTART_BOT', 'Restart Bot'
    GRANT_DIAMONDS = 'GRANT_DIAMONDS', 'Grant Diamonds'
    ADJUST_BALANCE = 'ADJUST_BALANCE', 'Adjust Balance'
    APPROVE_PAYMENT = 'APPROVE_PAYMENT', 'Approve Payment'
    REJECT_PAYMENT = 'REJECT_PAYMENT', 'Reject Payment'
    CHANGE_PLAN = 'CHANGE_PLAN', 'Change Plan'
    CREATE_MARKET_ITEM = 'CREATE_MARKET_ITEM', 'Create Market Item'
    UPDATE_MARKET_ITEM = 'UPDATE_MARKET_ITEM', 'Update Market Item'
    SYSTEM_CONFIG_CHANGE = 'SYSTEM_CONFIG_CHANGE', 'System Config Change'


class AdminAuditLog(BaseEntityModel):
    """Immutable audit trail for privileged administrator actions."""
    admin = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='admin_actions'
    )
    action = models.CharField(max_length=50, choices=AdminAuditAction.choices, db_index=True)
    target_type = models.CharField(max_length=50, db_index=True)
    target_id = models.CharField(max_length=255, null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    result = models.CharField(max_length=20, default='SUCCESS')

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['action', 'created_at']),
            models.Index(fields=['target_type', 'target_id']),
            models.Index(fields=['admin', 'action']),
        ]

    def __str__(self):
        return f"[{self.created_at}] Admin {self.admin} performed {self.action} on {self.target_type}:{self.target_id}"
