# MAFIA BOT FATHER — PLATFORM SECURITY & HARDENING

## 1. Secrets & Credentials Protection
- **Zero Plaintext Telegram Tokens**: Telegram bot tokens are encrypted at rest using AES-128 CBC via Fernet symmetric encryption (`ENCRYPTION_KEY`). Tokens are never stored in plaintext and are masked in API responses (`123456:ABC...XYZ`).
- **JWT Authentication**: Short-lived Access Tokens (60 min) + Refresh Tokens with rotation.
- **Environment Isolation**: No hardcoded API keys, database credentials, or secret keys in source code.

## 2. Multi-Tenant Data Isolation
- Queries are strictly scoped to `request.user` across Bots, Games, Tournaments, Payments, Invoices, and Wallets.
- Admin endpoints (`/api/v1/admin/*`) require `IsAdminOrStaffUser` permission; non-admin users receive `403 Forbidden`.

## 3. Webhook Idempotency & Signature Verification
- **Stripe**: HMAC SHA-256 signature verification (`Stripe-Signature` header).
- **Payme**: HTTP Basic Authentication header verification (`Payme-Authorization`).
- **Click**: MD5 / SHA-256 digest verification (`sign_string = md5(click_trans_id + service_id + secret_key + amount + action + sign_time)`).
- **Idempotency**: Webhook payload hashes are cached in Redis to guarantee duplicate webhook calls are processed safely only once.

## 4. Virtual Ledger Integrity
- Atomic transactions with `select_for_update()` prevent double-spending in concurrency.
- Daily transfer limits and velocity checks mitigate fraud.
