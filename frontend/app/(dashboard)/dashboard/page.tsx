'use client';

import React, { useEffect, useState } from 'react';
import { Bot, Gamepad2, Layers, ShieldCheck } from 'lucide-react';
import { botsService } from '../../../services/bots.service';
import { OverviewAnalytics } from '../../../types';

export default function DashboardPage() {
  const [stats, setStats] = useState<OverviewAnalytics>({
    total_bots: 0,
    active_bots: 0,
    total_games: 0,
    subscription_status: 'FREE',
  });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    botsService
      .getOverviewAnalytics()
      .then((data) => setStats(data))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-3xl font-bold text-white mb-1">Platform Dashboard</h1>
        <p className="text-slate-400 text-sm">
          Overview of your Telegram Mafia bot fleet and system status
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
        <div className="bg-slate-900 border border-slate-800 p-6 rounded-xl flex items-center gap-4">
          <div className="p-3 bg-emerald-500/10 border border-emerald-500/20 rounded-lg text-emerald-400">
            <Bot className="w-6 h-6" />
          </div>
          <div>
            <p className="text-xs font-medium text-slate-400 uppercase tracking-wider">Total Bots</p>
            <p className="text-2xl font-bold text-white mt-1">{loading ? '...' : stats.total_bots}</p>
          </div>
        </div>

        <div className="bg-slate-900 border border-slate-800 p-6 rounded-xl flex items-center gap-4">
          <div className="p-3 bg-emerald-500/10 border border-emerald-500/20 rounded-lg text-emerald-400">
            <ShieldCheck className="w-6 h-6" />
          </div>
          <div>
            <p className="text-xs font-medium text-slate-400 uppercase tracking-wider">Active Bots</p>
            <p className="text-2xl font-bold text-emerald-400 mt-1">{loading ? '...' : stats.active_bots}</p>
          </div>
        </div>

        <div className="bg-slate-900 border border-slate-800 p-6 rounded-xl flex items-center gap-4">
          <div className="p-3 bg-blue-500/10 border border-blue-500/20 rounded-lg text-blue-400">
            <Gamepad2 className="w-6 h-6" />
          </div>
          <div>
            <p className="text-xs font-medium text-slate-400 uppercase tracking-wider">Total Games</p>
            <p className="text-2xl font-bold text-white mt-1">{loading ? '...' : stats.total_games}</p>
          </div>
        </div>

        <div className="bg-slate-900 border border-slate-800 p-6 rounded-xl flex items-center gap-4">
          <div className="p-3 bg-purple-500/10 border border-purple-500/20 rounded-lg text-purple-400">
            <Layers className="w-6 h-6" />
          </div>
          <div>
            <p className="text-xs font-medium text-slate-400 uppercase tracking-wider">Subscription</p>
            <p className="text-2xl font-bold text-purple-300 mt-1">{stats.subscription_status}</p>
          </div>
        </div>
      </div>

      <div className="bg-slate-900 border border-slate-800 rounded-xl p-6">
        <h2 className="text-lg font-semibold text-white mb-2">Architectural Status — Phase 1 Foundation</h2>
        <p className="text-sm text-slate-400 leading-relaxed">
          The Control Plane API and Multi-tenant Bot Registry are running smoothly. All Telegram Bot tokens are symmetrically encrypted via Fernet algorithm before persistence.
        </p>
      </div>
    </div>
  );
}
