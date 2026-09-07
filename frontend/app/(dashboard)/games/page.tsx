'use client';

import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import { Gamepad2, Eye, Shield, Users } from 'lucide-react';
import { gamesService } from '../../../services/games.service';
import { Game } from '../../../types';

export default function GamesPage() {
  const [games, setGames] = useState<Game[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    gamesService
      .getGames()
      .then((data) => setGames(data))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-white mb-1">Active Games Monitoring</h1>
        <p className="text-slate-400 text-sm">
          Real-time monitoring of Mafia games running across your Telegram bot instances
        </p>
      </div>

      {loading ? (
        <div className="p-8 text-center text-slate-400 font-mono text-sm">Loading active games...</div>
      ) : games.length === 0 ? (
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-12 text-center">
          <Gamepad2 className="w-12 h-12 text-slate-600 mx-auto mb-3" />
          <h3 className="text-lg font-semibold text-slate-300">No Active Games Found</h3>
          <p className="text-sm text-slate-500 mt-1">
            Start a game in a Telegram Group Chat using <code className="text-emerald-400">/create_game</code>!
          </p>
        </div>
      ) : (
        <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden shadow-xl">
          <table className="w-full text-left text-sm text-slate-300">
            <thead className="bg-slate-950 text-xs uppercase text-slate-400 border-b border-slate-800">
              <tr>
                <th className="px-6 py-3.5">Game ID</th>
                <th className="px-6 py-3.5">Bot Name</th>
                <th className="px-6 py-3.5">Phase / Status</th>
                <th className="px-6 py-3.5">Round</th>
                <th className="px-6 py-3.5">Alive / Total</th>
                <th className="px-6 py-3.5">Created At</th>
                <th className="px-6 py-3.5 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60">
              {games.map((game) => (
                <tr key={game.id} className="hover:bg-slate-800/30 transition">
                  <td className="px-6 py-4 font-mono text-xs text-slate-400">{game.id.substring(0, 8)}...</td>
                  <td className="px-6 py-4 font-semibold text-white">{game.bot_name}</td>
                  <td className="px-6 py-4">
                    <span className={`text-xs px-2.5 py-1 rounded-full font-semibold border ${
                      game.phase === 'NIGHT'
                        ? 'bg-purple-950 text-purple-300 border-purple-800'
                        : game.phase === 'VOTING'
                        ? 'bg-amber-950 text-amber-300 border-amber-800'
                        : game.phase === 'FINISHED'
                        ? 'bg-emerald-950 text-emerald-300 border-emerald-800'
                        : 'bg-slate-800 text-slate-300 border-slate-700'
                    }`}>
                      {game.phase}
                    </span>
                  </td>
                  <td className="px-6 py-4 font-mono">#{game.round_number}</td>
                  <td className="px-6 py-4 flex items-center gap-1.5">
                    <Users className="w-4 h-4 text-emerald-400" />
                    <span>{game.alive_players_count} / {game.players_count}</span>
                  </td>
                  <td className="px-6 py-4 text-xs text-slate-400">
                    {new Date(game.created_at).toLocaleTimeString()}
                  </td>
                  <td className="px-6 py-4 text-right">
                    <Link
                      href={`/games/${game.id}`}
                      className="inline-flex items-center gap-1 px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-medium rounded-lg transition"
                    >
                      <Eye className="w-3.5 h-3.5" /> Monitor
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
