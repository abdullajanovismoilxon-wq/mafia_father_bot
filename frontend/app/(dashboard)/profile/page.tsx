'use client';

import React, { useEffect, useState } from 'react';
import { profileService, ProfileData, LeaderboardEntry } from '@/services/profile.service';
import { economyService, MarketplaceCatalog, MarketplaceItemData } from '@/services/economy.service';
import {
  User, Shield, Trophy, Gem, DollarSign, Coins, Crown, Send,
  Flame, Award, Target, HeartHandshake, Eye, CheckCircle2,
  Lock, RefreshCw, AlertTriangle, ArrowRight
} from 'lucide-react';

export default function ProfileAndEconomyPage() {
  const [data, setData] = useState<ProfileData | null>(null);
  const [catalog, setCatalog] = useState<MarketplaceCatalog | null>(null);
  const [leaderboard, setLeaderboard] = useState<LeaderboardEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  // Transfer Modal State
  const [transferModalOpen, setTransferModalOpen] = useState(false);
  const [transferCurrency, setTransferCurrency] = useState<'MONEY' | 'DIAMONDS' | 'COINS'>('DIAMONDS');
  const [transferRecipient, setTransferRecipient] = useState('');
  const [transferAmount, setTransferAmount] = useState<number>(5);
  const [transferMemo, setTransferMemo] = useState('');
  const [transferLoading, setTransferLoading] = useState(false);

  const fetchData = async () => {
    try {
      setLoading(true);
      setError('');
      const [profileData, catalogData, leaders] = await Promise.all([
        profileService.getProfile(),
        economyService.getCatalog(),
        profileService.getLeaderboard('wins', 10),
      ]);
      setData(profileData);
      setCatalog(catalogData);
      setLeaderboard(leaders);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to load profile data.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const handleTransferSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      setTransferLoading(true);
      const isNumeric = /^\d+$/.test(transferRecipient.trim());
      await economyService.transfer({
        currency: transferCurrency,
        amount: transferAmount,
        recipient_telegram_id: isNumeric ? parseInt(transferRecipient.trim()) : undefined,
        recipient_email: !isNumeric ? transferRecipient.trim() : undefined,
        description: transferMemo || 'P2P Transfer',
      });
      alert('Transfer completed successfully!');
      setTransferModalOpen(false);
      await fetchData();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Transfer failed.');
    } finally {
      setTransferLoading(false);
    }
  };

  const handleBuyDiamonds = async (item: MarketplaceItemData) => {
    if (!data) return;
    const confirmBuy = confirm(`Purchase ${item.name} for $${item.price_usd}?`);
    if (!confirmBuy) return;

    try {
      if (parseFloat(data.wallet.money) >= parseFloat(item.price_usd)) {
        await economyService.purchaseItem(item.code, 'MONEY');
        alert(`Successfully purchased ${item.name}!`);
      } else {
        const order = await economyService.createPaymentOrder(item.diamond_amount);
        alert(`Payment order #${order.order_id} created! Please contact @mafiabotfather_support to complete Payme/Click checkout.`);
      }
      await fetchData();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Purchase failed.');
    }
  };

  const handleBuyVip = async (item: MarketplaceItemData) => {
    const confirmBuy = confirm(`Activate ${item.name} for ${item.price_diamonds} 💎?`);
    if (!confirmBuy) return;

    try {
      await economyService.purchaseItem(item.code, 'DIAMONDS');
      alert(`🎉 VIP Subscription Activated!`);
      await fetchData();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to activate VIP. Check diamond balance.');
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <RefreshCw className="w-8 h-8 animate-spin text-emerald-500" />
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="p-6 bg-rose-500/10 border border-rose-500/20 rounded-2xl text-rose-400 flex items-center gap-3">
        <AlertTriangle className="w-6 h-6 flex-shrink-0" />
        <p>{error || 'Profile could not be loaded.'}</p>
      </div>
    );
  }

  const { profile, stats, wallet, achievements } = data;

  return (
    <div className="space-y-8">
      {/* Profile Header & Virtual Wallet */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Profile Card */}
        <div className="lg:col-span-1 p-6 bg-slate-900 border border-slate-800 rounded-3xl space-y-4">
          <div className="flex items-center gap-4">
            <div className="w-16 h-16 rounded-2xl bg-gradient-to-tr from-emerald-600 to-sky-500 flex items-center justify-center text-white text-2xl font-bold shadow-lg shadow-emerald-500/10">
              {profile.full_name ? profile.full_name[0].toUpperCase() : 'M'}
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-xl font-bold text-white">{profile.full_name || 'Mafia Player'}</h2>
                {profile.is_vip && (
                  <span className="px-2 py-0.5 bg-amber-500/10 border border-amber-500/20 text-amber-400 rounded-full text-[11px] font-bold flex items-center gap-1">
                    <Crown className="w-3 h-3" /> VIP {profile.vip_badge}
                  </span>
                )}
              </div>
              <p className="text-xs text-slate-400">@{profile.username || 'unknown'}</p>
              {profile.telegram_id && (
                <p className="text-[11px] font-mono text-slate-500 mt-0.5">TG ID: {profile.telegram_id}</p>
              )}
            </div>
          </div>

          <div className="pt-2">
            <div className="flex items-center justify-between text-xs text-slate-400 mb-1.5">
              <span>Player Level {profile.level}</span>
              <span className="text-emerald-400 font-semibold">{profile.experience_points} XP</span>
            </div>
            <div className="w-full bg-slate-950 rounded-full h-2 overflow-hidden border border-slate-800">
              <div
                className="bg-emerald-500 h-2 rounded-full transition-all duration-500"
                style={{ width: `${Math.min(100, (profile.experience_points % 500) / 5)}%` }}
              />
            </div>
          </div>
        </div>

        {/* Virtual Wallet & Balance */}
        <div className="lg:col-span-2 p-6 bg-slate-900 border border-slate-800 rounded-3xl flex flex-col justify-between space-y-6">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
            <div>
              <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">Virtual Wallet</span>
              <h3 className="text-xl font-bold text-white">Player Balances & Currency</h3>
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={() => setTransferModalOpen(true)}
                className="flex items-center gap-2 px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold rounded-xl transition shadow-lg shadow-emerald-600/20"
              >
                <Send className="w-3.5 h-3.5" />
                Transfer Funds
              </button>
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            {/* Money USD / UZS */}
            <div className="p-4 bg-slate-950/60 border border-slate-800 rounded-2xl">
              <div className="flex items-center justify-between text-slate-400 mb-2">
                <span className="text-xs font-medium">USD Balance</span>
                <DollarSign className="w-4 h-4 text-emerald-400" />
              </div>
              <div className="text-2xl font-bold text-emerald-400">${wallet.money}</div>
              <div className="text-[11px] text-slate-500 mt-1">≈ {wallet.money_uzs.toLocaleString()} so'm</div>
            </div>

            {/* Diamonds */}
            <div className="p-4 bg-slate-950/60 border border-slate-800 rounded-2xl">
              <div className="flex items-center justify-between text-slate-400 mb-2">
                <span className="text-xs font-medium">Diamonds</span>
                <Gem className="w-4 h-4 text-sky-400" />
              </div>
              <div className="text-2xl font-bold text-sky-400">{wallet.diamonds} 💎</div>
              <div className="text-[11px] text-slate-500 mt-1">Premium virtual currency</div>
            </div>

            {/* Coins */}
            <div className="p-4 bg-slate-950/60 border border-slate-800 rounded-2xl">
              <div className="flex items-center justify-between text-slate-400 mb-2">
                <span className="text-xs font-medium">Game Coins</span>
                <Coins className="w-4 h-4 text-amber-400" />
              </div>
              <div className="text-2xl font-bold text-amber-400">{wallet.coins.toLocaleString()} 🪙</div>
              <div className="text-[11px] text-slate-500 mt-1">Earned by winning games</div>
            </div>
          </div>
        </div>
      </div>

      {/* Diamond Packages Marketplace (Inspired by Reference Design) */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-lg font-bold text-white flex items-center gap-2">
              <Gem className="w-5 h-5 text-sky-400" />
              Diamond Store (Olmoslar Do'koni)
            </h3>
            <p className="text-xs text-slate-400">Official diamond packages with instant Payme / Click / Card conversion</p>
          </div>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-4 gap-4">
          {catalog?.items.filter(i => i.item_type === 'DIAMONDS_PACK').map((item) => (
            <div
              key={item.id}
              className={`p-5 bg-slate-900 border rounded-2xl flex flex-col justify-between transition hover:border-sky-500/50 ${
                item.is_popular ? 'border-sky-500/40 bg-sky-950/10' : 'border-slate-800'
              }`}
            >
              <div className="text-center space-y-2">
                {item.is_popular && (
                  <span className="inline-block px-2 py-0.5 bg-sky-500/20 text-sky-400 rounded-full text-[10px] font-bold uppercase tracking-wider mb-1">
                    Popular
                  </span>
                )}
                <div className="text-3xl font-extrabold text-white flex items-center justify-center gap-1.5">
                  <Gem className="w-7 h-7 text-sky-400" />
                  <span>{item.diamond_amount}</span>
                </div>
                <div className="text-xs font-semibold text-slate-400">{item.name}</div>
              </div>

              <div className="pt-4 space-y-2">
                <div className="text-center">
                  <div className="text-base font-bold text-emerald-400">${item.price_usd}</div>
                  <div className="text-[11px] text-slate-500">≈ {item.price_uzs.toLocaleString()} so'm</div>
                </div>
                <button
                  onClick={() => handleBuyDiamonds(item)}
                  className="w-full py-2 bg-sky-600 hover:bg-sky-500 text-white text-xs font-bold rounded-xl transition shadow-lg shadow-sky-600/20"
                >
                  Buy Pack
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Gameplay Statistics & Metrics */}
      <div className="space-y-4">
        <h3 className="text-lg font-bold text-white flex items-center gap-2">
          <Trophy className="w-5 h-5 text-amber-400" />
          Mafia Gameplay Statistics
        </h3>

        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-4">
          <div className="p-4 bg-slate-900 border border-slate-800 rounded-2xl text-center">
            <div className="text-xs text-slate-500 mb-1">Games Played</div>
            <div className="text-2xl font-bold text-white">{stats.games_played}</div>
          </div>
          <div className="p-4 bg-slate-900 border border-slate-800 rounded-2xl text-center">
            <div className="text-xs text-slate-500 mb-1">Victories</div>
            <div className="text-2xl font-bold text-emerald-400">{stats.games_won}</div>
            <div className="text-[11px] text-slate-500 mt-0.5">{stats.win_rate}% Win Rate</div>
          </div>
          <div className="p-4 bg-slate-900 border border-slate-800 rounded-2xl text-center">
            <div className="text-xs text-slate-500 mb-1">Win Streak</div>
            <div className="text-2xl font-bold text-amber-400 flex items-center justify-center gap-1">
              <Flame className="w-5 h-5" /> {stats.current_win_streak}
            </div>
            <div className="text-[11px] text-slate-500 mt-0.5">Best: {stats.best_win_streak}</div>
          </div>
          <div className="p-4 bg-slate-900 border border-slate-800 rounded-2xl text-center">
            <div className="text-xs text-slate-500 mb-1">Doctor Saves</div>
            <div className="text-2xl font-bold text-sky-400 flex items-center justify-center gap-1">
              <HeartHandshake className="w-5 h-5" /> {stats.doctor_saves}
            </div>
          </div>
          <div className="p-4 bg-slate-900 border border-slate-800 rounded-2xl text-center">
            <div className="text-xs text-slate-500 mb-1">Detective Intel</div>
            <div className="text-2xl font-bold text-indigo-400 flex items-center justify-center gap-1">
              <Eye className="w-5 h-5" /> {stats.detective_investigations}
            </div>
          </div>
          <div className="p-4 bg-slate-900 border border-slate-800 rounded-2xl text-center">
            <div className="text-xs text-slate-500 mb-1">MVP Awards</div>
            <div className="text-2xl font-bold text-rose-400 flex items-center justify-center gap-1">
              <Award className="w-5 h-5" /> {stats.mvp_count}
            </div>
          </div>
        </div>
      </div>

      {/* Achievements System */}
      <div className="space-y-4">
        <h3 className="text-lg font-bold text-white flex items-center gap-2">
          <Award className="w-5 h-5 text-purple-400" />
          Achievements & Badges
        </h3>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {achievements.map((ach) => (
            <div
              key={ach.id}
              className={`p-4 rounded-2xl border flex items-start gap-3 transition ${
                ach.is_unlocked
                  ? 'bg-slate-900 border-purple-500/30'
                  : 'bg-slate-950/40 border-slate-800 opacity-60'
              }`}
            >
              <div className="text-2xl p-2 bg-slate-800/80 rounded-xl">
                {ach.badge_icon || '🏆'}
              </div>
              <div className="space-y-1">
                <div className="flex items-center gap-1.5">
                  <h4 className="text-sm font-bold text-white">{ach.title}</h4>
                  {ach.is_unlocked ? (
                    <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                  ) : (
                    <Lock className="w-3.5 h-3.5 text-slate-600" />
                  )}
                </div>
                <p className="text-xs text-slate-400 leading-snug">{ach.description}</p>
                <div className="text-[11px] font-semibold text-sky-400 pt-1">
                  +{ach.diamond_reward} 💎  +{ach.coin_reward} 🪙
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Global Leaderboard */}
      <div className="space-y-4">
        <h3 className="text-lg font-bold text-white flex items-center gap-2">
          <Trophy className="w-5 h-5 text-amber-400" />
          Global Player Leaderboard
        </h3>

        <div className="bg-slate-900 border border-slate-800 rounded-2xl overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm text-slate-300">
              <thead className="bg-slate-950/60 text-xs uppercase tracking-wider text-slate-400 border-b border-slate-800">
                <tr>
                  <th className="py-3 px-4">Rank</th>
                  <th className="py-3 px-4">Player</th>
                  <th className="py-3 px-4">Wins</th>
                  <th className="py-3 px-4">Win Rate</th>
                  <th className="py-3 px-4">Streak</th>
                  <th className="py-3 px-4 text-right">Diamonds</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {leaderboard.map((player) => (
                  <tr key={player.id} className="hover:bg-slate-800/30 transition">
                    <td className="py-3 px-4 font-bold text-amber-400">#{player.rank}</td>
                    <td className="py-3 px-4 font-medium text-white">
                      {player.name}
                      {player.telegram_username && (
                        <span className="text-xs text-slate-500 ml-2">@{player.telegram_username}</span>
                      )}
                    </td>
                    <td className="py-3 px-4 font-semibold text-emerald-400">{player.games_won}</td>
                    <td className="py-3 px-4 text-slate-300">{player.win_rate}%</td>
                    <td className="py-3 px-4 text-amber-400">{player.win_streak} 🔥</td>
                    <td className="py-3 px-4 text-right font-semibold text-sky-400">{player.diamonds} 💎</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {/* P2P Transfer Modal */}
      {transferModalOpen && (
        <div className="fixed inset-0 z-50 bg-black/70 flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-md w-full p-6 space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-lg font-bold text-white">P2P Fund Transfer</h3>
              <button
                onClick={() => setTransferModalOpen(false)}
                className="text-slate-500 hover:text-slate-300 text-sm"
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleTransferSubmit} className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-slate-400 mb-1">Currency</label>
                <select
                  value={transferCurrency}
                  onChange={(e) => setTransferCurrency(e.target.value as any)}
                  className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-sm text-white focus:outline-none focus:border-emerald-500"
                >
                  <option value="DIAMONDS">💎 Diamonds</option>
                  <option value="MONEY">💵 Money (USD)</option>
                  <option value="COINS">🪙 Coins</option>
                </select>
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-400 mb-1">
                  Recipient (Telegram ID or User Email)
                </label>
                <input
                  type="text"
                  placeholder="e.g. 12345678 or friend@example.com"
                  value={transferRecipient}
                  onChange={(e) => setTransferRecipient(e.target.value)}
                  required
                  className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-sm text-white focus:outline-none focus:border-emerald-500"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-400 mb-1">Amount</label>
                <input
                  type="number"
                  step="any"
                  min="1"
                  value={transferAmount}
                  onChange={(e) => setTransferAmount(parseFloat(e.target.value))}
                  required
                  className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-sm text-white focus:outline-none focus:border-emerald-500"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-400 mb-1">Memo / Description</label>
                <input
                  type="text"
                  placeholder="Gift / Tournament Reward"
                  value={transferMemo}
                  onChange={(e) => setTransferMemo(e.target.value)}
                  className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-sm text-white focus:outline-none focus:border-emerald-500"
                />
              </div>

              <div className="flex justify-end gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => setTransferModalOpen(false)}
                  className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-medium rounded-lg transition"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={transferLoading}
                  className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold rounded-lg transition disabled:opacity-50"
                >
                  {transferLoading ? 'Transferring...' : 'Send Transfer'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
