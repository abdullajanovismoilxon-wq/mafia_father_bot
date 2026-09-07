'use client';

import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { ArrowLeft, Layers, Save, Loader2 } from 'lucide-react';
import { templatesService } from '@/services/templates.service';

const GAME_MODES = ['CLASSIC', 'QUICK', 'CUSTOM', 'TOURNAMENT'];

export default function NewTemplatePage() {
  const router = useRouter();
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [form, setForm] = useState({
    name: '',
    description: '',
    game_mode: 'CLASSIC',
    visibility: 'PRIVATE',
    minimum_players: 4,
    maximum_players: 20,
    night_duration: 60,
    discussion_duration: 120,
    voting_duration: 60,
    tie_behavior: 'NO_ELIMINATION',
    mafia_vote_mode: 'ANY',
    reveal_role_on_elimination: true,
    allow_self_vote: false,
    automatic_phase_transition: true,
    day_discussion_enabled: true,
  });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.name.trim()) { setError('Template name is required.'); return; }
    if (form.minimum_players > form.maximum_players) { setError('Min players cannot exceed max players.'); return; }

    setSaving(true);
    setError('');
    try {
      const { name, description, game_mode, visibility, ...rest } = form;
      const payload = {
        name,
        description,
        game_mode: game_mode as any,
        visibility: visibility as any,
        configuration_data: {
          minimum_players: rest.minimum_players,
          maximum_players: rest.maximum_players,
          night_duration: rest.night_duration,
          discussion_duration: rest.discussion_duration,
          voting_duration: rest.voting_duration,
          tie_behavior: rest.tie_behavior,
          mafia_vote_mode: rest.mafia_vote_mode,
          reveal_role_on_elimination: rest.reveal_role_on_elimination,
          allow_self_vote: rest.allow_self_vote,
          automatic_phase_transition: rest.automatic_phase_transition,
          day_discussion_enabled: rest.day_discussion_enabled,
        },
        role_distribution_data: [],
      };
      const created = await templatesService.create(payload);
      router.push(`/templates/${created.id}`);
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Failed to create template.');
    } finally {
      setSaving(false);
    }
  };

  const field = (key: keyof typeof form) => ({
    value: form[key] as any,
    onChange: (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => {
      const val = e.target.type === 'checkbox' ? (e.target as HTMLInputElement).checked : e.target.value;
      setForm(prev => ({ ...prev, [key]: e.target.type === 'number' ? Number(val) : val }));
    },
  });

  const checkbox = (key: keyof typeof form) => ({
    checked: form[key] as boolean,
    onChange: (e: React.ChangeEvent<HTMLInputElement>) =>
      setForm(prev => ({ ...prev, [key]: e.target.checked })),
  });

  return (
    <div className="max-w-2xl space-y-6">
      <Link href="/templates" className="flex items-center gap-1 text-slate-400 hover:text-white text-sm transition">
        <ArrowLeft className="w-4 h-4" /> Back to Templates
      </Link>

      <div className="flex items-center gap-3">
        <Layers className="w-6 h-6 text-emerald-400" />
        <div>
          <h1 className="text-xl font-bold text-white">New Game Template</h1>
          <p className="text-slate-400 text-sm">Configure and save reusable game rules</p>
        </div>
      </div>

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Basic Info */}
        <section className="bg-slate-800/50 border border-slate-700 rounded-xl p-5 space-y-4">
          <h2 className="text-white font-semibold">Basic Info</h2>

          <div>
            <label className="text-xs text-slate-400 mb-1 block">Template Name *</label>
            <input {...field('name')} type="text" placeholder="e.g. Classic 6-Player"
              className="w-full bg-slate-900 border border-slate-600 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-emerald-500" />
          </div>

          <div>
            <label className="text-xs text-slate-400 mb-1 block">Description</label>
            <textarea {...field('description')} rows={2} placeholder="Optional description..."
              className="w-full bg-slate-900 border border-slate-600 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-emerald-500 resize-none" />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="text-xs text-slate-400 mb-1 block">Game Mode</label>
              <select {...field('game_mode')} className="w-full bg-slate-900 border border-slate-600 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-emerald-500">
                {GAME_MODES.map(m => <option key={m}>{m}</option>)}
              </select>
            </div>
            <div>
              <label className="text-xs text-slate-400 mb-1 block">Visibility</label>
              <select {...field('visibility')} className="w-full bg-slate-900 border border-slate-600 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-emerald-500">
                <option value="PRIVATE">Private</option>
                <option value="PUBLIC">Public</option>
              </select>
            </div>
          </div>
        </section>

        {/* Player Settings */}
        <section className="bg-slate-800/50 border border-slate-700 rounded-xl p-5 space-y-4">
          <h2 className="text-white font-semibold">Player Settings</h2>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="text-xs text-slate-400 mb-1 block">Min Players</label>
              <input {...field('minimum_players')} type="number" min={2} max={50}
                className="w-full bg-slate-900 border border-slate-600 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-emerald-500" />
            </div>
            <div>
              <label className="text-xs text-slate-400 mb-1 block">Max Players</label>
              <input {...field('maximum_players')} type="number" min={2} max={50}
                className="w-full bg-slate-900 border border-slate-600 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-emerald-500" />
            </div>
          </div>
        </section>

        {/* Phase Durations */}
        <section className="bg-slate-800/50 border border-slate-700 rounded-xl p-5 space-y-4">
          <h2 className="text-white font-semibold">Phase Durations (seconds)</h2>
          <div className="grid grid-cols-3 gap-4">
            {(['night_duration', 'discussion_duration', 'voting_duration'] as const).map((key) => (
              <div key={key}>
                <label className="text-xs text-slate-400 mb-1 block">{key.replace('_', ' ').replace('duration', '').trim()}</label>
                <input {...field(key)} type="number" min={10}
                  className="w-full bg-slate-900 border border-slate-600 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-emerald-500" />
              </div>
            ))}
          </div>
        </section>

        {/* Game Rules */}
        <section className="bg-slate-800/50 border border-slate-700 rounded-xl p-5 space-y-4">
          <h2 className="text-white font-semibold">Game Rules</h2>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="text-xs text-slate-400 mb-1 block">Tie Behavior</label>
              <select {...field('tie_behavior')} className="w-full bg-slate-900 border border-slate-600 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-emerald-500">
                <option value="NO_ELIMINATION">No Elimination</option>
                <option value="RANDOM">Random Elimination</option>
              </select>
            </div>
            <div>
              <label className="text-xs text-slate-400 mb-1 block">Mafia Vote Mode</label>
              <select {...field('mafia_vote_mode')} className="w-full bg-slate-900 border border-slate-600 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-emerald-500">
                <option value="ANY">Any Can Choose</option>
                <option value="MAJORITY">Majority Vote</option>
              </select>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            {([
              ['reveal_role_on_elimination', 'Reveal role on elimination'],
              ['allow_self_vote', 'Allow self-vote'],
              ['automatic_phase_transition', 'Auto phase transition'],
              ['day_discussion_enabled', 'Day discussion'],
            ] as [keyof typeof form, string][]).map(([key, label]) => (
              <label key={key} className="flex items-center gap-2 cursor-pointer select-none">
                <input type="checkbox" {...checkbox(key)} className="accent-emerald-500" />
                <span className="text-sm text-slate-300">{label}</span>
              </label>
            ))}
          </div>
        </section>

        {error && (
          <div className="p-3 rounded-lg bg-red-900/30 border border-red-500/30 text-red-400 text-sm">
            {error}
          </div>
        )}

        <button
          type="submit"
          disabled={saving}
          className="w-full flex items-center justify-center gap-2 py-3 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white font-medium rounded-xl transition"
        >
          {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
          {saving ? 'Saving...' : 'Create Template'}
        </button>
      </form>
    </div>
  );
}
