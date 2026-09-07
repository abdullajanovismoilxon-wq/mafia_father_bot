# MAFIA BOT FATHER — OBSERVABILITY, HEALTH CHECKS & MONITORING

## 1. Health Endpoints
- `GET /health/` — Quick liveness check. Returns `{"status": "healthy", "service": "MAFIA BOT FATHER Control Plane API"}`.
- `GET /health/live/` — Kubernetes liveness probe endpoint. Returns `{"status": "alive"}`.
- `GET /health/ready/` — Deep readiness probe checking:
  - Database connectivity (`SELECT 1`)
  - Redis connectivity (`PING`)
  - Bot runtime statuses (Running bots count & Error bots count)

## 2. Metrics & Admin Overview
- `GET /api/v1/admin/overview/` provides live real-time aggregates for:
  - Total users, active vs suspended
  - Bot runtimes: running vs error vs suspended
  - Games: active vs finished vs today
  - Revenue: total, daily, monthly USD
  - Virtual Economy: Money, Diamonds, Coins in circulation
  - Subscriptions & VIP members
