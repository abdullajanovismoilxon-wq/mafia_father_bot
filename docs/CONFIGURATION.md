# Advanced Game Configuration

The **MAFIA BOT FATHER** platform provides a fully data-driven configuration engine. Game rules are data, not hardcoded Python logic.

## GameConfiguration Model

A `GameConfiguration` encapsulates all configurable parameters for a Mafia game session:

- **Player Limits**: `minimum_players` (default 4), `maximum_players` (default 20).
- **Phase Durations**: `night_duration`, `discussion_duration`, `voting_duration` (seconds).
- **Tie Behavior**: `NO_ELIMINATION` (default) or `RANDOM` elimination when voting ends in a tie.
- **Mafia Vote Mode**: `ANY` (any single Mafia action counts) or `MAJORITY` (majority agreement required).
- **Rule Toggles**:
  - `allow_self_vote`: Allow players to vote for themselves during Day voting.
  - `allow_self_protection`: Allow Doctor to protect themselves at night.
  - `reveal_role_on_elimination`: Reveal player role upon elimination.
  - `automatic_phase_transition`: Auto-advance phase when timers expire.
  - `day_discussion_enabled`: Enable discussion phase before voting.

## RoleDistributionRules

Each `GameConfiguration` can contain one or more `RoleDistributionRule` instances defining how roles are allocated:

- **EXACT**: Fixed count of a specific role.
- **RANGE**: Range of min and max count.
- **PERCENTAGE**: Percentage of total player count.

## Configuration Snapshot Pattern

When a game starts (`GameService.start_game`), the active `GameConfiguration` is frozen into an immutable `ConfigurationSnapshot` attached to the `Game` instance. Subsequent changes to templates or configurations **never** corrupt active games.
