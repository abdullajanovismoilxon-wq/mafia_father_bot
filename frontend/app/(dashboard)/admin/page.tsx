'use client';

import React, { useEffect, useState } from 'react';
import { adminService, AdminOverview } from '@/services/admin.service';
import {
  Users, Bot, Gamepad2, DollarSign, Gem, ShieldCheck,
  AlertTriangle, RefreshCw
} from 'lucide-react';

const safeNum = (val: number | string | undefined | null) => {
  if (val === null || val === undefined) return '0';
  const num = typeof val === 'number' ? val : Number(val);
  return isNaN(num) ? '0' : num.toLocaleString();
};

export default function AdminOverviewPage() {
  const [overview, setOverview] = useState<AdminOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const fetchOverview = async () => {
    try {
      setLoading(true);
      setError('');
      const data = await adminService.getOverview();
      setOverview(data);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to load admin overview. Check administrator permissions.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchOverview();
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[300px]">
        <RefreshCw className="w-6 h-6 animate-spin text-rose-500" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-4 bg-rose-500/10 border border-rose-500/20 rounded-xl text-rose-400 flex items-center gap-3">
        <AlertTriangle className="w-5 h-5 flex-shrink-0" />
        <p className="text-sm">{error}</p>
      </div>
    );
  }

  if (!overview) return null;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-white">System Metrics & Vital Health</h2>
        <button
          onClick={fetchOverview}
          className="flex items-center gap-2 px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-medium rounded-lg transition"
        >
          <RefreshCw className="w-3.5 h-3.5" />
          Refresh
        </button>
      </div>

      {/* Top Stat Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Total Revenue */}
        <div className="p-5 bg-slate-900 border border-slate-800 rounded-2xl">
          <div className="flex items-center justify-between text-slate-400 mb-3">
            <span className="text-xs font-medium uppercase tracking-wider">Total Revenue</span>
            <div className="p-2 bg-emerald-500/10 rounded-xl text-emerald-400">
              <DollarSign className="w-4 h-4" />
            </div>
          </div>
          <div className="text-2xl font-bold text-white">${safeNum(overview?.revenue?.total_usd)}</div>
          <div className="text-xs text-slate-500 mt-1">
            Today: <span className="text-emerald-400 font-medium">${safeNum(overview?.revenue?.today_usd)}</span> | Month: ${safeNum(overview?.revenue?.monthly_usd)}
          </div>
        </div>

        {/* Active Bots */}
        <div className="p-5 bg-slate-900 border border-slate-800 rounded-2xl">
          <div className="flex items-center justify-between text-slate-400 mb-3">
            <span className="text-xs font-medium uppercase tracking-wider">Bot Runtimes</span>
            <div className="p-2 bg-blue-500/10 rounded-xl text-blue-400">
              <Bot className="w-4 h-4" />
            </div>
          </div>
          <div className="text-2xl font-bold text-white">
            {overview?.bots?.running ?? 0} <span className="text-sm font-normal text-slate-500">/ {overview?.bots?.total ?? 0}</span>
          </div>
          <div className="text-xs text-slate-500 mt-1">
            Running: <span className="text-blue-400 font-medium">{overview?.bots?.running ?? 0}</span> | Offline: {overview?.bots?.offline ?? 0} | Suspended: {overview?.bots?.suspended ?? 0}
          </div>
        </div>

        {/* Active Games */}
        <div className="p-5 bg-slate-900 border border-slate-800 rounded-2xl">
          <div className="flex items-center justify-between text-slate-400 mb-3">
            <span className="text-xs font-medium uppercase tracking-wider">Active Games</span>
            <div className="p-2 bg-purple-500/10 rounded-xl text-purple-400">
              <Gamepad2 className="w-4 h-4" />
            </div>
          </div>
          <div className="text-2xl font-bold text-white">{overview?.games?.active ?? 0}</div>
          <div className="text-xs text-slate-500 mt-1">
            Total Finished: <span className="text-purple-400 font-medium">{overview?.games?.finished ?? 0}</span> | Played Today: {overview?.games?.today ?? 0}
          </div>
        </div>

        {/* Registered Users & Players */}
        <div className="p-5 bg-slate-900 border border-slate-800 rounded-2xl">
          <div className="flex items-center justify-between text-slate-400 mb-3">
            <span className="text-xs font-medium uppercase tracking-wider">Platform Users</span>
            <div className="p-2 bg-amber-500/10 rounded-xl text-amber-400">
              <Users className="w-4 h-4" />
            </div>
          </div>
          <div className="text-2xl font-bold text-white">{overview?.users?.total ?? 0}</div>
          <div className="text-xs text-slate-500 mt-1">
            Active: <span className="text-amber-400 font-medium">{overview?.users?.active ?? 0}</span> | Suspended: {overview?.users?.suspended ?? 0}
          </div>
        </div>
      </div>

      {/* Economy & Virtual Assets Distribution */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="p-6 bg-slate-900 border border-slate-800 rounded-2xl space-y-4">
          <div className="flex items-center gap-2 text-white font-semibold">
            <Gem className="w-5 h-5 text-sky-400" />
            <h3>Virtual Economy in Circulation</h3>
          </div>
          <div className="grid grid-cols-3 gap-4 pt-2">
            <div className="p-4 bg-slate-950/60 rounded-xl border border-slate-800">
              <div className="text-xs text-slate-400 mb-1">Money Circulation</div>
              <div className="text-xl font-bold text-emerald-400">${safeNum(overview?.economy?.money_in_circulation)}</div>
            </div>
            <div className="p-4 bg-slate-950/60 rounded-xl border border-slate-800">
              <div className="text-xs text-slate-400 mb-1">Diamonds Circulation</div>
              <div className="text-xl font-bold text-sky-400">{safeNum(overview?.economy?.diamonds_in_circulation)} 💎</div>
            </div>
            <div className="p-4 bg-slate-950/60 rounded-xl border border-slate-800">
              <div className="text-xs text-slate-400 mb-1">Coins Circulation</div>
              <div className="text-xl font-bold text-amber-400">{safeNum(overview?.economy?.coins_in_circulation)} 🪙</div>
            </div>
          </div>
        </div>

        <div className="p-6 bg-slate-900 border border-slate-800 rounded-2xl space-y-4">
          <div className="flex items-center gap-2 text-white font-semibold">
            <ShieldCheck className="w-5 h-5 text-emerald-400" />
            <h3>Subscriptions & VIP Entitlements</h3>
          </div>
          <div className="grid grid-cols-2 gap-4 pt-2">
            <div className="p-4 bg-slate-950/60 rounded-xl border border-slate-800">
              <div className="text-xs text-slate-400 mb-1">Paid SaaS Subscriptions</div>
              <div className="text-xl font-bold text-purple-400">{overview?.subscriptions?.active_paid_subscriptions ?? 0}</div>
            </div>
            <div className="p-4 bg-slate-950/60 rounded-xl border border-slate-800">
              <div className="text-xs text-slate-400 mb-1">Active VIP Players</div>
              <div className="text-xl font-bold text-amber-400">{overview?.subscriptions?.vip_users ?? 0}</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
