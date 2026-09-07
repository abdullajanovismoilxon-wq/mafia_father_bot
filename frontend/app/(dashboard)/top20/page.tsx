'use client';

import React, { useEffect, useState } from 'react';
import { apiClient } from '@/lib/api-client';
import { Trophy, Crown, RefreshCw, Award, Target, Flame } from 'lucide-react';

interface PlayerRank {
  rank: number;
  full_name: string;
  username: string;
  games_played: number;
  games_won: number;
  win_rate: number;
  mvp_count: number;
}

export default function Top20PlayersPage() {
  const [players, setPlayers] = useState<PlayerRank[]>([]);
  const [groupName, setGroupName] = useState('');
  const [loading, setLoading] = useState(true);

  const fetchTop20 = async () => {
    try {
      setLoading(true);
      const res = await apiClient.get('/stats/group-top20/');
      setPlayers(res.data.top20_players || []);
      setGroupName(res.data.group_name || 'Guruh');
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchTop20();
  }, []);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-white">🏆 Guruhning Top 20 Eng Yaxshi Oʻyinchilari</h2>
          <p className="text-xs text-slate-400"><span className="text-emerald-400 font-medium">{groupName}</span> guruhidagi eng mahoratli va gʻolib mafia oʻyinchilari reytingi</p>
        </div>
        <button
          onClick={fetchTop20}
          className="flex items-center gap-2 px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-medium rounded-xl transition"
        >
          <RefreshCw className="w-3.5 h-3.5" />
          Yangilash
        </button>
      </div>

      {loading ? (
        <div className="flex items-center justify-center min-h-[200px]">
          <RefreshCw className="w-6 h-6 animate-spin text-amber-400" />
        </div>
      ) : players.length === 0 ? (
        <div className="p-12 text-center bg-slate-900 border border-slate-800 rounded-2xl space-y-3">
          <Trophy className="w-10 h-10 text-slate-600 mx-auto" />
          <h3 className="text-sm font-semibold text-slate-300">Hali oʻyinlar oʻtkazilmagan</h3>
          <p className="text-xs text-slate-500">Guruhda birinchi Mafia oʻyinini boshlang va reytingni shakllantiring!</p>
        </div>
      ) : (
        <div className="bg-slate-900 border border-slate-800 rounded-2xl overflow-hidden shadow-xl">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-950/60 text-slate-400 border-b border-slate-800 uppercase tracking-wider font-semibold">
                <tr>
                  <th className="py-3.5 px-4 text-center w-12">#</th>
                  <th className="py-3.5 px-4">Oʻyinchi</th>
                  <th className="py-3.5 px-4">Oʻtkazilgan Oʻyinlar</th>
                  <th className="py-3.5 px-4">Gʻalabalar</th>
                  <th className="py-3.5 px-4">Gʻalaba Foizi (Win Rate)</th>
                  <th className="py-3.5 px-4 text-right">MVP Unvonlari</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {players.map((p) => (
                  <tr key={p.rank} className="hover:bg-slate-800/40 transition">
                    <td className="py-3 px-4 text-center font-bold">
                      {p.rank === 1 ? (
                        <span className="inline-flex items-center justify-center w-7 h-7 rounded-full bg-amber-500/20 text-amber-400 border border-amber-500/40">
                          🥇
                        </span>
                      ) : p.rank === 2 ? (
                        <span className="inline-flex items-center justify-center w-7 h-7 rounded-full bg-slate-400/20 text-slate-300 border border-slate-400/40">
                          🥈
                        </span>
                      ) : p.rank === 3 ? (
                        <span className="inline-flex items-center justify-center w-7 h-7 rounded-full bg-amber-700/20 text-amber-600 border border-amber-700/40">
                          🥉
                        </span>
                      ) : (
                        <span className="text-slate-500">{p.rank}</span>
                      )}
                    </td>
                    <td className="py-3 px-4">
                      <div className="font-semibold text-white flex items-center gap-2">
                        {p.full_name}
                        {p.rank === 1 && <Crown className="w-3.5 h-3.5 text-amber-400" />}
                      </div>
                      <div className="text-[11px] text-slate-500">@{p.username}</div>
                    </td>
                    <td className="py-3 px-4 text-slate-300 font-medium">{p.games_played} ta</td>
                    <td className="py-3 px-4 text-emerald-400 font-bold">{p.games_won} ta</td>
                    <td className="py-3 px-4">
                      <div className="flex items-center gap-2">
                        <div className="w-16 bg-slate-800 h-2 rounded-full overflow-hidden">
                          <div
                            className="bg-emerald-500 h-full rounded-full"
                            style={{ width: `${Math.min(p.win_rate, 100)}%` }}
                          />
                        </div>
                        <span className="font-bold text-slate-200">{p.win_rate}%</span>
                      </div>
                    </td>
                    <td className="py-3 px-4 text-right">
                      {p.mvp_count > 0 ? (
                        <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-amber-500/10 text-amber-400 border border-amber-500/20">
                          <Flame className="w-3 h-3 text-amber-400" /> {p.mvp_count} MVP
                        </span>
                      ) : (
                        <span className="text-slate-600">-</span>
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
