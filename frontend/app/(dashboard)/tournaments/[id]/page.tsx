'use client';

import React, { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import { ArrowLeft, Trophy, Users, BarChart3, Play, X, Loader2 } from 'lucide-react';
import { Tournament, LeaderboardEntry, TournamentRound } from '@/types';
import { tournamentsService } from '@/services/tournaments.service';

export default function TournamentDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [tournament, setTournament] = useState<Tournament | null>(null);
  const [leaderboard, setLeaderboard] = useState<LeaderboardEntry[]>([]);
  const [rounds, setRounds] = useState<TournamentRound[]>([]);
  const [loading, setLoading] = useState(true);
  const [acting, setActing] = useState(false);
  const [error, setError] = useState('');
  const [activeTab, setActiveTab] = useState<'overview' | 'leaderboard' | 'rounds'>('overview');

  const load = async () => {
    setLoading(true);
    try {
      const [t, lb, r] = await Promise.all([
        tournamentsService.get(id),
        tournamentsService.leaderboard(id),
        tournamentsService.rounds(id),
      ]);
      setTournament(t);
      setLeaderboard(lb);
      setRounds(r);
    } catch {
      setError('Tournament not found.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, [id]);

  const handleAction = async (action: 'start' | 'cancel' | 'openRegistration') => {
    setActing(true);
    setError('');
    try {
      if (action === 'start') await tournamentsService.start(id);
      else if (action === 'cancel') await tournamentsService.cancel(id);
      else await tournamentsService.openRegistration(id);
      await load();
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Action failed.');
    } finally {
      setActing(false);
    }
  };

  if (loading) return <div className="flex justify-center py-20"><Loader2 className="w-5 h-5 animate-spin text-slate-400" /></div>;
  if (error || !tournament) return <div className="text-red-400 text-sm py-10 text-center">{error || 'Not found.'}</div>;

  const MEDAL = ['🥇', '🥈', '🥉'];

  return (
    <div className="space-y-6 max-w-3xl">
      <Link href="/tournaments" className="flex items-center gap-1 text-slate-400 hover:text-white text-sm transition">
        <ArrowLeft className="w-4 h-4" /> Back to Tournaments
      </Link>

      {/* Header */}
      <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-6">
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-3">
            <Trophy className="w-6 h-6 text-yellow-400" />
            <div>
              <h1 className="text-xl font-bold text-white">{tournament.name}</h1>
              <p className="text-slate-400 text-sm">{tournament.description || 'No description'}</p>
            </div>
          </div>
          <span className={`text-xs px-2.5 py-1 rounded-full font-medium ${
            tournament.status === 'ACTIVE' ? 'bg-emerald-900/30 text-emerald-400' :
            tournament.status === 'REGISTRATION' ? 'bg-blue-900/30 text-blue-400' :
            tournament.status === 'FINISHED' ? 'bg-slate-700 text-slate-400' :
            'bg-slate-700 text-slate-400'
          }`}>
            {tournament.status}
          </span>
        </div>

        <div className="grid grid-cols-4 gap-3 mt-5">
          {[
            ['Participants', `${tournament.participant_count}/${tournament.max_players}`],
            ['Per Game', tournament.players_per_game],
            ['Rounds', `${tournament.current_round}/${tournament.total_rounds}`],
            ['Owner', tournament.owner_email.split('@')[0]],
          ].map(([label, value]) => (
            <div key={label} className="bg-slate-900/60 rounded-lg p-3 text-center">
              <p className="text-xs text-slate-500 mb-1">{label}</p>
              <p className="text-sm font-bold text-white">{value}</p>
            </div>
          ))}
        </div>

        {/* Actions */}
        <div className="flex gap-3 mt-5">
          {tournament.status === 'DRAFT' && (
            <button onClick={() => handleAction('openRegistration')} disabled={acting}
              className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white text-sm rounded-lg transition">
              {acting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Users className="w-4 h-4" />}
              Open Registration
            </button>
          )}
          {tournament.status === 'REGISTRATION' && (
            <button onClick={() => handleAction('start')} disabled={acting}
              className="flex items-center gap-2 px-4 py-2 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white text-sm rounded-lg transition">
              {acting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />}
              Start Tournament
            </button>
          )}
          {!['FINISHED', 'CANCELLED'].includes(tournament.status) && (
            <button onClick={() => handleAction('cancel')} disabled={acting}
              className="flex items-center gap-2 px-4 py-2 bg-slate-700 hover:bg-red-900/40 text-red-400 text-sm rounded-lg transition">
              {acting ? <Loader2 className="w-4 h-4 animate-spin" /> : <X className="w-4 h-4" />}
              Cancel
            </button>
          )}
        </div>

        {error && <p className="text-red-400 text-xs mt-3">{error}</p>}
      </div>

      {/* Tabs */}
      <div className="flex gap-2">
        {(['overview', 'leaderboard', 'rounds'] as const).map((tab) => (
          <button key={tab} onClick={() => setActiveTab(tab)}
            className={`px-4 py-2 text-sm rounded-lg font-medium transition capitalize ${
              activeTab === tab ? 'bg-emerald-600 text-white' : 'bg-slate-800 text-slate-300 hover:bg-slate-700'
            }`}>
            {tab}
          </button>
        ))}
      </div>

      {activeTab === 'overview' && (
        <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-5 space-y-2">
          <h2 className="text-white font-semibold mb-4">Scoring Rules</h2>
          {Object.entries(tournament.scoring_config || {}).map(([key, val]) => (
            <div key={key} className="flex justify-between text-sm">
              <span className="text-slate-400 capitalize">{key.replace(/_/g, ' ')}</span>
              <span className="text-white font-medium">+{val} pts</span>
            </div>
          ))}
        </div>
      )}

      {activeTab === 'leaderboard' && (
        <div className="bg-slate-800/50 border border-slate-700 rounded-xl overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-700 bg-slate-800/80">
                <th className="px-4 py-3 text-left text-slate-400">Rank</th>
                <th className="px-4 py-3 text-left text-slate-400">Player</th>
                <th className="px-4 py-3 text-center text-slate-400">Score</th>
                <th className="px-4 py-3 text-center text-slate-400">W</th>
                <th className="px-4 py-3 text-center text-slate-400">K</th>
                <th className="px-4 py-3 text-center text-slate-400">S</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-700">
              {leaderboard.map((entry) => (
                <tr key={entry.telegram_user_id} className="bg-slate-800/30">
                  <td className="px-4 py-3 text-lg">{MEDAL[entry.rank - 1] || entry.rank}</td>
                  <td className="px-4 py-3 text-white">{entry.display_name}</td>
                  <td className="px-4 py-3 text-center font-bold text-emerald-400">{entry.score}</td>
                  <td className="px-4 py-3 text-center text-blue-400">{entry.games_won}</td>
                  <td className="px-4 py-3 text-center text-red-400">{entry.kills}</td>
                  <td className="px-4 py-3 text-center text-yellow-400">{entry.survival_count}</td>
                </tr>
              ))}
              {leaderboard.length === 0 && (
                <tr><td colSpan={6} className="text-center py-8 text-slate-500 text-sm">No scores yet.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {activeTab === 'rounds' && (
        <div className="space-y-3">
          {rounds.map((round) => (
            <div key={round.id} className="bg-slate-800/50 border border-slate-700 rounded-xl px-5 py-4 flex justify-between items-center">
              <div>
                <p className="text-white font-medium">Round {round.number}</p>
                <p className="text-slate-500 text-xs">{round.games_count} games</p>
              </div>
              <span className={`text-xs px-2 py-0.5 rounded ${
                round.status === 'ACTIVE' ? 'bg-emerald-900/30 text-emerald-400' :
                round.status === 'FINISHED' ? 'bg-slate-700 text-slate-400' :
                'bg-slate-700 text-slate-500'
              }`}>{round.status}</span>
            </div>
          ))}
          {rounds.length === 0 && (
            <div className="text-center py-8 text-slate-500 text-sm">No rounds started yet.</div>
          )}
        </div>
      )}
    </div>
  );
}
