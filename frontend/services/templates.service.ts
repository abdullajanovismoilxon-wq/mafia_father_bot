import axios from 'axios';
import { GameTemplate } from '../types';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

const api = axios.create({ baseURL: API_BASE });

api.interceptors.request.use((config) => {
  if (typeof window !== 'undefined') {
    const token = localStorage.getItem('access_token');
    if (token) config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

export const templatesService = {
  list: async (type: 'all' | 'mine' | 'system' | 'public' = 'all') => {
    const res = await api.get<{ results: GameTemplate[] }>('/templates/game-templates/', { params: { type } });
    return res.data.results ?? (res.data as any);
  },

  get: async (id: string) => {
    const res = await api.get<GameTemplate>(`/templates/game-templates/${id}/`);
    return res.data;
  },

  create: async (data: Partial<GameTemplate>) => {
    const res = await api.post<GameTemplate>('/templates/game-templates/', data);
    return res.data;
  },

  update: async (id: string, data: Partial<GameTemplate>) => {
    const res = await api.patch<GameTemplate>(`/templates/game-templates/${id}/`, data);
    return res.data;
  },

  delete: async (id: string) => {
    await api.delete(`/templates/game-templates/${id}/`);
  },

  duplicate: async (id: string) => {
    const res = await api.post<GameTemplate>(`/templates/game-templates/${id}/duplicate/`);
    return res.data;
  },

  use: async (id: string, botId?: string) => {
    const res = await api.post(`/templates/game-templates/${id}/use/`, botId ? { bot_id: botId } : {});
    return res.data;
  },
};
