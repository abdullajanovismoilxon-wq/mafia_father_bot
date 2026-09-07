# Centralized Entitlement & Limit Engine

The `EntitlementService` manages resource limits and feature gates across all platform engines.

## Feature Codes

| Feature Code | Type | Description |
|---|---|---|
| `MAX_BOTS` | Numeric | Maximum Telegram bot instances |
| `MAX_ACTIVE_GAMES` | Numeric | Maximum concurrent active games |
| `MAX_PLAYERS_PER_GAME` | Numeric | Maximum player lobby capacity |
| `MAX_TOURNAMENTS` | Numeric | Maximum active tournaments |
| `MAX_TEMPLATES` | Numeric | Maximum saved custom templates |
| `CUSTOM_ROLES` | Boolean | Access to Custom Role Builder |
| `TOURNAMENT_MODE` | Boolean | Access to Tournament System |
| `ADVANCED_ANALYTICS` | Boolean | Advanced statistics dashboard |

## Enforcement Points

1. **Bot Creation**: `BotViewSet.perform_create` → `can_create_bot(user)`
2. **Game Start**: `GameService.start_game` → `can_start_game(owner)`
3. **Tournament Creation**: `TournamentService.create_tournament` → `can_create_tournament(owner)`
4. **Custom Role Creation**: `RoleViewSet.perform_create` → `can_use_custom_roles(user)`
5. **Template Creation**: `GameTemplateViewSet.perform_create` → `can_create_template(user)`

## Error Response Format (403 / 402)

```json
{
  "code": "PLAN_LIMIT_REACHED",
  "feature": "MAX_BOTS",
  "limit": 1,
  "current_usage": 1,
  "detail": "Plan limit reached for 'MAX_BOTS'. Limit: 1, Current Usage: 1."
}
```
