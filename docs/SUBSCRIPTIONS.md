# Subscription Lifecycle

```
TRIALING ──> ACTIVE ──> PAST_DUE ──> EXPIRED
               │
               └──> CANCELED (at period end)
```

## Subscription States
- **TRIALING**: Trial period active.
- **ACTIVE**: Paid or free tier subscription valid.
- **PAST_DUE**: Payment attempt failed, grace period applied.
- **CANCELED**: Scheduled for cancellation when `current_period_end` is reached.
- **EXPIRED**: Period ended, access revoked.

## Cancellation & Retention
When a user cancels, `cancel_at_period_end` is set to `True`. Access is preserved until `current_period_end`.
Users can resume before period expiration via `POST /api/v1/billing/resume/`.
