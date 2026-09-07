# MAFIA BOT FATHER — VIRTUAL ECONOMY & WALLET SYSTEM

## 1. Multi-Currency Architecture
The virtual economy manages three distinct virtual asset balances per tenant/player wallet:
1. **Money (`USD`)**: Real cash balance used for purchases and subscriptions (with automatic conversion to `UZS` using dynamic `CurrencyRate`).
2. **Diamonds (`💎`)**: Premium virtual currency used for VIP memberships, exclusive cosmetic packages, and gifts.
3. **Coins (`🪙`)**: Gameplay currency awarded automatically upon winning games, achieving win streaks, and completing achievements.

## 2. Concurrency Safety & Anti-Fraud
- **Atomic Operations**: All debit, credit, and transfer operations execute inside `transaction.atomic()` with `Wallet.objects.select_for_update().get(...)` row locks, preventing race conditions or double-spending.
- **Self-Transfer Prevention**: Transfers to self are strictly rejected at the service layer.
- **Non-Negative Invariant**: Balances can never drop below zero; `InsufficientBalanceError` is raised on insufficient funds.
- **Daily Cap Anti-Fraud Protection**: Daily transfer caps protect against unauthorized bulk transfers.

## 3. Telegram Bot Economy Commands
- `/profile` — Rich Telegram card displaying player level, XP, balances (USD, UZS, 💎, 🪙), VIP badge, and gameplay statistics with InlineKeyboard buttons.
- `/money <amount>` — Transfers virtual USD to another player by reply or `@username`.
- `/diamond <amount>` — Transfers diamonds to another player.
- `/shop` or `/market` — Displays interactive diamond purchasing options and VIP upgrade packages.
- `/leaderboard` — Displays real-time ranking by victories, streaks, and diamond wealth.
