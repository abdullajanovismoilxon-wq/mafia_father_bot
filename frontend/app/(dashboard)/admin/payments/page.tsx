'use client';

import React, { useEffect, useState } from 'react';
import { adminService, AdminPaymentOrder } from '@/services/admin.service';
import {
  CreditCard, RefreshCw, AlertTriangle, CheckCircle2, XCircle,
  Gem, Clock, User
} from 'lucide-react';

export default function AdminPaymentsPage() {
  const [orders, setOrders] = useState<AdminPaymentOrder[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  const fetchOrders = async () => {
    try {
      setLoading(true);
      setError('');
      const data = await adminService.getPaymentOrders();
      setOrders(data);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to load payment orders.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchOrders();
  }, []);

  const handleReview = async (orderId: string, approve: boolean) => {
    const notes = prompt(
      approve
        ? 'Approval note (e.g. Payme transaction verified):'
        : 'Rejection reason (e.g. Receipt not found):',
      approve ? 'Verified via payment receipt' : 'Invalid payment receipt'
    );
    if (notes === null) return;

    try {
      setActionLoading(orderId);
      await adminService.reviewPaymentOrder(orderId, approve, notes);
      alert(`Order ${approve ? 'APPROVED' : 'REJECTED'} successfully!`);
      await fetchOrders();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to review order.');
    } finally {
      setActionLoading(null);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-white">Manual / P2P Payment Orders Review</h2>
          <p className="text-xs text-slate-400">Review diamond purchase orders and credit virtual wallets safely</p>
        </div>
        <button
          onClick={fetchOrders}
          className="flex items-center gap-2 px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-medium rounded-lg transition"
        >
          <RefreshCw className="w-3.5 h-3.5" />
          Refresh
        </button>
      </div>

      {error && (
        <div className="p-4 bg-rose-500/10 border border-rose-500/20 rounded-xl text-rose-400 flex items-center gap-3">
          <AlertTriangle className="w-5 h-5 flex-shrink-0" />
          <p className="text-sm">{error}</p>
        </div>
      )}

      {loading ? (
        <div className="flex items-center justify-center min-h-[300px]">
          <RefreshCw className="w-6 h-6 animate-spin text-rose-500" />
        </div>
      ) : orders.length === 0 ? (
        <div className="p-12 text-center bg-slate-900 border border-slate-800 rounded-2xl">
          <CreditCard className="w-10 h-10 text-slate-600 mx-auto mb-3" />
          <p className="text-slate-400 font-medium">No pending payment orders found.</p>
        </div>
      ) : (
        <div className="bg-slate-900 border border-slate-800 rounded-2xl overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm text-slate-300">
              <thead className="bg-slate-950/60 text-xs uppercase tracking-wider text-slate-400 border-b border-slate-800">
                <tr>
                  <th className="py-3.5 px-4">Order ID</th>
                  <th className="py-3.5 px-4">Customer</th>
                  <th className="py-3.5 px-4">Diamonds / Amount</th>
                  <th className="py-3.5 px-4">Status</th>
                  <th className="py-3.5 px-4">Admin Notes</th>
                  <th className="py-3.5 px-4">Date</th>
                  <th className="py-3.5 px-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {orders.map((ord) => (
                  <tr key={ord.id} className="hover:bg-slate-800/30 transition">
                    <td className="py-3 px-4 font-mono text-xs font-semibold text-rose-400">
                      {ord.order_id}
                    </td>
                    <td className="py-3 px-4">
                      <div className="text-xs font-medium text-white">{ord.user_email}</div>
                      {ord.telegram_id && (
                        <div className="text-[11px] text-slate-500">TG ID: {ord.telegram_id}</div>
                      )}
                    </td>
                    <td className="py-3 px-4">
                      <div className="text-xs font-semibold text-sky-400 flex items-center gap-1">
                        <Gem className="w-3.5 h-3.5" /> {ord.diamonds} 💎
                      </div>
                      <div className="text-[11px] text-emerald-400 font-medium">${ord.amount_usd}</div>
                    </td>
                    <td className="py-3 px-4">
                      <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-semibold ${
                        ord.status === 'APPROVED'
                          ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                          : ord.status === 'REJECTED'
                          ? 'bg-rose-500/10 text-rose-400 border border-rose-500/20'
                          : 'bg-amber-500/10 text-amber-400 border border-amber-500/20'
                      }`}>
                        {ord.status}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-xs text-slate-400">
                      {ord.admin_notes || '—'}
                    </td>
                    <td className="py-3 px-4 text-xs text-slate-500">
                      {new Date(ord.created_at).toLocaleDateString()}
                    </td>
                    <td className="py-3 px-4 text-right">
                      {ord.status === 'PENDING_REVIEW' ? (
                        <div className="flex items-center justify-end gap-2">
                          <button
                            onClick={() => handleReview(ord.order_id, true)}
                            disabled={actionLoading === ord.order_id}
                            className="px-2.5 py-1 bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-400 text-xs font-semibold rounded-lg transition disabled:opacity-50"
                          >
                            Approve
                          </button>
                          <button
                            onClick={() => handleReview(ord.order_id, false)}
                            disabled={actionLoading === ord.order_id}
                            className="px-2.5 py-1 bg-rose-500/10 hover:bg-rose-500/20 text-rose-400 text-xs font-semibold rounded-lg transition disabled:opacity-50"
                          >
                            Reject
                          </button>
                        </div>
                      ) : (
                        <span className="text-xs text-slate-500">Reviewed</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
