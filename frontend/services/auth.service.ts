import { apiClient } from '../lib/api-client';
import { AuthResponse, User } from '../types';

export const authService = {
  async register(data: Record<string, string>): Promise<AuthResponse> {
    const response = await apiClient.post('/auth/register/', data);
    return response.data;
  },

  async login(data: Record<string, string>): Promise<{ access: string; refresh: string }> {
    const response = await apiClient.post('/auth/login/', data);
    return response.data;
  },

  async getMe(): Promise<User> {
    const response = await apiClient.get('/auth/me/');
    return response.data;
  },

  async logout(refreshToken: string): Promise<void> {
    await apiClient.post('/auth/logout/', { refresh: refreshToken });
  },
};
