from django.db import models
from django.conf import settings
from apps.common.models import BaseEntityModel


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class PaymentStatus(models.TextChoices):
    PENDING = 'PENDING', 'Pending'
    PROCESSING = 'PROCESSING', 'Processing'
    SUCCEEDED = 'SUCCEEDED', 'Succeeded'
    COMPLETED = 'COMPLETED', 'Completed'  # Legacy choice preserved
    FAILED = 'FAILED', 'Failed'
    CANCELED = 'CANCELED', 'Canceled'
    REFUNDED = 'REFUNDED', 'Refunded'


class PaymentProviderType(models.TextChoices):
    MANUAL = 'MANUAL', 'Manual'
    STRIPE = 'STRIPE', 'Stripe'
    PAYME = 'PAYME', 'Payme'
    CLICK = 'CLICK', 'Click'


class WebhookStatus(models.TextChoices):
    PENDING = 'PENDING', 'Pending'
    PROCESSED = 'PROCESSED', 'Processed'
    FAILED = 'FAILED', 'Failed'
    IGNORED = 'IGNORED', 'Ignored'


class InvoiceStatus(models.TextChoices):
    DRAFT = 'DRAFT', 'Draft'
    OPEN = 'OPEN', 'Open'
    PAID = 'PAID', 'Paid'
    UNCOLLECTIBLE = 'UNCOLLECTIBLE', 'Uncollectible'
    VOID = 'VOID', 'Void'


class RefundStatus(models.TextChoices):
    PENDING = 'PENDING', 'Pending'
    SUCCEEDED = 'SUCCEEDED', 'Succeeded'
    FAILED = 'FAILED', 'Failed'


# ---------------------------------------------------------------------------
# Domain Models
# ---------------------------------------------------------------------------

class Payment(BaseEntityModel):
    """
    Immutable payment transaction record.
    Status changes originate ONLY from verified backend logic or provider webhooks.
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='payments',
        db_index=True,
    )
    subscription = models.ForeignKey(
        'subscriptions.Subscription',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='payments',
        db_index=True,
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default='USD')
    status = models.CharField(
        max_length=20,
        choices=PaymentStatus.choices,
        default=PaymentStatus.PENDING,
        db_index=True,
    )
    provider = models.CharField(
        max_length=50,
        choices=PaymentProviderType.choices,
        default=PaymentProviderType.MANUAL,
        db_index=True,
    )
    provider_payment_id = models.CharField(
        max_length=255, null=True, blank=True, db_index=True
    )
    # Legacy field preserved for backward compat
    transaction_id = models.CharField(max_length=255, null=True, blank=True)

    paid_at = models.DateTimeField(null=True, blank=True)
    failure_reason = models.TextField(blank=True, default='')
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['provider', 'provider_payment_id']),
        ]

    def __str__(self):
        return f"Payment [{self.status}] ${self.amount} by {self.user.email} via {self.provider}"


class PaymentWebhookEvent(BaseEntityModel):
    """
    Audit log & idempotency lock for payment webhooks.
    The same event MUST NOT be processed twice.
    """
    provider = models.CharField(max_length=50, choices=PaymentProviderType.choices, db_index=True)
    event_id = models.CharField(max_length=255, db_index=True)
    event_type = models.CharField(max_length=100, db_index=True)
    payload_hash = models.CharField(
        max_length=64,
        db_index=True,
        help_text="SHA-256 hash of raw webhook payload for deduplication."
    )
    status = models.CharField(
        max_length=20,
        choices=WebhookStatus.choices,
        default=WebhookStatus.PENDING,
        db_index=True,
    )
    received_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    processing_error = models.TextField(blank=True, default='')
    raw_payload = models.JSONField(default=dict)

    class Meta:
        ordering = ['-received_at']
        unique_together = [('provider', 'event_id')]

    def __str__(self):
        return f"Webhook [{self.provider}/{self.event_type}] Event#{self.event_id} ({self.status})"


class Invoice(BaseEntityModel):
    """
    Billing invoice entity for user billing history and receipts.
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='invoices',
        db_index=True,
    )
    subscription = models.ForeignKey(
        'subscriptions.Subscription',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='invoices',
    )
    payment = models.ForeignKey(
        Payment,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='invoices',
    )
    invoice_number = models.CharField(max_length=100, unique=True, db_index=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default='USD')
    status = models.CharField(
        max_length=20,
        choices=InvoiceStatus.choices,
        default=InvoiceStatus.PAID,
        db_index=True,
    )
    issued_at = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-issued_at']

    def __str__(self):
        return f"Invoice #{self.invoice_number} - ${self.amount} ({self.status})"


class RefundRecord(BaseEntityModel):
    """
    Refund transaction entity.
    Maintains financial history immutability — never mutates original Payment record directly.
    """
    payment = models.ForeignKey(Payment, on_delete=models.CASCADE, related_name='refunds')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    reason = models.TextField(blank=True, default='')
    provider_refund_id = models.CharField(max_length=255, blank=True, default='')
    status = models.CharField(
        max_length=20,
        choices=RefundStatus.choices,
        default=RefundStatus.PENDING,
    )

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Refund ${self.amount} for Payment #{self.payment_id} [{self.status}]"
