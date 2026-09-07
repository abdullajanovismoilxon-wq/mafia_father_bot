'use client';

import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import { CreditCard, Shield, Zap, RefreshCw, ChevronRight, CheckCircle2, AlertTriangle, Loader2 } from 'lucide-react';
import { Subscription, UsageSummary } from '@/types';
import { billingService } from '@/services/billing.service';

export default function BillingOverviewPage() {
  const [subscription, setSubscription] = useState<Subscription | null>(null);
  const [usage, setUsage] = useState<UsageSummary | null>(null);
  const [loading, setLoading] = useState(true);

  const loadData = async () => {
    setLoading(true);
    try {
      const [sub, usg] = await Promise.all([
        billingService.subscription(),
        billingService.usage(),
      ]);
      setSubscription(sub);
      setUsage(usg);
    } catch {
      // Graceful fallback
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadData(); }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20 text-slate-400 text-sm gap-2">
        <Loader2 className="w-5 h-5 animate-spin" /> Loading billing overview...
      </div>
    );
  }

  const planName = subscription?.plan?.name || subscription?.plan_tier || 'Free Tier';
  const status = subscription?.status || 'ACTIVE';

  return (
    <div className="space-y-6 max-w-5xl">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <CreditCard className="w-6 h-6 text-emerald-400" />
          <div>
            <h1 className="text-xl font-bold text-white">Billing & Subscription</h1>
            <p className="text-slate-400 text-sm">Manage your plan, usage limits, and payment history</p>
          </div>
        </div>
        <Link
          href="/billing/plans"
          className="flex items-center gap-2 px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white text-sm font-medium rounded-lg transition"
        >
          <Zap className="w-4 h-4" /> Upgrade Plan
        </Link>
      </div>

      {/* Overview Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* Current Plan Card */}
        <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-5 space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-xs text-slate-400 uppercase tracking-wider font-semibold">Current Plan</span>
            <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
              status === 'ACTIVE' ? 'bg-emerald-900/40 text-emerald-400 border border-emerald-500/30' :
              status === 'TRIALING' ? 'bg-blue-900/40 text-blue-400 border border-blue-500/30' :
              'bg-red-900/40 text-red-400 border border-red-500/30'
            }`}>
              {status}
            </span>
          </div>
          <p className="text-2xl font-bold text-white">{planName}</p>
          <p className="text-xs text-slate-400">
            {subscription?.current_period_end
              ? `Renews on ${new Date(subscription.current_period_end).toLocaleDateString()}`
              : 'Permanent free access'}
          </p>
          {subscription?.cancel_at_period_end && (
            <div className="flex items-center gap-1.5 text-xs text-yellow-400 bg-yellow-900/20 border border-yellow-500/20 p-2 rounded">
              <AlertTriangle className="w-3.5 h-3.5 shrink-0" />
              Cancels at period end
            </div>
          )}
          <Link
            href="/billing/subscription"
            className="flex items-center gap-1 text-xs text-emerald-400 hover:underline pt-2 font-medium"
          >
            Manage Subscription <ChevronRight className="w-3 h-3" />
          </Link>
        </div>

        {/* Quick Links Card */}
        <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-5 space-y-3">
          <span className="text-xs text-slate-400 uppercase tracking-wider font-semibold">Billing Actions</span>
          <div className="space-y-2 pt-1">
            <Link
              href="/billing/payments"
              className="flex items-center justify-between px-3 py-2 bg-slate-900/60 hover:bg-slate-900 rounded-lg text-sm text-slate-200 transition"
            >
              <span>Payment History</span>
              <ChevronRight className="w-4 h-4 text-slate-500" />
            </Link>
            <Link
              href="/billing/invoices"
              className="flex items-center justify-between px-3 py-2 bg-slate-900/60 hover:bg-slate-900 rounded-lg text-sm text-slate-200 transition"
            >
              <span>Invoices & Receipts</span>
              <ChevronRight className="w-4 h-4 text-slate-500" />
            </Link>
          </div>
        </div>

        {/* Features Summary */}
        <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-5 space-y-3">
          <span className="text-xs text-slate-400 uppercase tracking-wider font-semibold">Enabled Features</span>
          <div className="space-y-2 text-xs text-slate-300 pt-1">
            <div className="flex items-center gap-2">
              <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
              <span>Custom Roles: {usage?.usage?.custom_roles_enabled ? 'Enabled' : 'Disabled'}</span>
            </div>
            <div className="flex items-center gap-2">
              <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
              <span>Tournament Mode: {usage?.usage?.tournament_mode_enabled ? 'Enabled' : 'Disabled'}</span>
            </div>
            <div className="flex items-center gap-2">
              <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
              <span>Max Players/Game: {usage?.usage?.max_players_per_game?.limit === -1 ? 'Unlimited' : usage?.usage?.max_players_per_game?.limit || 8}</span>
            </div>
          </div>
        </div>
      </div>

      {/* Resource Usage Breakdown */}
      {usage && (
        <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-6 space-y-5">
          <div className="flex items-center justify-between">
            <h2 className="text-white font-semibold">Resource Usage & Plan Limits</h2>
            <Link href="/billing/usage" className="text-xs text-emerald-400 hover:underline">
              Detailed Usage →
            </Link>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Bots Usage */}
            <div>
              <div className="flex justify-between text-xs mb-1.5">
                <span className="text-slate-400">Bots Created</span>
                <span className="text-white font-medium">
                  {usage.usage.bots.current} / {usage.usage.bots.limit === -1 ? '∞' : usage.usage.bots.limit}
                </span>
              </div>
              <div className="w-full bg-slate-900 rounded-full h-2 overflow-hidden">
                <div
                  className="bg-emerald-500 h-full rounded-full transition-all"
                  style={{
                    width: `${
                      usage.usage.bots.limit === -1
                        ? 10
                        : Math.min(100, ((usage.usage.bots.current || 0) / (usage.usage.bots.limit || 1)) * 100)
                    }%`,
                  }}
                />
              </div>
            </div>

            {/* Active Games Usage */}
            <div>
              <div className="flex justify-between text-xs mb-1.5">
                <span className="text-slate-400">Active Concurrent Games</span>
                <span className="text-white font-medium">
                  {usage.usage.active_games.current} / {usage.usage.active_games.limit === -1 ? '∞' : usage.usage.active_games.limit}
                </span>
              </div>
              <div className="w-full bg-slate-900 rounded-full h-2 overflow-hidden">
                <div
                  className="bg-blue-500 h-full rounded-full transition-all"
                  style={{
                    width: `${
                      usage.usage.active_games.limit === -1
                        ? 10
                        : Math.min(100, ((usage.usage.active_games.current || 0) / (usage.usage.active_games.limit || 1)) * 100)
                    }%`,
                  }}
                />
              </div>
            </div>

            {/* Tournaments Usage */}
            <div>
              <div className="flex justify-between text-xs mb-1.5">
                <span className="text-slate-400">Active Tournaments</span>
                <span className="text-white font-medium">
                  {usage.usage.tournaments.current} / {usage.usage.tournaments.limit === -1 ? '∞' : usage.usage.tournaments.limit}
                </span>
              </div>
              <div className="w-full bg-slate-900 rounded-full h-2 overflow-hidden">
                <div
                  className="bg-purple-500 h-full rounded-full transition-all"
                  style={{
                    width: `${
                      usage.usage.tournaments.limit === -1
                        ? 10
                        : Math.min(100, ((usage.usage.tournaments.current || 0) / Math.max(1, usage.usage.tournaments.limit || 1)) * 100)
                    }%`,
                  }}
                />
              </div>
            </div>

            {/* Saved Templates Usage */}
            <div>
              <div className="flex justify-between text-xs mb-1.5">
                <span className="text-slate-400">Saved Game Templates</span>
                <span className="text-white font-medium">
                  {usage.usage.templates.current} / {usage.usage.templates.limit === -1 ? '∞' : usage.usage.templates.limit}
                </span>
              </div>
              <div className="w-full bg-slate-900 rounded-full h-2 overflow-hidden">
                <div
                  className="bg-yellow-500 h-full rounded-full transition-all"
                  style={{
                    width: `${
                      usage.usage.templates.limit === -1
                        ? 10
                        : Math.min(100, ((usage.usage.templates.current || 0) / Math.max(1, usage.usage.templates.limit || 1)) * 100)
                    }%`,
                  }}
                />
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
