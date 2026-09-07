'use client';

import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { Trophy, Plus, Play, X, Users, Loader2, ChevronRight } from 'lucide-react';
import { Tournament, TournamentStatus } from '@/types';
import { tournamentsService } from '@/services/tournaments.service';

const STATUS_BADGE: Record<TournamentStatus, string> = {
  DRAFT: 'bg-slate-700 text-slate-300',
  REGISTRATION: 'bg-blue-900/30 text-blue-400',
  ACTIVE: 'bg-emerald-900/30 text-emerald-400',
  PAUSED: 'bg-yellow-900/30 text-yellow-400',
  FINISHED: 'bg-slate-700 text-slate-500',
  CANCELLED: 'bg-red-900/20 text-red-500',
};

export default function TournamentsPage() {
  const [tournaments, setTournaments] = useState<Tournament[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState('');
  const [form, setForm] = useState({ name: '', description: '', max_players: 24, players_per_game: 6, total_rounds: 3 });
  const router = useRouter();

  const load = async () => {
    setLoading(true);
    try {
      const data = await tournamentsService.list();
      setTournaments(Array.isArray(data) ? data : []);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.name.trim()) { setCreateError('Name is required.'); return; }
    setCreating(true);
    setCreateError('');
    try {
      const t = await tournamentsService.create(form);
      setShowCreate(false);
      router.push(`/tournaments/${t.id}`);
    } catch (err: any) {
      setCreateError(err?.response?.data?.detail || 'Failed to create tournament.');
    } finally {
      setCreating(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Trophy className="w-6 h-6 text-emerald-400" />
          <div>
            <h1 className="text-xl font-bold text-white">Tournaments</h1>
            <p className="text-slate-400 text-sm">Manage multi-round Mafia tournaments</p>
          </div>
        </div>
        <button
          onClick={() => setShowCreate(true)}
          className="flex items-center gap-2 px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white text-sm font-medium rounded-lg transition"
        >
          <Plus className="w-4 h-4" /> New Tournament
        </button>
      </div>

      {/* Create Form Modal */}
      {showCreate && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
          <form
            onSubmit={handleCreate}
            className="bg-slate-800 border border-slate-700 rounded-xl p-6 w-full max-w-md space-y-4 shadow-2xl"
          >
            <div className="flex items-center justify-between mb-2">
              <h2 className="text-white font-semibold">Create Tournament</h2>
              <button type="button" onClick={() => setShowCreate(false)}>
                <X className="w-4 h-4 text-slate-400 hover:text-white" />
              </button>
            </div>

            <div>
              <label className="text-xs text-slate-400 mb-1 block">Tournament Name *</label>
              <input value={form.name} onChange={e => setForm(p => ({ ...p, name: e.target.value }))}
                className="w-full bg-slate-900 border border-slate-600 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-emerald-500"
                placeholder="e.g. Spring 2025 Cup" />
            </div>

            <div>
              <label className="text-xs text-slate-400 mb-1 block">Description</label>
              <textarea value={form.description} onChange={e => setForm(p => ({ ...p, description: e.target.value }))}
                rows={2}
                className="w-full bg-slate-900 border border-slate-600 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-emerald-500 resize-none" />
            </div>

            <div className="grid grid-cols-3 gap-3">
              {([
                ['max_players', 'Max Players'],
                ['players_per_game', 'Per Game'],
                ['total_rounds', 'Rounds'],
              ] as [keyof typeof form, string][]).map(([key, label]) => (
                <div key={key}>
                  <label className="text-xs text-slate-400 mb-1 block">{label}</label>
                  <input
                    type="number"
                    value={form[key] as number}
                    onChange={e => setForm(p => ({ ...p, [key]: Number(e.target.value) }))}
                    min={key === 'total_rounds' ? 1 : 4}
                    className="w-full bg-slate-900 border border-slate-600 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-emerald-500"
                  />
                </div>
              ))}
            </div>

            {createError && (
              <p className="text-red-400 text-xs">{createError}</p>
            )}

            <div className="flex gap-3 pt-2">
              <button type="button" onClick={() => setShowCreate(false)}
                className="flex-1 py-2 bg-slate-700 hover:bg-slate-600 text-slate-300 text-sm rounded-lg">
                Cancel
              </button>
              <button type="submit" disabled={creating}
                className="flex-1 flex items-center justify-center gap-2 py-2 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white text-sm rounded-lg">
                {creating ? <Loader2 className="w-4 h-4 animate-spin" /> : <Plus className="w-4 h-4" />}
                Create
              </button>
            </div>
          </form>
        </div>
      )}

      {loading ? (
        <div className="flex justify-center py-16"><Loader2 className="w-5 h-5 animate-spin text-slate-400" /></div>
      ) : tournaments.length === 0 ? (
        <div className="text-center py-16 text-slate-500">
          <Trophy className="w-10 h-10 mx-auto mb-3 opacity-30" />
          <p className="text-sm">No tournaments yet.</p>
        </div>
      ) : (
        <div className="space-y-3">
          {tournaments.map((t) => (
            <Link
              key={t.id}
              href={`/tournaments/${t.id}`}
              className="flex items-center justify-between bg-slate-800/50 border border-slate-700 hover:border-emerald-500/40 rounded-xl px-5 py-4 transition"
            >
              <div className="flex items-center gap-4">
                <Trophy className="w-5 h-5 text-slate-500" />
                <div>
                  <p className="text-white font-medium">{t.name}</p>
                  <p className="text-slate-500 text-xs mt-0.5">
                    Round {t.current_round}/{t.total_rounds} •{' '}
                    <Users className="w-3 h-3 inline" /> {t.participant_count}/{t.max_players}
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-3">
                <span className={`text-xs px-2 py-0.5 rounded ${STATUS_BADGE[t.status]}`}>
                  {t.status}
                </span>
                <ChevronRight className="w-4 h-4 text-slate-600" />
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
