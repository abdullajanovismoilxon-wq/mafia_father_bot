import { apiClient } from '../lib/api-client';
import { Bot, OverviewAnalytics } from '../types';

export const botsService = {
  async getBots(): Promise<Bot[]> {
    const response = await apiClient.get('/bots/');
    return response.data.results || response.data;
  },

  async createBot(data: { name: string; telegram_username: string; bot_token: string; description?: string }): Promise<Bot> {
    const response = await apiClient.post('/bots/', data);
    return response.data;
  },

  async startBot(id: string): Promise<void> {
    await apiClient.post(`/bots/${id}/start_bot/`);
  },

  async stopBot(id: string): Promise<void> {
    await apiClient.post(`/bots/${id}/stop_bot/`);
  },

  async getOverviewAnalytics(): Promise<OverviewAnalytics> {
    const response = await apiClient.get('/analytics/overview/');
    return response.data;
  },
};
