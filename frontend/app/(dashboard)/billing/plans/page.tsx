'use client';

import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import { ArrowLeft, Check, Zap, CreditCard, Loader2, X } from 'lucide-react';
import { Plan, Subscription } from '@/types';
import { billingService } from '@/services/billing.service';

export default function PlansPage() {
  const [plans, setPlans] = useState<Plan[]>([]);
  const [subscription, setSubscription] = useState<Subscription | null>(null);
  const [loading, setLoading] = useState(true);
  const [selectedPlan, setSelectedPlan] = useState<Plan | null>(null);
  const [provider, setProvider] = useState<'STRIPE' | 'PAYME' | 'CLICK'>('STRIPE');
  const [checkoutLoading, setCheckoutLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    const load = async () => {
      try {
        const [pList, sub] = await Promise.all([
          billingService.plans(),
          billingService.subscription(),
        ]);
        setPlans(Array.isArray(pList) ? pList : []);
        setSubscription(sub);
      } finally {
        setLoading(false);
      }
    };
    load();
  }, []);

  const handleCheckout = async () => {
    if (!selectedPlan) return;
    setCheckoutLoading(true);
    setError('');

    try {
      const res = await billingService.checkout({
        plan_code: selectedPlan.code,
        provider,
        return_url: `${window.location.origin}/billing`,
        cancel_url: `${window.location.origin}/billing/plans`,
      });

      if (res.checkout_url) {
        window.location.href = res.checkout_url;
      }
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Failed to initiate checkout.');
    } finally {
      setCheckoutLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20 text-slate-400 text-sm gap-2">
        <Loader2 className="w-5 h-5 animate-spin" /> Loading plans...
      </div>
    );
  }

  const activeCode = subscription?.plan?.code || 'free';

  return (
    <div className="space-y-6 max-w-6xl">
      <Link href="/billing" className="flex items-center gap-1 text-slate-400 hover:text-white text-sm transition">
        <ArrowLeft className="w-4 h-4" /> Back to Billing Overview
      </Link>

      <div className="text-center max-w-xl mx-auto space-y-2">
        <h1 className="text-3xl font-bold text-white">Choose Your Plan</h1>
        <p className="text-slate-400 text-sm">
          Scale your Mafia bot fleet with features, higher limits, and tournament mode.
        </p>
      </div>

      {/* Pricing Cards Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 pt-4">
        {plans.map((plan) => {
          const isCurrent = activeCode === plan.code;
          return (
            <div
              key={plan.id}
              className={`flex flex-col justify-between bg-slate-800/50 border rounded-2xl p-6 relative transition ${
                isCurrent
                  ? 'border-emerald-500 ring-1 ring-emerald-500'
                  : 'border-slate-700 hover:border-slate-600'
              }`}
            >
              {isCurrent && (
                <span className="absolute -top-3 left-1/2 -translate-x-1/2 bg-emerald-600 text-white text-[10px] font-bold uppercase tracking-wider px-2.5 py-0.5 rounded-full">
                  Current Plan
                </span>
              )}

              <div>
                <h3 className="text-lg font-bold text-white mb-1">{plan.name}</h3>
                <p className="text-slate-400 text-xs mb-4 min-h-[36px]">{plan.description}</p>

                <div className="flex items-baseline gap-1 mb-6">
                  <span className="text-3xl font-extrabold text-white">${plan.price}</span>
                  <span className="text-slate-400 text-xs">/month</span>
                </div>

                <div className="space-y-2.5 text-xs text-slate-300 mb-6">
                  {plan.features?.map((feat) => (
                    <div key={feat.feature_code} className="flex items-center gap-2">
                      <Check className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
                      <span>
                        {feat.feature_code.replace(/_/g, ' ')}: {' '}
                        <strong className="text-white">
                          {feat.limit_value === -1 ? 'Unlimited' : feat.enabled ? feat.limit_value : 'Disabled'}
                        </strong>
                      </span>
                    </div>
                  ))}
                </div>
              </div>

              <button
                disabled={isCurrent}
                onClick={() => setSelectedPlan(plan)}
                className={`w-full py-2.5 rounded-xl text-sm font-semibold transition ${
                  isCurrent
                    ? 'bg-slate-700 text-slate-500 cursor-not-allowed'
                    : 'bg-emerald-600 hover:bg-emerald-500 text-white'
                }`}
              >
                {isCurrent ? 'Current Plan' : 'Select Plan'}
              </button>
            </div>
          );
        })}
      </div>

      {/* Provider Checkout Modal */}
      {selectedPlan && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm">
          <div className="bg-slate-800 border border-slate-700 rounded-2xl p-6 w-full max-w-md space-y-5 shadow-2xl">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Zap className="w-5 h-5 text-emerald-400" />
                <h2 className="text-lg font-bold text-white">Subscribe to {selectedPlan.name}</h2>
              </div>
              <button onClick={() => setSelectedPlan(null)} className="text-slate-400 hover:text-white">
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="bg-slate-900/60 p-4 rounded-xl space-y-2">
              <div className="flex justify-between text-sm">
                <span className="text-slate-400">Plan</span>
                <span className="text-white font-semibold">{selectedPlan.name}</span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-slate-400">Amount</span>
                <span className="text-emerald-400 font-bold">${selectedPlan.price} / month</span>
              </div>
            </div>

            {/* Payment Provider Selection */}
            <div className="space-y-2">
              <label className="text-xs text-slate-400 uppercase tracking-wider font-semibold block">
                Select Payment Provider
              </label>
              <div className="grid grid-cols-3 gap-2">
                {[
                  ['STRIPE', '💳 Stripe (Card)'],
                  ['PAYME', '🔹 Payme'],
                  ['CLICK', '🔹 Click'],
                ].map(([code, label]) => (
                  <button
                    key={code}
                    onClick={() => setProvider(code as any)}
                    className={`py-2.5 px-2 text-xs font-semibold rounded-xl border transition ${
                      provider === code
                        ? 'border-emerald-500 bg-emerald-900/20 text-emerald-400'
                        : 'border-slate-700 bg-slate-900/40 text-slate-300 hover:bg-slate-900'
                    }`}
                  >
                    {label}
                  </button>
                ))}
              </div>
            </div>

            {error && (
              <div className="p-3 bg-red-900/30 border border-red-500/30 rounded-xl text-red-400 text-xs">
                {error}
              </div>
            )}

            <button
              onClick={handleCheckout}
              disabled={checkoutLoading}
              className="w-full flex items-center justify-center gap-2 py-3 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white font-semibold rounded-xl transition"
            >
              {checkoutLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <CreditCard className="w-4 h-4" />}
              {checkoutLoading ? 'Redirecting to Provider...' : `Pay $${selectedPlan.price} via ${provider}`}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
