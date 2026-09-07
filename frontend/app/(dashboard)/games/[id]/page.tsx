'use client';

import React, { useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { ArrowLeft, Play, Square, Shield, Users, Trophy } from 'lucide-react';
import { gamesService } from '../../../../services/games.service';
import { Game } from '../../../../types';

export default function GameDetailPage() {
  const params = useParams();
  const router = useRouter();
  const id = params.id as string;

  const [game, setGame] = useState<Game | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const fetchDetail = () => {
    setLoading(true);
    gamesService
      .getGameDetail(id)
      .then((data) => setGame(data))
      .catch((err) => setError('Failed to load game details.'))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    if (id) fetchDetail();
  }, [id]);

  const handleStart = async () => {
    try {
      await gamesService.startGame(id);
      fetchDetail();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to start game.');
    }
  };

  const handleCancel = async () => {
    if (!confirm('Are you sure you want to cancel this game?')) return;
    try {
      await gamesService.cancelGame(id);
      fetchDetail();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to cancel game.');
    }
  };

  if (loading) {
    return <div className="p-8 text-center text-slate-400 font-mono text-sm">Loading game monitor...</div>;
  }

  if (error || !game) {
    return (
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-8 text-center">
        <p className="text-rose-400 text-sm mb-4">{error || 'Game not found.'}</p>
        <button onClick={() => router.push('/games')} className="px-4 py-2 bg-slate-800 text-slate-300 text-sm rounded-lg">
          Back to Games
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <button
            onClick={() => router.push('/games')}
            className="p-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg transition"
          >
            <ArrowLeft className="w-4 h-4" />
          </button>
          <div>
            <h1 className="text-2xl font-bold text-white flex items-center gap-2">
              Game Monitor #{game.id.substring(0, 8)}
            </h1>
            <p className="text-slate-400 text-xs font-mono">Hosted on Bot: {game.bot_name} | Chat ID: {game.chat_id}</p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          {game.phase === 'WAITING' && (
            <button
              onClick={handleStart}
              className="flex items-center gap-1.5 px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold rounded-lg transition"
            >
              <Play className="w-3.5 h-3.5 fill-current" /> Start Game
            </button>
          )}
          {game.phase !== 'FINISHED' && game.phase !== 'CANCELED' && (
            <button
              onClick={handleCancel}
              className="flex items-center gap-1.5 px-4 py-2 bg-rose-950/80 text-rose-300 border border-rose-800 hover:bg-rose-900 text-xs font-semibold rounded-lg transition"
            >
              <Square className="w-3.5 h-3.5 fill-current" /> Cancel Game
            </button>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
        <div className="bg-slate-900 border border-slate-800 p-5 rounded-xl">
          <p className="text-xs text-slate-400 uppercase tracking-wider">Current Phase</p>
          <p className="text-xl font-bold text-emerald-400 mt-1">{game.phase}</p>
        </div>

        <div className="bg-slate-900 border border-slate-800 p-5 rounded-xl">
          <p className="text-xs text-slate-400 uppercase tracking-wider">Round Number</p>
          <p className="text-xl font-bold text-white mt-1">#{game.round_number}</p>
        </div>

        <div className="bg-slate-900 border border-slate-800 p-5 rounded-xl">
          <p className="text-xs text-slate-400 uppercase tracking-wider">Alive Players</p>
          <p className="text-xl font-bold text-white mt-1">{game.alive_players_count} / {game.players_count}</p>
        </div>

        <div className="bg-slate-900 border border-slate-800 p-5 rounded-xl">
          <p className="text-xs text-slate-400 uppercase tracking-wider">Winner Faction</p>
          <p className="text-xl font-bold text-purple-300 mt-1">{game.winner_team || 'In Progress'}</p>
        </div>
      </div>

      <div className="bg-slate-900 border border-slate-800 rounded-xl p-6">
        <h3 className="text-lg font-bold text-white mb-4 flex items-center gap-2">
          <Users className="w-5 h-5 text-emerald-400" /> Game Participants ({game.players?.length || 0})
        </h3>

        {!game.players || game.players.length === 0 ? (
          <p className="text-slate-500 text-sm">No players have joined yet.</p>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {game.players.map((player) => (
              <div key={player.id} className="bg-slate-950 border border-slate-800/80 p-4 rounded-lg flex items-center justify-between">
                <div>
                  <p className="font-semibold text-white text-sm">{player.display_name || player.username}</p>
                  <p className="text-xs text-slate-400 font-mono">ID: {player.telegram_user_id}</p>
                </div>
                <div className="text-right">
                  <span className={`text-xs px-2.5 py-0.5 rounded-full font-semibold border ${
                    player.is_alive
                      ? 'bg-emerald-950 text-emerald-400 border-emerald-800'
                      : 'bg-rose-950 text-rose-400 border-rose-800'
                  }`}>
                    {player.is_alive ? 'ALIVE' : 'DEAD'}
                  </span>
                  {player.role_name && (
                    <p className="text-[11px] text-slate-400 mt-1 font-mono">{player.role_name}</p>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
