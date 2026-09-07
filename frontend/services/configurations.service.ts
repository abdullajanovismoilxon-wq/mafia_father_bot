import axios from 'axios';
import { Role, GameConfiguration } from '../types';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

const api = axios.create({ baseURL: API_BASE });

api.interceptors.request.use((config) => {
  if (typeof window !== 'undefined') {
    const token = localStorage.getItem('access_token');
    if (token) config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

export const rolesService = {
  list: async () => {
    const res = await api.get<{ results: Role[] }>('/roles/');
    return res.data.results ?? (res.data as any);
  },

  get: async (id: string) => {
    const res = await api.get<Role>(`/roles/${id}/`);
    return res.data;
  },

  create: async (data: Partial<Role>) => {
    const res = await api.post<Role>('/roles/', data);
    return res.data;
  },

  update: async (id: string, data: Partial<Role>) => {
    const res = await api.patch<Role>(`/roles/${id}/`, data);
    return res.data;
  },

  delete: async (id: string) => {
    await api.delete(`/roles/${id}/`);
  },
};

export const configurationsService = {
  list: async () => {
    const res = await api.get<{ results: GameConfiguration[] }>('/configurations/');
    return res.data.results ?? (res.data as any);
  },

  get: async (id: string) => {
    const res = await api.get<GameConfiguration>(`/configurations/${id}/`);
    return res.data;
  },

  create: async (data: Partial<GameConfiguration>) => {
    const res = await api.post<GameConfiguration>('/configurations/', data);
    return res.data;
  },

  update: async (id: string, data: Partial<GameConfiguration>) => {
    const res = await api.patch<GameConfiguration>(`/configurations/${id}/`, data);
    return res.data;
  },
};
