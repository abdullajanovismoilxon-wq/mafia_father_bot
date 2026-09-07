import axios from 'axios';
import { Tournament, TournamentParticipant, TournamentRound, LeaderboardEntry } from '../types';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

const api = axios.create({ baseURL: API_BASE });

api.interceptors.request.use((config) => {
  if (typeof window !== 'undefined') {
    const token = localStorage.getItem('access_token');
    if (token) config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

export const tournamentsService = {
  list: async () => {
    const res = await api.get<{ results: Tournament[] }>('/tournaments/');
    return res.data.results ?? (res.data as any);
  },

  get: async (id: string) => {
    const res = await api.get<Tournament>(`/tournaments/${id}/`);
    return res.data;
  },

  create: async (data: Partial<Tournament>) => {
    const res = await api.post<Tournament>('/tournaments/', data);
    return res.data;
  },

  start: async (id: string) => {
    const res = await api.post<Tournament>(`/tournaments/${id}/start/`);
    return res.data;
  },

  cancel: async (id: string) => {
    const res = await api.post(`/tournaments/${id}/cancel/`);
    return res.data;
  },

  openRegistration: async (id: string) => {
    const res = await api.post<Tournament>(`/tournaments/${id}/open-registration/`);
    return res.data;
  },

  participants: async (id: string) => {
    const res = await api.get<TournamentParticipant[]>(`/tournaments/${id}/participants/`);
    return res.data;
  },

  leaderboard: async (id: string) => {
    const res = await api.get<LeaderboardEntry[]>(`/tournaments/${id}/leaderboard/`);
    return res.data;
  },

  rounds: async (id: string) => {
    const res = await api.get<TournamentRound[]>(`/tournaments/${id}/rounds/`);
    return res.data;
  },
};
