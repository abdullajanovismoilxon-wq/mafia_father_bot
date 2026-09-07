'use client';

import React, { useEffect, useState } from 'react';
import { adminService, AdminGame } from '@/services/admin.service';
import { Gamepad2, RefreshCw, AlertTriangle, Users, Clock } from 'lucide-react';

export default function AdminGamesPage() {
  const [games, setGames] = useState<AdminGame[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const fetchGames = async () => {
    try {
      setLoading(true);
      setError('');
      const data = await adminService.getGames();
      setGames(data);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to load games.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchGames();
  }, []);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-white">Live & Finished Games Monitor</h2>
          <p className="text-xs text-slate-400">Real-time match lifecycle, player survival and phase transitions</p>
        </div>
        <button
          onClick={fetchGames}
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
      ) : (
        <div className="bg-slate-900 border border-slate-800 rounded-2xl overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm text-slate-300">
              <thead className="bg-slate-950/60 text-xs uppercase tracking-wider text-slate-400 border-b border-slate-800">
                <tr>
                  <th className="py-3.5 px-4">Game ID</th>
                  <th className="py-3.5 px-4">Chat / Group</th>
                  <th className="py-3.5 px-4">Bot Runtime</th>
                  <th className="py-3.5 px-4">Current Phase</th>
                  <th className="py-3.5 px-4">Round</th>
                  <th className="py-3.5 px-4">Alive Players</th>
                  <th className="py-3.5 px-4">Created At</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {games.map((g) => (
                  <tr key={g.id} className="hover:bg-slate-800/30 transition">
                    <td className="py-3 px-4 font-mono text-xs text-slate-400">
                      {g.id.slice(0, 8)}...
                    </td>
                    <td className="py-3 px-4">
                      <div className="font-medium text-white">{g.chat_title}</div>
                      <div className="text-xs text-slate-500">ID: {g.chat_id}</div>
                    </td>
                    <td className="py-3 px-4 text-xs text-slate-300">@{g.bot_username}</td>
                    <td className="py-3 px-4">
                      <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold ${
                        g.phase === 'NIGHT'
                          ? 'bg-indigo-500/10 text-indigo-400 border border-indigo-500/20'
                          : g.phase === 'DAY' || g.phase === 'DISCUSSION'
                          ? 'bg-amber-500/10 text-amber-400 border border-amber-500/20'
                          : g.phase === 'VOTING'
                          ? 'bg-rose-500/10 text-rose-400 border border-rose-500/20'
                          : g.phase === 'FINISHED'
                          ? 'bg-slate-800 text-slate-400'
                          : 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                      }`}>
                        {g.phase}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-xs font-semibold text-white">
                      R{g.round_number}
                    </td>
                    <td className="py-3 px-4">
                      <div className="flex items-center gap-1.5 text-xs text-slate-300">
                        <Users className="w-3.5 h-3.5 text-slate-500" />
                        <span className="font-bold text-emerald-400">{g.alive_count}</span>
                        <span className="text-slate-500">/ {g.players_count}</span>
                      </div>
                    </td>
                    <td className="py-3 px-4 text-xs text-slate-500">
                      {new Date(g.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
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
