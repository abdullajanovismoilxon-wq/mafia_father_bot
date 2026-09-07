'use client';

import React, { useEffect, useState } from 'react';
import { adminService, AdminBot } from '@/services/admin.service';
import {
  Bot, RefreshCw, Power, RotateCw, PauseCircle, PlayCircle,
  AlertTriangle, Shield, CheckCircle2
} from 'lucide-react';

export default function AdminBotsPage() {
  const [bots, setBots] = useState<AdminBot[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  const fetchBots = async () => {
    try {
      setLoading(true);
      setError('');
      const data = await adminService.getBots();
      setBots(data);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to load bots.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchBots();
  }, []);

  const handleAction = async (botId: string, actionType: 'suspend' | 'resume' | 'restart' | 'stop') => {
    try {
      setActionLoading(botId);
      if (actionType === 'suspend') await adminService.suspendBot(botId);
      else if (actionType === 'resume') await adminService.resumeBot(botId);
      else if (actionType === 'restart') await adminService.restartBot(botId);
      else if (actionType === 'stop') await adminService.stopBot(botId);
      await fetchBots();
    } catch (err: any) {
      alert(err.response?.data?.detail || `Failed to execute ${actionType} action.`);
    } finally {
      setActionLoading(null);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-white">Global Bot Runtimes Control Plane</h2>
          <p className="text-xs text-slate-400">Monitor, restart, suspend or stop tenant bots across the fleet</p>
        </div>
        <button
          onClick={fetchBots}
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
                  <th className="py-3.5 px-4">Bot Info</th>
                  <th className="py-3.5 px-4">Owner</th>
                  <th className="py-3.5 px-4">Registry Status</th>
                  <th className="py-3.5 px-4">Runtime</th>
                  <th className="py-3.5 px-4">Active Games</th>
                  <th className="py-3.5 px-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {bots.map((bot) => (
                  <tr key={bot.id} className="hover:bg-slate-800/30 transition">
                    <td className="py-3 px-4">
                      <div className="font-medium text-white">{bot.name}</div>
                      <div className="text-xs text-slate-500">@{bot.username}</div>
                    </td>
                    <td className="py-3 px-4 text-xs text-slate-400">{bot.owner_email}</td>
                    <td className="py-3 px-4">
                      <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-medium ${
                        bot.status === 'ACTIVE'
                          ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                          : bot.status === 'SUSPENDED'
                          ? 'bg-rose-500/10 text-rose-400 border border-rose-500/20'
                          : 'bg-slate-800 text-slate-400'
                      }`}>
                        {bot.status}
                      </span>
                    </td>
                    <td className="py-3 px-4">
                      <span className={`inline-flex items-center gap-1.5 text-xs ${
                        bot.runtime_status === 'RUNNING'
                          ? 'text-emerald-400'
                          : bot.runtime_status === 'ERROR'
                          ? 'text-rose-400'
                          : 'text-slate-500'
                      }`}>
                        <span className={`w-1.5 h-1.5 rounded-full ${
                          bot.runtime_status === 'RUNNING'
                            ? 'bg-emerald-400 animate-pulse'
                            : bot.runtime_status === 'ERROR'
                            ? 'bg-rose-400'
                            : 'bg-slate-600'
                        }`} />
                        {bot.runtime_status}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-xs font-semibold text-white">
                      {bot.active_games} active
                    </td>
                    <td className="py-3 px-4 text-right">
                      <div className="flex items-center justify-end gap-1.5">
                        <button
                          onClick={() => handleAction(bot.id, 'restart')}
                          disabled={actionLoading === bot.id}
                          title="Restart Runtime"
                          className="p-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white rounded-lg transition disabled:opacity-50"
                        >
                          <RotateCw className="w-4 h-4" />
                        </button>
                        {bot.status === 'SUSPENDED' ? (
                          <button
                            onClick={() => handleAction(bot.id, 'resume')}
                            disabled={actionLoading === bot.id}
                            title="Unsuspend / Resume"
                            className="p-1.5 bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-400 rounded-lg transition disabled:opacity-50"
                          >
                            <PlayCircle className="w-4 h-4" />
                          </button>
                        ) : (
                          <button
                            onClick={() => handleAction(bot.id, 'suspend')}
                            disabled={actionLoading === bot.id}
                            title="Suspend Bot"
                            className="p-1.5 bg-rose-500/10 hover:bg-rose-500/20 text-rose-400 rounded-lg transition disabled:opacity-50"
                          >
                            <PauseCircle className="w-4 h-4" />
                          </button>
                        )}
                        <button
                          onClick={() => handleAction(bot.id, 'stop')}
                          disabled={actionLoading === bot.id}
                          title="Stop Runtime"
                          className="p-1.5 bg-slate-800 hover:bg-slate-700 text-slate-400 hover:text-rose-400 rounded-lg transition disabled:opacity-50"
                        >
                          <Power className="w-4 h-4" />
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
    </div>
  );
}
