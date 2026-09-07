# Game & Bot Templates

Templates allow platform users to create, share, and duplicate reusable game configurations.

## GameTemplate Model

- `name`, `slug`, `description`: Metadata.
- `template_type`: `SYSTEM` (official built-in templates) or `USER` (tenant custom templates).
- `visibility`: `PRIVATE` (owner-only) or `PUBLIC` (browseable/copyable by all platform users).
- `game_mode`: `CLASSIC`, `QUICK`, `CUSTOM`, `TOURNAMENT`.
- `configuration_data`: Frozen JSON dictionary of `GameConfiguration` parameters.
- `role_distribution_data`: Frozen JSON list of `RoleDistributionRule` parameters.
- `source_template`: Self-FK pointing to the template this was duplicated from.
- `version`: Integer version number.

## Key Actions

- **List** (`GET /api/v1/templates/game-templates/?type=all|mine|system|public`): Filtered list.
- **Duplicate** (`POST /api/v1/templates/game-templates/{id}/duplicate/`): Creates a personal copy of any system or public template.
- **Use** (`POST /api/v1/templates/game-templates/{id}/use/`): Applies template to a Bot or retrieves configuration payload.
