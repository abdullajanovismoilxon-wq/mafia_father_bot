'use client';

import React, { useEffect, useState } from 'react';
import { Bot as BotIcon, Plus, Play, Square, Shield } from 'lucide-react';
import { botsService } from '../../../services/bots.service';
import { Bot } from '../../../types';

export default function BotsPage() {
  const [bots, setBots] = useState<Bot[]>([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);

  // Form states
  const [name, setName] = useState('');
  const [username, setUsername] = useState('');
  const [token, setToken] = useState('8741801900:AAHtCUxO2zvG737po1_2mTOEW_hr8lA657g');
  const [description, setDescription] = useState('');
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState('');

  const fetchBots = () => {
    setLoading(true);
    botsService
      .getBots()
      .then((data) => setBots(data))
      .catch(() => {})
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    fetchBots();
  }, []);

  const handleCreateBot = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setCreating(true);

    try {
      await botsService.createBot({
        name,
        telegram_username: username.replace('@', ''),
        bot_token: token,
        description,
      });
      setShowModal(false);
      setName('');
      setUsername('');
      setDescription('');
      fetchBots();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to create bot.');
    } finally {
      setCreating(false);
    }
  };

  const handleToggleBot = async (bot: Bot) => {
    try {
      if (bot.runtime_status === 'RUNNING') {
        await botsService.stopBot(bot.id);
      } else {
        await botsService.startBot(bot.id);
      }
      fetchBots();
    } catch (err) {
      console.error(err);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-white mb-1">My Bot Fleet</h1>
          <p className="text-slate-400 text-sm">
            Manage your multi-tenant Telegram Mafia game bot instances
          </p>
        </div>
        <button
          onClick={() => setShowModal(true)}
          className="flex items-center gap-2 px-4 py-2.5 bg-emerald-600 hover:bg-emerald-500 text-white font-semibold rounded-lg transition"
        >
          <Plus className="w-4 h-4" />
          <span>Add New Bot</span>
        </button>
      </div>

      {loading ? (
        <div className="p-8 text-center text-slate-400 font-mono text-sm">Loading bot fleet...</div>
      ) : bots.length === 0 ? (
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-12 text-center">
          <BotIcon className="w-12 h-12 text-slate-600 mx-auto mb-3" />
          <h3 className="text-lg font-semibold text-slate-300">No Mafia Bots Registered</h3>
          <p className="text-sm text-slate-500 mt-1 mb-6">
            Get a bot token from Telegram @BotFather and add your first bot instance.
          </p>
          <button
            onClick={() => setShowModal(true)}
            className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white font-medium rounded-lg transition"
          >
            Add First Bot
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {bots.map((bot) => (
            <div key={bot.id} className="bg-slate-900 border border-slate-800 rounded-xl p-6 flex flex-col justify-between">
              <div>
                <div className="flex items-start justify-between mb-3">
                  <div>
                    <h3 className="font-bold text-lg text-white">{bot.name}</h3>
                    <p className="text-sm text-emerald-400">@{bot.telegram_username}</p>
                  </div>
                  <span className={`text-xs px-2.5 py-1 rounded-full font-semibold border ${
                    bot.runtime_status === 'RUNNING'
                      ? 'bg-emerald-950 text-emerald-400 border-emerald-800'
                      : 'bg-slate-800 text-slate-400 border-slate-700'
                  }`}>
                    {bot.runtime_status}
                  </span>
                </div>

                <p className="text-xs text-slate-400 mb-4 line-clamp-2">
                  {bot.description || 'Standard Mafia Game Bot Instance'}
                </p>

                <div className="bg-slate-950 p-3 rounded-lg border border-slate-800/80 mb-4 font-mono text-xs text-slate-400 flex items-center justify-between">
                  <span className="flex items-center gap-1.5">
                    <Shield className="w-3.5 h-3.5 text-emerald-400" />
                    Token Encrypted
                  </span>
                  <span className="text-slate-300">{bot.masked_token}</span>
                </div>
              </div>

              <div className="flex items-center gap-2 pt-4 border-t border-slate-800/80">
                <button
                  onClick={() => handleToggleBot(bot)}
                  className={`flex-1 py-2 px-3 rounded-lg text-xs font-semibold flex items-center justify-center gap-1.5 transition ${
                    bot.runtime_status === 'RUNNING'
                      ? 'bg-rose-950/60 text-rose-300 border border-rose-800/50 hover:bg-rose-900/60'
                      : 'bg-emerald-950/60 text-emerald-300 border border-emerald-800/50 hover:bg-emerald-900/60'
                  }`}
                >
                  {bot.runtime_status === 'RUNNING' ? (
                    <>
                      <Square className="w-3.5 h-3.5 fill-current" /> Stop Bot
                    </>
                  ) : (
                    <>
                      <Play className="w-3.5 h-3.5 fill-current" /> Start Bot
                    </>
                  )}
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Modal for adding a bot */}
      {showModal && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4 z-50">
          <div className="bg-slate-900 border border-slate-800 rounded-xl max-w-md w-full p-6 shadow-2xl">
            <h2 className="text-xl font-bold text-white mb-4">Register New Bot Instance</h2>

            {error && (
              <div className="mb-4 p-3 bg-rose-950/50 border border-rose-800 text-rose-300 text-sm rounded-lg">
                {error}
              </div>
            )}

            <form onSubmit={handleCreateBot} className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1">Bot Name</label>
                <input
                  type="text"
                  required
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="Mafia Boss Bot"
                  className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white text-sm focus:outline-none focus:border-emerald-500"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1">Telegram Username</label>
                <input
                  type="text"
                  required
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder="MyMafiaGame_bot"
                  className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white text-sm focus:outline-none focus:border-emerald-500"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1">Telegram Bot Token (from @BotFather)</label>
                <input
                  type="password"
                  required
                  value={token}
                  onChange={(e) => setToken(e.target.value)}
                  className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white text-sm font-mono focus:outline-none focus:border-emerald-500"
                />
                <p className="text-[11px] text-slate-500 mt-1">
                  🔒 Token is symmetrically encrypted with AES-128 Fernet algorithm before storage.
                </p>
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1">Description (Optional)</label>
                <textarea
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  rows={2}
                  className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white text-sm focus:outline-none focus:border-emerald-500"
                  placeholder="Official mafia bot for group chats..."
                />
              </div>

              <div className="flex justify-end gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => setShowModal(false)}
                  className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 text-sm font-medium rounded-lg transition"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={creating}
                  className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white text-sm font-semibold rounded-lg transition disabled:opacity-50"
                >
                  {creating ? 'Saving...' : 'Register Bot'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
