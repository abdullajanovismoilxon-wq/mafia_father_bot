'use client';

import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import { ArrowLeft, CreditCard, AlertTriangle, RefreshCw, XCircle, CheckCircle2, Loader2 } from 'lucide-react';
import { Subscription } from '@/types';
import { billingService } from '@/services/billing.service';

export default function ManageSubscriptionPage() {
  const [subscription, setSubscription] = useState<Subscription | null>(null);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);
  const [msg, setMsg] = useState('');
  const [error, setError] = useState('');

  const load = async () => {
    setLoading(true);
    try {
      const data = await billingService.subscription();
      setSubscription(data);
    } catch {
      setError('Failed to load subscription details.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const handleCancel = async () => {
    if (!confirm('Are you sure you want to cancel your subscription at the end of the billing period?')) return;
    setActionLoading(true);
    setMsg('');
    setError('');
    try {
      const updated = await billingService.cancel();
      setSubscription(updated);
      setMsg('Subscription scheduled for cancellation at period end.');
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Failed to cancel subscription.');
    } finally {
      setActionLoading(false);
    }
  };

  const handleResume = async () => {
    setActionLoading(true);
    setMsg('');
    setError('');
    try {
      const updated = await billingService.resume();
      setSubscription(updated);
      setMsg('Subscription successfully resumed!');
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Failed to resume subscription.');
    } finally {
      setActionLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20 text-slate-400 text-sm gap-2">
        <Loader2 className="w-5 h-5 animate-spin" /> Loading subscription details...
      </div>
    );
  }

  const planName = subscription?.plan?.name || subscription?.plan_tier || 'Free Tier';

  return (
    <div className="space-y-6 max-w-3xl">
      <Link href="/billing" className="flex items-center gap-1 text-slate-400 hover:text-white text-sm transition">
        <ArrowLeft className="w-4 h-4" /> Back to Billing Overview
      </Link>

      <div className="flex items-center gap-3">
        <CreditCard className="w-6 h-6 text-emerald-400" />
        <div>
          <h1 className="text-xl font-bold text-white">Manage Subscription</h1>
          <p className="text-slate-400 text-sm">Control cancellation, plan status, and renewal</p>
        </div>
      </div>

      {msg && (
        <div className="p-4 rounded-xl bg-emerald-900/30 border border-emerald-500/30 text-emerald-400 text-sm flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4 shrink-0" /> {msg}
        </div>
      )}

      {error && (
        <div className="p-4 rounded-xl bg-red-900/30 border border-red-500/30 text-red-400 text-sm">
          {error}
        </div>
      )}

      {/* Subscription Card */}
      <div className="bg-slate-800/50 border border-slate-700 rounded-2xl p-6 space-y-6">
        <div className="flex items-center justify-between border-b border-slate-700/80 pb-4">
          <div>
            <span className="text-xs text-slate-400 uppercase tracking-wider block mb-1 font-semibold">Active Plan</span>
            <span className="text-2xl font-extrabold text-white">{planName}</span>
          </div>
          <span className={`text-xs px-3 py-1 rounded-full font-semibold ${
            subscription?.status === 'ACTIVE' ? 'bg-emerald-900/40 text-emerald-400 border border-emerald-500/30' :
            'bg-slate-700 text-slate-300'
          }`}>
            {subscription?.status || 'ACTIVE'}
          </span>
        </div>

        <div className="grid grid-cols-2 md:grid-cols-3 gap-4 text-sm">
          <div className="bg-slate-900/60 p-3 rounded-xl">
            <span className="text-xs text-slate-500 block mb-1">Provider</span>
            <span className="text-white font-medium">{subscription?.provider || 'MANUAL'}</span>
          </div>
          <div className="bg-slate-900/60 p-3 rounded-xl">
            <span className="text-xs text-slate-500 block mb-1">Period Start</span>
            <span className="text-white font-medium">
              {subscription?.current_period_start ? new Date(subscription.current_period_start).toLocaleDateString() : 'N/A'}
            </span>
          </div>
          <div className="bg-slate-900/60 p-3 rounded-xl">
            <span className="text-xs text-slate-500 block mb-1">Period End</span>
            <span className="text-white font-medium">
              {subscription?.current_period_end ? new Date(subscription.current_period_end).toLocaleDateString() : 'N/A'}
            </span>
          </div>
        </div>

        {/* Cancellation Warning */}
        {subscription?.cancel_at_period_end && (
          <div className="bg-yellow-900/20 border border-yellow-500/30 p-4 rounded-xl space-y-2">
            <div className="flex items-center gap-2 text-yellow-400 font-semibold text-sm">
              <AlertTriangle className="w-4 h-4" /> Subscription Scheduled to Cancel
            </div>
            <p className="text-xs text-slate-300">
              Your subscription will remain active until {new Date(subscription.current_period_end!).toLocaleDateString()}.
              After this date, access will revert to the Free Tier.
            </p>
          </div>
        )}

        {/* Actions */}
        <div className="flex items-center gap-3 pt-2">
          {subscription?.cancel_at_period_end ? (
            <button
              onClick={handleResume}
              disabled={actionLoading}
              className="flex items-center gap-2 px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white text-sm font-semibold rounded-xl transition"
            >
              {actionLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />}
              Resume Subscription
            </button>
          ) : (
            subscription?.plan?.code !== 'free' && (
              <button
                onClick={handleCancel}
                disabled={actionLoading}
                className="flex items-center gap-2 px-4 py-2 bg-slate-700 hover:bg-red-900/40 text-red-400 text-sm font-semibold rounded-xl transition"
              >
                {actionLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <XCircle className="w-4 h-4" />}
                Cancel Subscription
              </button>
            )
          )}
          <Link
            href="/billing/plans"
            className="flex items-center gap-2 px-4 py-2 bg-slate-700 hover:bg-slate-600 text-white text-sm font-semibold rounded-xl transition"
          >
            Change Plan
          </Link>
        </div>
      </div>
    </div>
  );
}
