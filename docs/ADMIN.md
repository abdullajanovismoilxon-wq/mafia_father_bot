# MAFIA BOT FATHER — ADMIN CONTROL PLANE & GOVERNANCE

## 1. Overview
The MAFIA BOT FATHER Admin Control Plane provides platform administrators and staff with real-time operational governance, multi-tenant bot runtime fleet supervision, virtual economy controls, and an immutable audit trail.

## 2. RBAC Roles Hierarchy
| Role | Access Level | Capabilities |
|------|-------------|--------------|
| `SUPERADMIN` | Platform Owner | Full unrestricted platform access, user deletion, role promotions |
| `ADMIN` | Administrator | Bot runtime suspension/resumption, balance adjustments, payment approvals, game inspection |
| `MODERATOR` | Operations Staff | Game monitoring, participant review, player warnings |
| `SUPPORT` | Customer Support | User lookup, ticket troubleshooting |
| `USER` | Tenant / Player | Bot creation, personal game hosting, wallet & inventory |

## 3. Administrative REST Endpoints
- `GET /api/v1/admin/overview/` — Platform health metrics, active games, bot runtimes, revenue, and currency in circulation.
- `GET /api/v1/admin/bots/` — Fleet status listing.
  - `POST /api/v1/admin/bots/{id}/suspend/` — Suspends bot.
  - `POST /api/v1/admin/bots/{id}/resume/` — Resumes bot.
  - `POST /api/v1/admin/bots/{id}/restart/` — Restarts runtime process.
  - `POST /api/v1/admin/bots/{id}/stop/` — Gracefully stops runtime.
- `GET /api/v1/admin/games/` — Live game session monitor.
- `GET /api/v1/admin/users/` — User management.
  - `POST /api/v1/admin/users/{id}/suspend/` — Suspends tenant/user account.
  - `POST /api/v1/admin/users/{id}/activate/` — Reactivates suspended account.
  - `POST /api/v1/admin/users/{id}/grant_vip/` — Grants VIP membership (GOLD/DIAMOND).
  - `POST /api/v1/admin/users/{id}/adjust_balance/` — Credits or debits virtual wallet.
- `GET /api/v1/admin/payment-orders/` — P2P / Manual payment review queue.
  - `POST /api/v1/admin/payment-orders/{order_id}/review/` — Approves or rejects payment order with audit trail.
- `GET /api/v1/admin/audit-logs/` — Immutable audit trail with admin IP, action, timestamp, and target metadata.

## 4. Web UI Admin Dashboard
Located at `/admin` (Next.js Dashboard) and `/django-admin/` (Django Model Administration).
Includes interactive tabs: Overview, Bots Control, Games Monitor, User Management, Payment Orders, and Audit Logs.
