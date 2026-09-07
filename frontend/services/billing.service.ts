import axios from 'axios';
import { Plan, Subscription, Payment, Invoice, UsageSummary } from '../types';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

const api = axios.create({ baseURL: API_BASE });

api.interceptors.request.use((config) => {
  if (typeof window !== 'undefined') {
    const token = localStorage.getItem('access_token');
    if (token) config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

export const billingService = {
  plans: async () => {
    const res = await api.get<{ results: Plan[] }>('/billing/plans/');
    return res.data.results ?? (res.data as any);
  },

  subscription: async () => {
    const res = await api.get<Subscription>('/billing/subscription/');
    return res.data;
  },

  checkout: async (data: { plan_code: string; provider: string; return_url?: string; cancel_url?: string }) => {
    const res = await api.post<{ checkout_url: string; session_id: string; provider: string }>('/billing/checkout/', data);
    return res.data;
  },

  cancel: async () => {
    const res = await api.post<Subscription>('/billing/cancel/');
    return res.data;
  },

  resume: async () => {
    const res = await api.post<Subscription>('/billing/resume/');
    return res.data;
  },

  payments: async () => {
    const res = await api.get<{ results: Payment[] }>('/billing/payments/');
    return res.data.results ?? (res.data as any);
  },

  invoices: async () => {
    const res = await api.get<{ results: Invoice[] }>('/billing/invoices/');
    return res.data.results ?? (res.data as any);
  },

  usage: async () => {
    const res = await api.get<UsageSummary>('/billing/usage/');
    return res.data;
  },

  entitlements: async () => {
    const res = await api.get<Plan>('/billing/entitlements/');
    return res.data;
  },
};
