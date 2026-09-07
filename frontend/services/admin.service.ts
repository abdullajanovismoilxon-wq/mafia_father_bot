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

export interface AdminOverview {
  users: { total: number; active: number; suspended: number };
  bots: { total: number; running: number; offline: number; error: number; suspended: number };
  games: { total: number; active: number; finished: number; today: number };
  players: { total: number; online: number };
  revenue: { total_usd: number; today_usd: number; monthly_usd: number };
  economy: { money_in_circulation: number; diamonds_in_circulation: number; coins_in_circulation: number };
  subscriptions: { active_paid_subscriptions: number; vip_users: number };
  system_health: string;
  timestamp: string;
}

export interface AdminBot {
  id: string;
  name: string;
  username: string;
  owner_email: string;
  status: string;
  runtime_status: string;
  active_games: number;
  created_at: string;
  updated_at: string;
}

export interface AdminGame {
  id: string;
  bot_username: string;
  owner_email: string;
  chat_id: number;
  chat_title: string;
  phase: string;
  round_number: number;
  status: string;
  players_count: number;
  alive_count: number;
  created_at: string;
}

export interface AdminUser {
  id: string;
  username: string;
  email: string;
  role: string;
  is_suspended: boolean;
  is_active: boolean;
  wallet: {
    money: number;
    diamonds: number;
    coins: number;
  };
  vip: {
    is_vip: boolean;
    level: string | null;
    expires_at: string | null;
  };
  subscription_plan: string;
  bots_count: number;
  created_at: string;
}

export interface AdminPaymentOrder {
  id: string;
  order_id: string;
  user_email: string;
  telegram_id: number | null;
  diamonds: number;
  amount_usd: number;
  status: string;
  proof_file: string | null;
  admin_notes: string;
  reviewed_by: string | null;
  created_at: string;
  reviewed_at: string | null;
}

export interface AdminAuditLog {
  id: string;
  admin_email: string;
  action: string;
  target_type: string;
  target_id: string;
  ip_address: string | null;
  metadata: Record<string, any>;
  result: string;
  created_at: string;
}

export const adminService = {
  getOverview: async () => {
    const res = await api.get<AdminOverview>('/admin/overview/');
    return res.data;
  },

  getBots: async (statusFilter?: string) => {
    const params = statusFilter ? { status: statusFilter } : {};
    const res = await api.get<AdminBot[]>('/admin/bots/', { params });
    return res.data;
  },

  suspendBot: async (botId: string) => {
    const res = await api.post(`/admin/bots/${botId}/suspend/`);
    return res.data;
  },

  resumeBot: async (botId: string) => {
    const res = await api.post(`/admin/bots/${botId}/resume/`);
    return res.data;
  },

  restartBot: async (botId: string) => {
    const res = await api.post(`/admin/bots/${botId}/restart/`);
    return res.data;
  },

  stopBot: async (botId: string) => {
    const res = await api.post(`/admin/bots/${botId}/stop/`);
    return res.data;
  },

  getGames: async (statusFilter?: string) => {
    const params = statusFilter ? { status: statusFilter } : {};
    const res = await api.get<AdminGame[]>('/admin/games/', { params });
    return res.data;
  },

  getUsers: async (search?: string) => {
    const params = search ? { search } : {};
    const res = await api.get<AdminUser[]>('/admin/users/', { params });
    return res.data;
  },

  suspendUser: async (userId: string, reason?: string) => {
    const res = await api.post(`/admin/users/${userId}/suspend/`, { reason });
    return res.data;
  },

  activateUser: async (userId: string) => {
    const res = await api.post(`/admin/users/${userId}/activate/`);
    return res.data;
  },

  grantVip: async (userId: string, vipLevel: string, days: number = 30) => {
    const res = await api.post(`/admin/users/${userId}/grant_vip/`, {
      vip_level: vipLevel,
      days,
    });
    return res.data;
  },

  adjustBalance: async (userId: string, currency: string, amount: number, reason: string) => {
    const res = await api.post(`/admin/users/${userId}/adjust_balance/`, {
      currency,
      amount,
      reason,
    });
    return res.data;
  },

  getPaymentOrders: async (statusFilter?: string) => {
    const params = statusFilter ? { status: statusFilter } : {};
    const res = await api.get<AdminPaymentOrder[]>('/admin/payment-orders/', { params });
    return res.data;
  },

  reviewPaymentOrder: async (orderId: string, approve: boolean, notes?: string) => {
    const res = await api.post(`/admin/payment-orders/${orderId}/review/`, {
      approve,
      admin_notes: notes,
    });
    return res.data;
  },

  getAuditLogs: async (action?: string) => {
    const params = action ? { action } : {};
    const res = await api.get<AdminAuditLog[]>('/admin/audit-logs/', { params });
    return res.data;
  },
};
