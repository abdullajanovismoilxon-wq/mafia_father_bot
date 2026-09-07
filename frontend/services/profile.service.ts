import axios from 'axios';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

const api = axios.create({ baseURL: API_BASE });

api.interceptors.request.use((config) => {
  if (typeof window !== 'undefined') {
    const token = localStorage.getItem('access_token');
    if (token) config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

export interface PlayerStatsData {
  games_played: number;
  games_won: number;
  games_lost: number;
  win_rate: number;
  current_win_streak: number;
  best_win_streak: number;
  mafia_wins: number;
  civilian_wins: number;
  doctor_saves: number;
  detective_investigations: number;
  survival_count: number;
  mvp_count: number;
}

export interface AchievementItem {
  id: string;
  code: string;
  title: string;
  description: string;
  category: string;
  diamond_reward: number;
  coin_reward: number;
  badge_icon: string;
  is_unlocked: boolean;
  unlocked_at: string | null;
}

export interface ProfileData {
  profile: {
    id: string;
    telegram_id: number | null;
    username: string;
    full_name: string;
    level: number;
    experience_points: number;
    vip_badge: string | null;
    vip_expires_at: string | null;
    is_vip: boolean;
    created_at: string;
  };
  stats: PlayerStatsData;
  wallet: {
    money: string;
    money_uzs: number;
    diamonds: number;
    coins: number;
    usd_to_uzs_rate: number;
  };
  achievements: AchievementItem[];
  inventory: Array<{
    id: string;
    item_name: string;
    item_code: string;
    item_type: string;
    quantity: number;
    is_equipped: boolean;
  }>;
}

export interface LeaderboardEntry {
  rank: number;
  id: string;
  name: string;
  telegram_username: string;
  games_won: number;
  games_played: number;
  win_rate: number;
  win_streak: number;
  diamonds: number;
}

export const profileService = {
  getProfile: async () => {
    const res = await api.get<ProfileData>('/stats/profile/');
    return res.data;
  },

  getLeaderboard: async (category: string = 'wins', limit: number = 20) => {
    const res = await api.get<LeaderboardEntry[]>('/stats/leaderboard/', {
      params: { category, limit },
    });
    return res.data;
  },
};
