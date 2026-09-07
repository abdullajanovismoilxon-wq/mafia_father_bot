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

export interface WalletData {
  money: string;
  money_uzs: number;
  diamonds: number;
  coins: number;
  usd_to_uzs_rate: number;
}

export interface WalletTransactionItem {
  id: string;
  currency: string;
  amount: string;
  transaction_type: string;
  balance_after: string;
  description: string;
  created_at: string;
}

export interface MarketplaceItemData {
  id: string;
  code: string;
  name: string;
  item_type: string;
  diamond_amount: number;
  coin_amount: number;
  price_usd: string;
  price_uzs: number;
  price_diamonds: number;
  price_coins: number;
  badge_icon: string;
  is_popular: boolean;
}

export interface MarketplaceCatalog {
  categories: Array<{ id: string; name: string; slug: string; icon: string }>;
  items: MarketplaceItemData[];
  usd_to_uzs_rate: number;
}

export const economyService = {
  getWallet: async () => {
    const res = await api.get<WalletData>('/economy/wallet/');
    return res.data;
  },

  getTransactions: async () => {
    const res = await api.get<WalletTransactionItem[]>('/economy/transactions/');
    return res.data;
  },

  transfer: async (data: {
    currency: 'MONEY' | 'DIAMONDS' | 'COINS';
    amount: number;
    recipient_email?: string;
    recipient_telegram_id?: number;
    description?: string;
  }) => {
    const res = await api.post('/economy/transfer/', data);
    return res.data;
  },

  getCatalog: async () => {
    const res = await api.get<MarketplaceCatalog>('/economy/marketplace/');
    return res.data;
  },

  purchaseItem: async (itemCode: string, currency: string) => {
    const res = await api.post('/economy/purchase/', {
      item_code: itemCode,
      currency,
    });
    return res.data;
  },

  createPaymentOrder: async (diamonds: number) => {
    const res = await api.post('/economy/orders/', { diamonds });
    return res.data;
  },
};
