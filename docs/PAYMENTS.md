# Payment Provider Abstraction & Webhook Security

The platform supports multiple payment gateways (**Stripe**, **Payme**, **Click**) via Dependency Inversion.

## Payment Provider Abstraction

```text
                     ┌──────────────────────────┐
                     │   BasePaymentProvider    │
                     └─────────────▲────────────┘
                                   │
             ┌─────────────────────┼─────────────────────┐
             │                     │                     │
   ┌─────────┴──────────┐┌─────────┴──────────┐┌─────────┴──────────┐
   │   StripeProvider   ││   PaymeProvider    ││    ClickProvider   │
   └────────────────────┘└────────────────────┘└────────────────────┘
```

Each provider implements:
- `create_checkout_session(...)`
- `verify_webhook(...)`
- `process_webhook_event(...)`
- `refund_payment(...)`
- `get_payment_status(...)`

## Webhook Security & Idempotency Pipeline

1. **Untrusted Input**: Webhooks do NOT use JWT tokens.
2. **Signature Verification**:
   - **Stripe**: `stripe-signature` HMAC-SHA256 timestamp validation.
   - **Payme**: `Authorization: Basic <base64(Paycom:secret_key)>`.
   - **Click**: MD5 signature hash `md5(click_trans_id + service_id + secret_key + merchant_trans_id + amount + action + sign_time)`.
3. **Payload Deduplication**: SHA-256 hash of payload stored in `PaymentWebhookEvent`. Duplicate hashes return 200 OK without re-processing.
4. **Atomic Transaction**: Updating `Payment`, activating `Subscription`, and issuing `Invoice` executed inside `transaction.atomic()`.

## Safe Failure Behavior
If provider secret keys are absent in environment, `validate_configuration()` raises `ProviderConfigurationError` (503 Service Unavailable or 400 Bad Request) instead of throwing unhandled exceptions.
