'use client';

import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import { ArrowLeft, CreditCard, Loader2 } from 'lucide-react';
import { Payment } from '@/types';
import { billingService } from '@/services/billing.service';

const STATUS_BADGE: Record<string, string> = {
  SUCCEEDED: 'bg-emerald-900/30 text-emerald-400 border border-emerald-500/30',
  COMPLETED: 'bg-emerald-900/30 text-emerald-400 border border-emerald-500/30',
  PENDING: 'bg-yellow-900/30 text-yellow-400 border border-yellow-500/30',
  PROCESSING: 'bg-blue-900/30 text-blue-400 border border-blue-500/30',
  FAILED: 'bg-red-900/30 text-red-400 border border-red-500/30',
  REFUNDED: 'bg-purple-900/30 text-purple-400 border border-purple-500/30',
};

export default function PaymentsHistoryPage() {
  const [payments, setPayments] = useState<Payment[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const load = async () => {
      try {
        const data = await billingService.payments();
        setPayments(Array.isArray(data) ? data : []);
      } finally {
        setLoading(false);
      }
    };
    load();
  }, []);

  return (
    <div className="space-y-6 max-w-4xl">
      <Link href="/billing" className="flex items-center gap-1 text-slate-400 hover:text-white text-sm transition">
        <ArrowLeft className="w-4 h-4" /> Back to Billing Overview
      </Link>

      <div className="flex items-center gap-3">
        <CreditCard className="w-6 h-6 text-emerald-400" />
        <div>
          <h1 className="text-xl font-bold text-white">Payment History</h1>
          <p className="text-slate-400 text-sm">View all financial transactions and payment attempts</p>
        </div>
      </div>

      {loading ? (
        <div className="flex justify-center py-16">
          <Loader2 className="w-5 h-5 animate-spin text-slate-400" />
        </div>
      ) : (
        <div className="overflow-x-auto rounded-2xl border border-slate-700">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-700 bg-slate-800/80">
                <th className="px-4 py-3 text-left text-slate-400 font-medium">Date</th>
                <th className="px-4 py-3 text-left text-slate-400 font-medium">Amount</th>
                <th className="px-4 py-3 text-left text-slate-400 font-medium">Provider</th>
                <th className="px-4 py-3 text-left text-slate-400 font-medium">Status</th>
                <th className="px-4 py-3 text-left text-slate-400 font-medium">Transaction ID</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-700">
              {payments.map((p) => (
                <tr key={p.id} className="bg-slate-800/30 hover:bg-slate-800/60 transition">
                  <td className="px-4 py-3 text-slate-300">
                    {new Date(p.created_at).toLocaleDateString()} {new Date(p.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                  </td>
                  <td className="px-4 py-3 font-bold text-white">${p.amount} {p.currency}</td>
                  <td className="px-4 py-3 text-slate-300">{p.provider}</td>
                  <td className="px-4 py-3">
                    <span className={`text-xs px-2.5 py-0.5 rounded-full font-medium ${STATUS_BADGE[p.status] || 'bg-slate-700 text-slate-300'}`}>
                      {p.status}
                    </span>
                  </td>
                  <td className="px-4 py-3 font-mono text-xs text-slate-400">
                    {p.provider_payment_id || p.transaction_id || '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {payments.length === 0 && (
            <div className="text-center py-12 text-slate-500 text-sm">No payment records found.</div>
          )}
        </div>
      )}
    </div>
  );
}
