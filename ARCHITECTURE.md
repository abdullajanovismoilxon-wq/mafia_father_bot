# MAFIA BOT FATHER — SaaS Platform Architectural Blueprint

## Executive Overview
**MAFIA BOT FATHER** is a scalable, multi-tenant SaaS platform designed to create, configure, deploy, and manage multiple Telegram Mafia game bots ("Telegram BotFather → creates Telegram bots; Mafia Bot Father → creates and manages Mafia game bots").

The platform enforces the core architectural principle:
> **ONE GAME ENGINE, MANY BOT INSTANCES.**

The system separates concerns into a **Control Plane** (Django REST API + Next.js Web Dashboard) and a **Runtime Plane** (aiogram Bot Runtime Engine + Workers).

---

## 1. System Architecture Diagram

```text
                    ┌─────────────────────┐
                    │     Next.js Web     │
                    │      Dashboard      │
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │    Django REST API  │
                    │    Control Plane    │
                    └──────────┬──────────┘
                               │
              ┌────────────────┼────────────────┐
              │                │                │
              ▼                ▼                ▼
        PostgreSQL           Redis           Celery
              │                │                │
              │                │                ▼
              │                │         Background Tasks
              │                │
              └────────────────┼────────────────┐
                               │                │
                               ▼                ▼
                       Bot Registry       Bot Runtime (aiogram)
                                                │
                              ┌─────────────────┼───────────────┐
                              │                 │               │
                              ▼                 ▼               ▼
                           Bot #1            Bot #2          Bot #N
                              │                 │               │
                              └─────────────────┼───────────────┘
                                                │
                                           Telegram API
```

---

## 2. Layer Responsibilities

### Control Plane (Django API)
- User Authentication & Account Management (JWT)
- Multi-tenant Bot Registry & Configuration Management
- Subscription & Billing Tracking (Phase 1 Foundation)
- Credential Security (Fernet Token Encryption)
- System Audit Logging & Health Monitoring

### Runtime Plane (aiogram Engine)
- Shared Telegram Bot Game Engine
- Dynamic Bot Instance Lifecycle (STARTING, RUNNING, STOPPING, OFFLINE)
- Isolated Bot Configuration & State Management per Tenant Bot
- Long-polling & Webhook handling via scalable workers

---

## 3. Multi-Tenancy Architecture & Security

Every entity (Bot, Credential, Configuration, Game, Analytics) is strictly isolated per tenant (`User`).

```text
User A
  ├── Bot A1 (Token Encrypted)
  │     └── BotConfiguration A1
  └── Bot A2 (Token Encrypted)

User B
  └── Bot B1 (Token Encrypted)
```

- **Query-Level Enforcement**: DRF views implement `get_queryset()` restricted to `filter(owner=request.user)`.
- **Permission-Level Enforcement**: `IsOwnerPermission` ensures no cross-tenant object manipulation.
- **Credential Security**: Telegram Bot Tokens are encrypted symmetrically via `cryptography.fernet.Fernet` prior to DB storage. Plaintext tokens are NEVER logged, exposed in REST API responses, or stored in plaintext.

---

## 4. Backend Logical Application Layout

```text
backend/
├── config/             # Django settings, URLs, WSGI/ASGI, Celery setup
├── apps/
│   ├── users/          # Custom User model, JWT authentication endpoints
│   ├── common/         # Base models, Fernet encryption service, permissions, health views
│   ├── bots/           # Bot Registry, BotCredentials, BotConfiguration models & APIs
│   ├── subscriptions/  # Subscription model foundation & plan tiers
│   ├── payments/       # Payment transaction record foundation
│   ├── templates/      # GameTemplate & BotTemplate models foundation
│   ├── games/          # Architectural models (Game, Player, Role)
│   └── analytics/      # Audit log & analytics query endpoints
├── bot_runtime/        # Shared aiogram game engine & bot instance manager abstraction
├── manage.py
├── requirements/       # Modular python requirements (base.txt, dev.txt)
└── tests/              # Test suite (auth, user isolation, encryption, health checks)
```

---

## 5. Bot Lifecycle & Status State Machine

### Bot Registry Status
- `PENDING`: Newly created bot awaiting initial token validation.
- `ACTIVE`: Fully configured and authorized bot.
- `PAUSED`: Bot suspended temporarily by owner.
- `SUSPENDED`: Bot disabled due to subscription limits or policy.
- `ERROR`: Bot configuration or credential invalid.
- `DELETED`: Soft-deleted bot entity.

### Runtime Status
- `OFFLINE`: Instance not executing.
- `STARTING`: Process initialisation.
- `RUNNING`: Polling / receiving Telegram updates.
- `STOPPING`: Graceful shutdown signal.
- `ERROR`: Runtime crash or API connection failure.

---

## 6. Docker & Infrastructure Blueprint

Services defined in `docker-compose.yml`:
1. `postgres`: PostgreSQL 16 DB with persistent storage volume.
2. `redis`: Redis 7 in-memory store for Celery message broker & state cache.
3. `backend`: Django WSGI / Gunicorn control plane API server.
4. `celery_worker`: Background process execution & bot runtime manager worker.
5. `celery_beat`: Periodic scheduled task scheduler.
6. `frontend`: Next.js 14 web dashboard server.
7. `nginx`: High-performance reverse proxy routing `/api/` to Django and `/` to Next.js.

---

## 7. Phase 3 Architecture: Configuration, Roles, Templates & Tournaments

```text
┌───────────────────────────────────────────────────────────────────┐
│                    MAFIA BOT FATHER PLATFORM                      │
├─────────────────┬─────────────────┬───────────────┬───────────────┤
│ Config Engine   │ Role System     │ Templates     │ Tournaments   │
│ - Rules (Data)  │ - System Roles  │ - System Tpls │ - Multi-Round │
│ - Snapshotting  │ - Custom Roles  │ - User Tpls   │ - Grouping    │
│ - Durations     │ - RoleAbilities │ - Duplication │ - Scoring     │
└────────┬────────┴────────┬────────┴───────┬───────┴───────┬───────┘
         │                 │                │               │
         └─────────────────┼────────────────┴───────────────┘
                           ▼
              Shared Game Engine Runtimes
```

### Core Innovations in Phase 3
1. **Configuration Snapshotting**: `ConfigurationSnapshot` freezes configuration rules at game start. Config edits never corrupt active games.
2. **Declarative Role Abilities**: Role capabilities (KILL, PROTECT, INVESTIGATE) are DB entries, NOT hardcoded code branches.
3. **Template Duplication**: Public/System templates can be duplicated to user accounts as editable copies.
4. **Deterministic Tournament Engine**: `TournamentGroupingService` and `TournamentScoringService` provide isolated, testable algorithms.

