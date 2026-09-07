'use client';

import React, { useEffect, useState } from 'react';
import { apiClient } from '@/lib/api-client';
import { Users, UserPlus, Trash2, Key, ShieldCheck, RefreshCw, AlertCircle } from 'lucide-react';

interface CoAdmin {
  id: string;
  username: string;
  email: string;
  group_name: string;
  role: string;
  created_at: string;
  raw_password?: string;
}

export default function CoAdminsPage() {
  const [coAdmins, setCoAdmins] = useState<CoAdmin[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  
  // Modal state
  const [modalOpen, setModalOpen] = useState(false);
  const [username, setUsername] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [createdCredentials, setCreatedCredentials] = useState<{ email: string; pass: string } | null>(null);

  const fetchCoAdmins = async () => {
    try {
      setLoading(true);
      setError('');
      const res = await apiClient.get('/auth/co-admins/');
      setCoAdmins(res.data);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to load co-admins.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchCoAdmins();
  }, []);

  const handleCreateCoAdmin = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const res = await apiClient.post('/auth/co-admins/', {
        username,
        email,
        password: password || undefined,
      });
      const newAdmin = res.data;
      setCreatedCredentials({
        email: newAdmin.email,
        pass: newAdmin.raw_password || password || 'Generated',
      });
      setUsername('');
      setEmail('');
      setPassword('');
      fetchCoAdmins();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to create co-admin.');
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm('Are you sure you want to remove this co-admin?')) return;
    try {
      await apiClient.delete(`/auth/co-admins/${id}/`);
      fetchCoAdmins();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to remove co-admin.');
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h2 className="text-lg font-semibold text-white">Guruh Adminlarini Boshqarish (Co-Admins)</h2>
          <p className="text-xs text-slate-400">Guruhingizni birgalikda boshqarish uchun 3-4 ta moderator/admin qoʻshing</p>
        </div>
        <button
          onClick={() => {
            setCreatedCredentials(null);
            setModalOpen(true);
          }}
          className="flex items-center gap-2 px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold rounded-xl transition shadow-lg shadow-emerald-600/20"
        >
          <UserPlus className="w-4 h-4" />
          Yangi Admin Qoʻshish
        </button>
      </div>

      {createdCredentials && (
        <div className="p-4 bg-emerald-500/10 border border-emerald-500/30 rounded-xl space-y-2 text-emerald-300">
          <div className="flex items-center gap-2 font-semibold text-sm">
            <ShieldCheck className="w-5 h-5 text-emerald-400" />
            Yangi Admin Muvaffaqiyatli Yaratildi!
          </div>
          <p className="text-xs text-slate-300">Ushbu login va parolni admin sherigingizga berishingiz mumkin:</p>
          <div className="p-3 bg-slate-950 rounded-lg border border-slate-800 text-xs font-mono space-y-1">
            <div>Email: <span className="text-emerald-400 font-bold">{createdCredentials.email}</span></div>
            <div>Parol: <span className="text-amber-400 font-bold">{createdCredentials.pass}</span></div>
          </div>
        </div>
      )}

      {error && (
        <div className="p-4 bg-rose-500/10 border border-rose-500/20 rounded-xl text-rose-400 flex items-center gap-3 text-xs">
          <AlertCircle className="w-4 h-4 flex-shrink-0" />
          <p>{error}</p>
        </div>
      )}

      {loading ? (
        <div className="flex items-center justify-center min-h-[200px]">
          <RefreshCw className="w-6 h-6 animate-spin text-emerald-500" />
        </div>
      ) : coAdmins.length === 0 ? (
        <div className="p-12 text-center bg-slate-900 border border-slate-800 rounded-2xl space-y-3">
          <Users className="w-10 h-10 text-slate-600 mx-auto" />
          <h3 className="text-sm font-semibold text-slate-300">Hali Co-Adminlar mavjud emas</h3>
          <p className="text-xs text-slate-500">Guruhingizni birgalikda boshqarish uchun admin sheriklaringizni taklif qiling.</p>
        </div>
      ) : (
        <div className="bg-slate-900 border border-slate-800 rounded-2xl overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-950/60 text-slate-400 border-b border-slate-800 uppercase tracking-wider font-semibold">
                <tr>
                  <th className="py-3.5 px-4">Admin Foydalanuvchi</th>
                  <th className="py-3.5 px-4">Guruh Nomi</th>
                  <th className="py-3.5 px-4">Roli</th>
                  <th className="py-3.5 px-4">Qoʻshilgan Sana</th>
                  <th className="py-3.5 px-4 text-right">Amallar</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {coAdmins.map((ca) => (
                  <tr key={ca.id} className="hover:bg-slate-800/30 transition">
                    <td className="py-3 px-4">
                      <div className="font-semibold text-white">{ca.email}</div>
                      <div className="text-[11px] text-slate-500">@{ca.username}</div>
                    </td>
                    <td className="py-3 px-4 text-slate-300 font-medium">{ca.group_name}</td>
                    <td className="py-3 px-4">
                      <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-semibold bg-purple-500/10 text-purple-400 border border-purple-500/20">
                        {ca.role}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-slate-400">{new Date(ca.created_at).toLocaleDateString()}</td>
                    <td className="py-3 px-4 text-right">
                      <button
                        onClick={() => handleDelete(ca.id)}
                        className="p-1.5 text-slate-400 hover:text-rose-400 hover:bg-rose-500/10 rounded-lg transition"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Modal */}
      {modalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm">
          <div className="w-full max-w-md bg-slate-900 border border-slate-800 rounded-2xl p-6 space-y-4 shadow-2xl">
            <div className="flex items-center justify-between">
              <h3 className="text-base font-semibold text-white">Yangi Co-Admin Yaratish</h3>
              <button onClick={() => setModalOpen(false)} className="text-slate-400 hover:text-white">✕</button>
            </div>

            <form onSubmit={handleCreateCoAdmin} className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-slate-400 mb-1">Username</label>
                <input
                  type="text"
                  required
                  placeholder="masalan: bloody_admin1"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-xs text-white focus:outline-none focus:border-emerald-500"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-400 mb-1">Email</label>
                <input
                  type="email"
                  required
                  placeholder="masalan: admin1@bloodygroup.uz"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-xs text-white focus:outline-none focus:border-emerald-500"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-400 mb-1">Parol (Boʻsh qolsa avtomatik generatsiya boʻladi)</label>
                <input
                  type="password"
                  placeholder="Parolni kiriting..."
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-xs text-white focus:outline-none focus:border-emerald-500"
                />
              </div>

              <div className="flex items-center justify-end gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => setModalOpen(false)}
                  className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-medium rounded-xl transition"
                >
                  Bekor qilish
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold rounded-xl transition"
                >
                  Yaratish
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
