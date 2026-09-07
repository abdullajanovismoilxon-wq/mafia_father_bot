import { apiClient } from '../lib/api-client';
import { Game } from '../types';

export const gamesService = {
  async getGames(): Promise<Game[]> {
    const response = await apiClient.get('/games/');
    return response.data.results || response.data;
  },

  async getGameDetail(id: string): Promise<Game> {
    const response = await apiClient.get(`/games/${id}/`);
    return response.data;
  },

  async startGame(id: string): Promise<void> {
    await apiClient.post(`/games/${id}/start/`);
  },

  async cancelGame(id: string): Promise<void> {
    await apiClient.post(`/games/${id}/cancel/`);
  },
};
