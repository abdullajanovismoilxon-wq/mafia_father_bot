'use client';

import React, { useEffect, useState } from 'react';
import { adminService, AdminUser } from '@/services/admin.service';
import {
  Users, RefreshCw, AlertTriangle, ShieldCheck, Ban, CheckCircle2,
  Gem, DollarSign, Crown, Search
} from 'lucide-react';

export default function AdminUsersPage() {
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [error, setError] = useState('');

  // Balance Adjustment Modal State
  const [selectedUser, setSelectedUser] = useState<AdminUser | null>(null);
  const [balanceModalOpen, setBalanceModalOpen] = useState(false);
  const [currency, setCurrency] = useState('DIAMONDS');
  const [amount, setAmount] = useState<number>(10);
  const [reason, setReason] = useState('Admin compensation / reward');

  const fetchUsers = async () => {
    try {
      setLoading(true);
      setError('');
      const data = await adminService.getUsers(search);
      setUsers(data);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to load users.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchUsers();
  }, []);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    fetchUsers();
  };

  const handleToggleSuspend = async (user: AdminUser) => {
    try {
      if (user.is_suspended) {
        await adminService.activateUser(user.id);
      } else {
        const reason = prompt('Enter suspension reason:', 'Violation of terms');
        if (reason === null) return;
        await adminService.suspendUser(user.id, reason);
      }
      await fetchUsers();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to update user status.');
    }
  };

  const handleGrantVip = async (user: AdminUser) => {
    const level = prompt('Enter VIP Level (GOLD or DIAMOND):', 'GOLD');
    if (!level) return;
    try {
      await adminService.grantVip(user.id, level.toUpperCase(), 30);
      alert(`VIP ${level.toUpperCase()} successfully granted for 30 days!`);
      await fetchUsers();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to grant VIP.');
    }
  };

  const handleAdjustBalanceSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedUser) return;
    try {
      await adminService.adjustBalance(selectedUser.id, currency, amount, reason);
      alert('Balance successfully adjusted!');
      setBalanceModalOpen(false);
      await fetchUsers();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to adjust balance.');
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h2 className="text-lg font-semibold text-white">Platform Users & RBAC Control</h2>
          <p className="text-xs text-slate-400">Account status, balance adjustments, and VIP subscription management</p>
        </div>
        <form onSubmit={handleSearch} className="flex items-center gap-2">
          <div className="relative">
            <Search className="w-4 h-4 text-slate-500 absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              placeholder="Search by email / username..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="pl-9 pr-4 py-1.5 bg-slate-900 border border-slate-800 rounded-lg text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-rose-500"
            />
          </div>
          <button
            type="submit"
            className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-medium rounded-lg transition"
          >
            Search
          </button>
        </form>
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
      ) : (
        <div className="bg-slate-900 border border-slate-800 rounded-2xl overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm text-slate-300">
              <thead className="bg-slate-950/60 text-xs uppercase tracking-wider text-slate-400 border-b border-slate-800">
                <tr>
                  <th className="py-3.5 px-4">User</th>
                  <th className="py-3.5 px-4">Role</th>
                  <th className="py-3.5 px-4">Plan / VIP</th>
                  <th className="py-3.5 px-4">Wallet Balance</th>
                  <th className="py-3.5 px-4">Bots</th>
                  <th className="py-3.5 px-4">Status</th>
                  <th className="py-3.5 px-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {users.map((u) => (
                  <tr key={u.id} className="hover:bg-slate-800/30 transition">
                    <td className="py-3 px-4">
                      <div className="font-medium text-white">{u.email}</div>
                      <div className="text-xs text-slate-500">@{u.username}</div>
                    </td>
                    <td className="py-3 px-4">
                      <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-semibold ${
                        u.role === 'SUPERADMIN' || u.role === 'ADMIN'
                          ? 'bg-rose-500/10 text-rose-400 border border-rose-500/20'
                          : u.role === 'MODERATOR'
                          ? 'bg-purple-500/10 text-purple-400 border border-purple-500/20'
                          : 'bg-slate-800 text-slate-400'
                      }`}>
                        {u.role}
                      </span>
                    </td>
                    <td className="py-3 px-4">
                      <div className="text-xs font-medium text-slate-300">{u.subscription_plan}</div>
                      {u?.vip?.is_vip && (
                        <div className="text-[11px] text-amber-400 font-semibold flex items-center gap-1 mt-0.5">
                          <Crown className="w-3 h-3" /> VIP {u.vip.level}
                        </div>
                      )}
                    </td>
                    <td className="py-3 px-4">
                      <div className="text-xs text-slate-300">
                        <span className="text-emerald-400 font-medium">${u?.wallet?.money ?? '0.00'}</span>
                        <span className="mx-1.5 text-slate-600">|</span>
                        <span className="text-sky-400 font-medium">{u?.wallet?.diamonds ?? 0} 💎</span>
                        <span className="mx-1.5 text-slate-600">|</span>
                        <span className="text-amber-400 font-medium">{u?.wallet?.coins ?? 0} 🪙</span>
                      </div>
                    </td>
                    <td className="py-3 px-4 text-xs font-semibold text-slate-300">
                      {u.bots_count}
                    </td>
                    <td className="py-3 px-4">
                      <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-medium ${
                        u.is_suspended
                          ? 'bg-rose-500/10 text-rose-400 border border-rose-500/20'
                          : 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                      }`}>
                        {u.is_suspended ? 'Suspended' : 'Active'}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-right">
                      <div className="flex items-center justify-end gap-2">
                        <button
                          onClick={() => {
                            setSelectedUser(u);
                            setBalanceModalOpen(true);
                          }}
                          className="px-2.5 py-1 bg-slate-800 hover:bg-slate-700 text-sky-400 text-xs font-medium rounded-lg transition"
                        >
                          Adjust Funds
                        </button>
                        <button
                          onClick={() => handleGrantVip(u)}
                          className="px-2.5 py-1 bg-amber-500/10 hover:bg-amber-500/20 text-amber-400 text-xs font-medium rounded-lg transition"
                        >
                          Grant VIP
                        </button>
                        <button
                          onClick={() => handleToggleSuspend(u)}
                          className={`p-1.5 rounded-lg text-xs font-medium transition ${
                            u.is_suspended
                              ? 'bg-emerald-500/10 text-emerald-400 hover:bg-emerald-500/20'
                              : 'bg-rose-500/10 text-rose-400 hover:bg-rose-500/20'
                          }`}
                          title={u.is_suspended ? 'Activate User' : 'Suspend User'}
                        >
                          {u.is_suspended ? <CheckCircle2 className="w-4 h-4" /> : <Ban className="w-4 h-4" />}
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Adjust Balance Modal */}
      {balanceModalOpen && selectedUser && (
        <div className="fixed inset-0 z-50 bg-black/70 flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-md w-full p-6 space-y-4">
            <h3 className="text-lg font-bold text-white">Adjust Balance for {selectedUser.email}</h3>
            <form onSubmit={handleAdjustBalanceSubmit} className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-slate-400 mb-1">Currency</label>
                <select
                  value={currency}
                  onChange={(e) => setCurrency(e.target.value)}
                  className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-sm text-white focus:outline-none focus:border-rose-500"
                >
                  <option value="DIAMONDS">💎 Diamonds</option>
                  <option value="MONEY">💵 Money (USD)</option>
                  <option value="COINS">🪙 Coins</option>
                </select>
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-400 mb-1">
                  Amount (Positive to add, Negative to deduct)
                </label>
                <input
                  type="number"
                  step="any"
                  value={amount}
                  onChange={(e) => setAmount(parseFloat(e.target.value))}
                  required
                  className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-sm text-white focus:outline-none focus:border-rose-500"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-400 mb-1">Reason (Audit Trail)</label>
                <input
                  type="text"
                  value={reason}
                  onChange={(e) => setReason(e.target.value)}
                  required
                  className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-sm text-white focus:outline-none focus:border-rose-500"
                />
              </div>
              <div className="flex justify-end gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => setBalanceModalOpen(false)}
                  className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-medium rounded-lg transition"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 bg-rose-600 hover:bg-rose-500 text-white text-xs font-medium rounded-lg transition"
                >
                  Confirm Adjustment
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
