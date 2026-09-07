# MAFIA BOT FATHER — MARKETPLACE, DIAMONDS & VIP SYSTEM

## 1. Catalog & Packages
Inspired by standard Telegram Mafia bots, the marketplace offers structured diamond packages with dual USD/UZS pricing:

| Code | Diamond Amount | Price (USD) | Price (UZS ≈ 12,800) |
|------|---------------|-------------|---------------------|
| `DIA_1` | 1 💎 | $0.20 | ~2,560 so'm |
| `DIA_5` | 5 💎 | $0.80 | ~10,240 so'm |
| `DIA_10` | 10 💎 | $1.36 | ~17,408 so'm |
| `DIA_15` | 15 💎 | $1.90 | ~24,320 so'm |
| `DIA_30` | 30 💎 | $3.50 | ~44,800 so'm |
| `DIA_50` | 50 💎 | $5.50 | ~70,400 so'm |
| `DIA_250` | 250 💎 | $25.00 | ~320,000 so'm |
| `DIA_1000` | 1000 💎 | $90.00 | ~1,152,000 so'm |

## 2. VIP Memberships
- **VIP Gold (`VIP_GOLD_30`)**: 30 days active duration, costs 50 💎. Unlocks golden badge, 2x coin bonuses, and access to custom templates.
- **VIP Diamond (`VIP_DIAMOND_30`)**: 30 days active duration, costs 100 💎. Unlocks diamond crown badge, custom role creation, and VIP leaderboard priority.

## 3. P2P Payment Workflow
1. User requests purchase via bot or web dashboard.
2. System generates unique `PaymentOrder` (`#ORD-...`) with `PENDING_REVIEW` status.
3. User completes transfer via Payme / Click / Card and notifies support.
4. Administrator reviews receipt in `/admin/payments` and clicks **Approve**.
5. System atomically credits diamonds to user's virtual wallet and records an immutable audit log.
