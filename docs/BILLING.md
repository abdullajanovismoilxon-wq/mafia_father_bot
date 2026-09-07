# Billing System Architecture

The **MAFIA BOT FATHER** billing domain provides multi-tenant monetization, plan management, checkout session initiation, and payment history.

## Conceptual Model

```
User ──> Subscription ──> Plan ──> PlanFeature (Entitlements) ──> Resource Limits
                                          │
                                          ▼
                                     Payment History & Invoices
```

## Core Principles
1. **Decoupled Architecture**: Plans and features are DB entities (`Plan`, `PlanFeature`), not hardcoded logic.
2. **Immutable Payments**: Financial records are append-only. Refunds and status transitions do not mutate original transactions.
3. **No Frontend Reliance**: Frontend never dictates subscription status. Only verified provider webhooks trigger activation.
4. **Multi-Tenancy Isolation**: Users can access only their own billing data, payments, and invoices.

## API Endpoints

- `GET /api/v1/billing/plans/` — Active SaaS pricing plans & feature caps.
- `GET /api/v1/billing/subscription/` — Current user subscription details.
- `POST /api/v1/billing/checkout/` — Initiate provider checkout session (`STRIPE`, `PAYME`, `CLICK`).
- `POST /api/v1/billing/cancel/` — Schedule cancellation at period end.
- `POST /api/v1/billing/resume/` — Resume scheduled cancellation.
- `GET /api/v1/billing/payments/` — User payment transaction log.
- `GET /api/v1/billing/invoices/` — User invoice records.
- `GET /api/v1/billing/usage/` — Real-time resource usage vs plan limits.
- `GET /api/v1/billing/entitlements/` — Feature gates summary.
