'use client';

import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { ArrowLeft, Shield, Save, Loader2 } from 'lucide-react';
import { rolesService } from '@/services/configurations.service';
import { RoleAbility } from '@/types';

export default function NewRolePage() {
  const router = useRouter();
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [form, setForm] = useState({
    name: '',
    code: '',
    team: 'CIVILIAN',
    description: '',
    priority: 0,
    ability_type: 'NONE',
    ability_phase: 'NIGHT',
    target_required: true,
    uses_per_game: 0,
  });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.name.trim()) { setError('Role name is required.'); return; }
    if (!form.code.trim()) { setError('Role code is required.'); return; }
    if (!/^[a-z0-9_-]+$/.test(form.code)) {
      setError('Code must be lowercase letters, numbers, hyphens, or underscores.');
      return;
    }

    setSaving(true);
    setError('');
    try {
      const abilities: RoleAbility[] = form.ability_type !== 'NONE' ? [{
        ability_type: form.ability_type as 'KILL' | 'PROTECT' | 'INVESTIGATE',
        phase: form.ability_phase as 'NIGHT' | 'DAY' | 'ANY',
        target_required: form.target_required,
        uses_per_game: form.uses_per_game,
        cooldown_rounds: 0,
        allowed_targets: 'ANY',
      }] : [];

      await rolesService.create({
        name: form.name,
        code: form.code,
        team: form.team,
        description: form.description,
        priority: form.priority,
        abilities,
      });
      router.push('/roles');
    } catch (err: any) {
      const data = err?.response?.data;
      setError(data?.detail || data?.code?.[0] || 'Failed to create role.');
    } finally {
      setSaving(false);
    }
  };

  const f = (key: keyof typeof form) => ({
    value: form[key] as any,
    onChange: (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) =>
      setForm(prev => ({ ...prev, [key]: e.target.type === 'number' ? Number(e.target.value) : e.target.value })),
  });

  const autoCode = () => {
    if (!form.code) {
      setForm(prev => ({ ...prev, code: form.name.toLowerCase().replace(/\s+/g, '_').replace(/[^a-z0-9_-]/g, '') }));
    }
  };

  return (
    <div className="max-w-xl space-y-6">
      <Link href="/roles" className="flex items-center gap-1 text-slate-400 hover:text-white text-sm transition">
        <ArrowLeft className="w-4 h-4" /> Back to Roles
      </Link>

      <div className="flex items-center gap-3">
        <Shield className="w-6 h-6 text-emerald-400" />
        <div>
          <h1 className="text-xl font-bold text-white">Create Custom Role</h1>
          <p className="text-slate-400 text-sm">Define a new role for your game configurations</p>
        </div>
      </div>

      <form onSubmit={handleSubmit} className="space-y-5">
        <section className="bg-slate-800/50 border border-slate-700 rounded-xl p-5 space-y-4">
          <h2 className="text-white font-semibold">Role Identity</h2>

          <div>
            <label className="text-xs text-slate-400 mb-1 block">Role Name *</label>
            <input {...f('name')} type="text" onBlur={autoCode} placeholder="e.g. Vigilante"
              className="w-full bg-slate-900 border border-slate-600 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-emerald-500" />
          </div>

          <div>
            <label className="text-xs text-slate-400 mb-1 block">Code *</label>
            <input {...f('code')} type="text" placeholder="e.g. vigilante"
              className="w-full bg-slate-900 border border-slate-600 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-emerald-500 font-mono" />
            <p className="text-xs text-slate-600 mt-1">Lowercase letters, numbers, hyphens, underscores only.</p>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="text-xs text-slate-400 mb-1 block">Faction / Team</label>
              <select {...f('team')} className="w-full bg-slate-900 border border-slate-600 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-emerald-500">
                <option value="CIVILIAN">Civilian</option>
                <option value="MAFIA">Mafia</option>
                <option value="NEUTRAL">Neutral</option>
              </select>
            </div>
            <div>
              <label className="text-xs text-slate-400 mb-1 block">Priority</label>
              <input {...f('priority')} type="number" min={0}
                className="w-full bg-slate-900 border border-slate-600 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-emerald-500" />
            </div>
          </div>

          <div>
            <label className="text-xs text-slate-400 mb-1 block">Description</label>
            <textarea {...f('description')} rows={2} placeholder="What does this role do?"
              className="w-full bg-slate-900 border border-slate-600 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-emerald-500 resize-none" />
          </div>
        </section>

        <section className="bg-slate-800/50 border border-slate-700 rounded-xl p-5 space-y-4">
          <h2 className="text-white font-semibold">Night Ability</h2>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="text-xs text-slate-400 mb-1 block">Ability Type</label>
              <select {...f('ability_type')} className="w-full bg-slate-900 border border-slate-600 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-emerald-500">
                <option value="NONE">None (Passive)</option>
                <option value="KILL">Kill</option>
                <option value="PROTECT">Protect</option>
                <option value="INVESTIGATE">Investigate</option>
              </select>
            </div>
            <div>
              <label className="text-xs text-slate-400 mb-1 block">Phase</label>
              <select {...f('ability_phase')} className="w-full bg-slate-900 border border-slate-600 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-emerald-500"
                disabled={form.ability_type === 'NONE'}>
                <option value="NIGHT">Night</option>
                <option value="DAY">Day</option>
                <option value="ANY">Any</option>
              </select>
            </div>
          </div>

          {form.ability_type !== 'NONE' && (
            <div>
              <label className="text-xs text-slate-400 mb-1 block">Uses per game (0 = unlimited)</label>
              <input {...f('uses_per_game')} type="number" min={0}
                className="w-full bg-slate-900 border border-slate-600 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-emerald-500" />
            </div>
          )}
        </section>

        {error && (
          <div className="p-3 rounded-lg bg-red-900/30 border border-red-500/30 text-red-400 text-sm">{error}</div>
        )}

        <button
          type="submit"
          disabled={saving}
          className="w-full flex items-center justify-center gap-2 py-3 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white font-medium rounded-xl transition"
        >
          {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
          {saving ? 'Creating...' : 'Create Role'}
        </button>
      </form>
    </div>
  );
}
