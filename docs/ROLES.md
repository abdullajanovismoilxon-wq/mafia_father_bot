# Configurable Roles & Abilities

Phase 3 introduces custom, user-defined roles with declarative abilities. Users do **not** execute custom Python code — abilities are purely data-driven.

## System Roles vs Custom Roles

- **System Roles** (`is_system=True`, `owner=None`): Platform built-in roles (`citizen`, `mafia`, `doctor`, `detective`). Read-only for all users.
- **Custom Roles** (`is_system=False`, `owner=<User>`): Tenant-created roles. Users can create, modify, or deactivate their own roles.

## Role Model

- `name`: Display name (e.g., `Vigilante`, `Don`).
- `code`: Unique slug per owner (e.g., `vigilante`).
- `team`: Faction (`CIVILIAN`, `MAFIA`, `NEUTRAL`).
- `description`: Role narrative and instructions.
- `priority`: Processing order priority.

## RoleAbilities

Attached to a Role via `RoleAbility`:

- `ability_type`: `KILL`, `PROTECT`, `INVESTIGATE`, `NONE`.
- `phase`: `NIGHT`, `DAY`, `ANY`.
- `target_required`: `True` if action requires selecting a target player.
- `uses_per_game`: `0` for unlimited, `N` for limited uses.
- `allowed_targets`: `CIVILIAN`, `MAFIA`, `NEUTRAL`, `ANY`.

## REST API Endpoints

- `GET /api/v1/roles/` — List accessible roles (own + system).
- `POST /api/v1/roles/` — Create a custom role.
- `GET /api/v1/roles/{id}/` — Get role details + abilities.
- `PATCH /api/v1/roles/{id}/` — Update custom role.
- `DELETE /api/v1/roles/{id}/` — Soft-delete (deactivate) custom role.
