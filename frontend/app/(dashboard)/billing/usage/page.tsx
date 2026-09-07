'use client';

import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import { ArrowLeft, BarChart3, CheckCircle2, XCircle, Loader2 } from 'lucide-react';
import { UsageSummary } from '@/types';
import { billingService } from '@/services/billing.service';

export default function DetailedUsagePage() {
  const [usage, setUsage] = useState<UsageSummary | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const load = async () => {
      try {
        const data = await billingService.usage();
        setUsage(data);
      } finally {
        setLoading(false);
      }
    };
    load();
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20 text-slate-400 text-sm gap-2">
        <Loader2 className="w-5 h-5 animate-spin" /> Loading usage metrics...
      </div>
    );
  }

  if (!usage) {
    return <div className="text-slate-500 text-sm py-12 text-center">Failed to load usage data.</div>;
  }

  const u = usage.usage;

  return (
    <div className="space-y-6 max-w-3xl">
      <Link href="/billing" className="flex items-center gap-1 text-slate-400 hover:text-white text-sm transition">
        <ArrowLeft className="w-4 h-4" /> Back to Billing Overview
      </Link>

      <div className="flex items-center gap-3">
        <BarChart3 className="w-6 h-6 text-emerald-400" />
        <div>
          <h1 className="text-xl font-bold text-white">Resource Usage Breakdown</h1>
          <p className="text-slate-400 text-sm">Detailed limit allocation and current resource counters</p>
        </div>
      </div>

      <div className="bg-slate-800/50 border border-slate-700 rounded-2xl p-6 space-y-6">
        <div className="flex justify-between items-center border-b border-slate-700 pb-4">
          <span className="text-sm text-slate-400">Active Plan</span>
          <span className="text-lg font-bold text-white">{usage.plan_name}</span>
        </div>

        <div className="space-y-4">
          {[
            ['Active Bots', u.bots.current, u.bots.limit],
            ['Active Concurrent Games', u.active_games.current, u.active_games.limit],
            ['Max Players Per Game', '—', u.max_players_per_game.limit],
            ['Active Tournaments', u.tournaments.current, u.tournaments.limit],
            ['Saved Templates', u.templates.current, u.templates.limit],
          ].map(([label, curr, limit]) => (
            <div key={label as string} className="flex justify-between items-center bg-slate-900/60 p-3.5 rounded-xl text-sm">
              <span className="text-slate-300 font-medium">{label}</span>
              <div className="text-right">
                <span className="text-white font-bold">{curr !== '—' ? `${curr} / ` : ''}</span>
                <span className="text-emerald-400 font-bold">{limit === -1 ? 'Unlimited' : limit}</span>
              </div>
            </div>
          ))}
        </div>

        <div className="pt-2 border-t border-slate-700 space-y-3">
          <h3 className="text-xs text-slate-400 uppercase tracking-wider font-semibold">Feature Gates</h3>
          <div className="grid grid-cols-2 gap-3 text-sm">
            <div className="flex items-center justify-between bg-slate-900/40 p-3 rounded-xl">
              <span className="text-slate-300">Custom Role Builder</span>
              {u.custom_roles_enabled ? <CheckCircle2 className="w-4 h-4 text-emerald-400" /> : <XCircle className="w-4 h-4 text-slate-600" />}
            </div>
            <div className="flex items-center justify-between bg-slate-900/40 p-3 rounded-xl">
              <span className="text-slate-300">Tournament Mode</span>
              {u.tournament_mode_enabled ? <CheckCircle2 className="w-4 h-4 text-emerald-400" /> : <XCircle className="w-4 h-4 text-slate-600" />}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
