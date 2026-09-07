# MAFIA BOT FATHER — Production SaaS Platform (Phases 1–5 Complete)

> **Enterprise-grade multi-tenant SaaS platform for creating, configuring, deploying, monetizing, and managing Telegram Mafia Game bots.**
> *Concept: Telegram BotFather creates Telegram bots → Mafia Bot Father creates and manages Mafia game bots.*

---

## 🚀 Key Platform Capabilities

- **Shared Core Mafia Game Engine**: State machine handling lobbies, night actions (Kill, Protect, Investigate), day voting, elimination, and win conditions.
- **Bot Registry & Encrypted Credentials**: AES-128 CBC Fernet symmetric token encryption with zero plaintext tokens stored.
- **Custom Roles, Abilities & Templates**: Flexible, data-driven role editor, deterministic seeding, and tournament modes.
- **Subscription & Monetization Engine**: Multi-provider payments (Stripe, Payme, Click), automatic plan entitlement enforcement, and webhook idempotency.
- **Virtual Economy & Diamonds Marketplace**: Multi-currency wallet (USD, UZS, 💎 Diamonds, 🪙 Coins), atomic `select_for_update()` P2P transfers, VIP subscriptions, and diamond package store.
- **Player Profiles & Achievements**: Win streak tracking, role-specific metrics, automatic achievement unlocks, and global leaderboards.
- **Administrative Control Plane**: Real-time fleet health overview, bot suspension/resumption, user management, P2P payment review queue, and immutable audit logs.
- **Production DevOps**: Docker Compose, Kubernetes manifests (Deployments, Services, HPA, Ingress with TLS), GitHub Actions CI/CD pipeline, and 100% test coverage.

---

## 🛠 Tech Stack

- **Backend**: Python 3.11/3.12, Django 5.0, Django REST Framework, SimpleJWT, Celery, Redis, PostgreSQL, aiogram 3.x, drf-spectacular.
- **Frontend**: Next.js 14 (App Router, 27 pages), TypeScript, Tailwind CSS, Lucide Icons, Axios.
- **DevOps**: Docker, Docker Compose, Kubernetes, Nginx, GitHub Actions CI/CD.

---

## 🏁 Quick Start with Docker Compose

1. Copy `.env.production.example` to `.env`:
```bash
cp .env.production.example .env
```

2. Start the full multi-container stack:
```bash
docker-compose up --build -d
```

3. Access Platform Services:
- **Web UI & Dashboard**: `http://localhost` (or `http://localhost:3000`)
- **Admin Control Plane**: `http://localhost/admin`
- **Player Profile & Economy**: `http://localhost/profile`
- **Django Admin**: `http://localhost/django-admin/`
- **REST API V1**: `http://localhost/api/v1/`
- **Swagger UI**: `http://localhost/api/v1/schema/swagger-ui/`
- **Health / Readiness Probes**: `http://localhost/health/` & `http://localhost/health/ready/`

---

## 🧪 Running Tests

Run the complete 103-test suite covering all 5 phases:
```bash
cd backend
python manage.py test tests --verbosity=2
```
*Result: 103 / 103 tests passing (100% OK).*

---

## 📚 Documentation Index
- [`docs/ADMIN.md`](docs/ADMIN.md) — Admin Control Plane, RBAC, and Audit Logs
- [`docs/ECONOMY.md`](docs/ECONOMY.md) — Virtual Wallet, Transfers & Anti-Fraud
- [`docs/MARKETPLACE.md`](docs/MARKETPLACE.md) — Diamond packages, VIP & P2P Orders
- [`docs/SECURITY.md`](docs/SECURITY.md) — Security Hardening, Token Encryption & Webhooks
- [`docs/BACKUPS.md`](docs/BACKUPS.md) — Automated Database Dumps & Disaster Recovery
- [`docs/MONITORING.md`](docs/MONITORING.md) — Liveness/Readiness Probes & Observability
- [`docs/KUBERNETES.md`](docs/KUBERNETES.md) — Kubernetes Deployments, Ingress & HPA
- [`docs/TESTING.md`](docs/TESTING.md) — Test Suite Summary
