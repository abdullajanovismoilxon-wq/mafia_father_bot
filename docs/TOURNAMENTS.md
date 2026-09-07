# Tournament System

The Tournament System enables multi-round, multi-game competitive Mafia tournaments with deterministic scoring and live leaderboards.

## Architecture

- **`Tournament`**: Top-level competition entity (`owner`, `status`, `max_players`, `players_per_game`, `total_rounds`, `current_round`).
- **`TournamentRound`**: Individual round (`number`, `status`, `started_at`, `finished_at`).
- **`TournamentParticipant`**: Participant tracking cumulative statistics (`score`, `games_played`, `games_won`, `games_lost`, `kills`, `survival_count`).
- **`TournamentGame`**: Connects a round group to a `Game` engine instance.

## Tournament Lifecycle

```
DRAFT ──> REGISTRATION ──> ACTIVE ──> FINISHED
  │            │             │
  └────────────┴─────────────┴──> CANCELLED
```

1. **DRAFT**: Created by owner. Parameters configured.
2. **REGISTRATION**: Open for Telegram users to join (`/join_tournament` or UI).
3. **ACTIVE**: Round 1 generated. Participants grouped by `TournamentGroupingService`. Games spawned automatically.
4. **FINISHED**: All rounds completed. Final leaderboard generated.

## Deterministic Scoring

Scoring rules are configurable per tournament (`scoring_config`):

- Participation: +1
- Survival: +1
- Winning Faction: +3
- Mafia Elimination (kill): +1
- Final Survivor: +2

Calculated automatically by `TournamentScoringService` upon game completion.

## Telegram Bot Integration

- `/create_tournament <name>` — Create & open registration.
- `/tournament` — Show current status and inline join/rules buttons.
- `/leaderboard` — Display top 10 live leaderboard.
