export interface User {
  id: string;
  username: string;
  email: string;
  telegram_id?: number | null;
  role?: string;
  is_superadmin?: boolean;
  is_platform_owner?: boolean;
  group_name?: string;
  effective_group_name?: string;
  is_active: boolean;
  created_at: string;
}

export interface AuthTokens {
  access: string;
  refresh: string;
}

export interface AuthResponse {
  user: User;
  tokens: AuthTokens;
}

export type BotStatus = 'PENDING' | 'ACTIVE' | 'PAUSED' | 'SUSPENDED' | 'ERROR' | 'DELETED';
export type RuntimeStatus = 'OFFLINE' | 'STARTING' | 'RUNNING' | 'STOPPING' | 'ERROR';

export type GamePhase = 'WAITING' | 'STARTING' | 'NIGHT' | 'DAY' | 'DISCUSSION' | 'VOTING' | 'ELIMINATION' | 'FINISHED' | 'CANCELED';

export interface Player {
  id: string;
  telegram_user_id: number;
  username: string;
  display_name: string;
  role_name?: string | null;
  role_team?: string | null;
  is_alive: boolean;
  is_ready: boolean;
  eliminated_at?: string | null;
  eliminated_reason?: string;
  created_at: string;
}

export interface Game {
  id: string;
  bot: string;
  bot_name: string;
  chat_id: number;
  status: GamePhase;
  phase: GamePhase;
  round_number: number;
  winner_team?: string | null;
  players_count: number;
  alive_players_count: number;
  started_at?: string | null;
  finished_at?: string | null;
  created_at: string;
  players?: Player[];
}

export interface BotConfiguration {
  id: string;
  language: string;
  night_duration_seconds: number;
  day_duration_seconds: number;
  voting_duration_seconds: number;
  allow_custom_roles: boolean;
  show_roles_on_death: boolean;
  extra_settings: Record<string, any>;
}

export interface Bot {
  id: string;
  name: string;
  telegram_username: string;
  telegram_bot_id?: number | null;
  status: BotStatus;
  runtime_status: RuntimeStatus;
  description: string;
  configuration?: BotConfiguration;
  masked_token: string;
  created_at: string;
  updated_at: string;
}

export interface OverviewAnalytics {
  total_bots: number;
  active_bots: number;
  total_games: number;
  subscription_status: string;
}

// ---------------------------------------------------------------------------
// Phase 3 Types
// ---------------------------------------------------------------------------

export type TemplateType = 'SYSTEM' | 'USER';
export type TemplateVisibility = 'PRIVATE' | 'PUBLIC';
export type GameMode = 'CLASSIC' | 'QUICK' | 'CUSTOM' | 'TOURNAMENT';

export interface GameTemplate {
  id: string;
  name: string;
  slug: string;
  description: string;
  template_type: TemplateType;
  visibility: TemplateVisibility;
  game_mode: GameMode;
  status: string;
  version: number;
  owner_email: string;
  is_owned_by_me: boolean;
  configuration_data: Record<string, any>;
  role_distribution_data: RoleDistributionRule[];
  source_template_name?: string | null;
  created_at: string;
  updated_at: string;
}

export interface RoleAbility {
  id?: string;
  ability_type: 'KILL' | 'PROTECT' | 'INVESTIGATE' | 'NONE';
  phase: 'NIGHT' | 'DAY' | 'ANY';
  target_required: boolean;
  uses_per_game: number;
  cooldown_rounds: number;
  allowed_targets: string;
}

export interface Role {
  id: string;
  name: string;
  code: string;
  team: string;
  description: string;
  is_system: boolean;
  is_active: boolean;
  priority: number;
  is_mine: boolean;
  abilities?: RoleAbility[];
  created_at?: string;
  updated_at?: string;
}

export interface RoleDistributionRule {
  id?: string;
  role: string;
  role_name?: string;
  role_code?: string;
  role_team?: string;
  distribution_type: 'EXACT' | 'RANGE' | 'PERCENTAGE';
  min_count: number;
  max_count: number;
  percentage: number;
  priority: number;
}

export interface GameConfiguration {
  id: string;
  name: string;
  game_mode: GameMode;
  bot?: string | null;
  minimum_players: number;
  maximum_players: number;
  night_duration: number;
  discussion_duration: number;
  voting_duration: number;
  allow_self_vote: boolean;
  allow_self_protection: boolean;
  reveal_role_on_elimination: boolean;
  tie_behavior: string;
  mafia_vote_mode: string;
  allow_player_rejoin: boolean;
  automatic_phase_transition: boolean;
  day_discussion_enabled: boolean;
  distribution_rules: RoleDistributionRule[];
  created_at: string;
  updated_at: string;
}

export type TournamentStatus = 'DRAFT' | 'REGISTRATION' | 'ACTIVE' | 'PAUSED' | 'FINISHED' | 'CANCELLED';

export interface TournamentParticipant {
  id: string;
  telegram_user_id: number;
  display_name: string;
  username: string;
  score: number;
  games_played: number;
  games_won: number;
  games_lost: number;
  kills: number;
  survival_count: number;
  status: string;
  joined_at: string;
}

export interface TournamentRound {
  id: string;
  number: number;
  status: string;
  started_at?: string | null;
  finished_at?: string | null;
  games_count: number;
}

export interface Tournament {
  id: string;
  name: string;
  description: string;
  status: TournamentStatus;
  max_players: number;
  players_per_game: number;
  total_rounds: number;
  current_round: number;
  owner_email: string;
  participant_count: number;
  game_template?: string | null;
  configuration_data: Record<string, any>;
  scoring_config: Record<string, number>;
  started_at?: string | null;
  finished_at?: string | null;
  created_at: string;
  updated_at: string;
  rounds?: TournamentRound[];
}

export interface LeaderboardEntry {
  rank: number;
  telegram_user_id: number;
  display_name: string;
  score: number;
  games_played: number;
  games_won: number;
  kills: number;
  survival_count: number;
}

// ---------------------------------------------------------------------------
// Phase 4 Billing Types
// ---------------------------------------------------------------------------

export interface PlanFeature {
  id?: string;
  feature_code: string;
  limit_value: number;
  enabled: boolean;
}

export interface Plan {
  id: string;
  name: string;
  code: string;
  description: string;
  price: string;
  currency: string;
  billing_interval: 'MONTHLY' | 'YEARLY';
  is_active: boolean;
  display_order: number;
  features?: PlanFeature[];
}

export interface Subscription {
  id: string;
  plan?: Plan | null;
  plan_tier: string;
  status: 'TRIALING' | 'ACTIVE' | 'PAST_DUE' | 'CANCELED' | 'EXPIRED' | 'PAUSED';
  provider: 'MANUAL' | 'STRIPE' | 'PAYME' | 'CLICK';
  provider_subscription_id?: string;
  current_period_start?: string | null;
  current_period_end?: string | null;
  cancel_at_period_end: boolean;
  canceled_at?: string | null;
  trial_start?: string | null;
  trial_end?: string | null;
  is_valid: boolean;
  created_at: string;
}

export interface Payment {
  id: string;
  amount: string;
  currency: string;
  status: 'PENDING' | 'PROCESSING' | 'SUCCEEDED' | 'COMPLETED' | 'FAILED' | 'CANCELED' | 'REFUNDED';
  provider: string;
  provider_payment_id?: string;
  transaction_id?: string;
  paid_at?: string | null;
  failure_reason?: string;
  created_at: string;
}

export interface Invoice {
  id: string;
  invoice_number: string;
  amount: string;
  currency: string;
  status: 'DRAFT' | 'OPEN' | 'PAID' | 'UNCOLLECTIBLE' | 'VOID';
  issued_at: string;
  paid_at?: string | null;
}

export interface ResourceUsageLimit {
  current?: number;
  limit: number;
}

export interface UsageSummary {
  plan_name: string;
  plan_code: string;
  billing_interval: string;
  usage: {
    bots: ResourceUsageLimit;
    active_games: ResourceUsageLimit;
    max_players_per_game: ResourceUsageLimit;
    tournaments: ResourceUsageLimit;
    templates: ResourceUsageLimit;
    custom_roles_enabled: boolean;
    tournament_mode_enabled: boolean;
  };
}

