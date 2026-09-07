'use client';

import React, { useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import { Layers, ArrowLeft, Copy, Edit, Globe, Lock, Loader2, CheckCircle } from 'lucide-react';
import { GameTemplate } from '@/types';
import { templatesService } from '@/services/templates.service';

export default function TemplateDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [template, setTemplate] = useState<GameTemplate | null>(null);
  const [loading, setLoading] = useState(true);
  const [duplicating, setDuplicating] = useState(false);
  const [duplicated, setDuplicated] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    const load = async () => {
      try {
        const data = await templatesService.get(id);
        setTemplate(data);
      } catch {
        setError('Template not found or access denied.');
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [id]);

  const handleDuplicate = async () => {
    if (!template) return;
    setDuplicating(true);
    try {
      const copy = await templatesService.duplicate(template.id);
      setDuplicated(true);
      setTimeout(() => router.push(`/templates/${copy.id}`), 1200);
    } catch {
      setError('Failed to duplicate template.');
    } finally {
      setDuplicating(false);
    }
  };

  if (loading) return (
    <div className="flex items-center gap-2 text-slate-400 text-sm py-20 justify-center">
      <Loader2 className="w-5 h-5 animate-spin" /> Loading...
    </div>
  );

  if (error || !template) return (
    <div className="text-red-400 text-sm py-10 text-center">{error || 'Template not found.'}</div>
  );

  const cfg = template.configuration_data || {};

  return (
    <div className="space-y-6 max-w-3xl">
      {/* Back */}
      <Link href="/templates" className="flex items-center gap-1 text-slate-400 hover:text-white text-sm transition">
        <ArrowLeft className="w-4 h-4" /> Back to Templates
      </Link>

      {/* Header */}
      <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-6">
        <div className="flex items-start justify-between gap-4">
          <div className="flex items-center gap-3">
            <Layers className="w-6 h-6 text-emerald-400 shrink-0" />
            <div>
              <h1 className="text-xl font-bold text-white">{template.name}</h1>
              <p className="text-slate-400 text-sm mt-0.5">{template.description || 'No description'}</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {template.visibility === 'PUBLIC'
              ? <Globe className="w-4 h-4 text-blue-400" />
              : <Lock className="w-4 h-4 text-slate-500" />}
            <span className="text-xs text-slate-400">{template.visibility}</span>
          </div>
        </div>

        <div className="mt-4 grid grid-cols-3 gap-3">
          <div className="bg-slate-900/60 rounded-lg p-3">
            <p className="text-xs text-slate-500 mb-1">Owner</p>
            <p className="text-sm text-white">{template.owner_email}</p>
          </div>
          <div className="bg-slate-900/60 rounded-lg p-3">
            <p className="text-xs text-slate-500 mb-1">Mode</p>
            <p className="text-sm text-white">{template.game_mode}</p>
          </div>
          <div className="bg-slate-900/60 rounded-lg p-3">
            <p className="text-xs text-slate-500 mb-1">Version</p>
            <p className="text-sm text-white">v{template.version}</p>
          </div>
        </div>
      </div>

      {/* Configuration */}
      <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-6">
        <h2 className="text-white font-semibold mb-4">Game Configuration</h2>
        <div className="grid grid-cols-2 gap-3 text-sm">
          {[
            ['Min Players', cfg.minimum_players ?? 4],
            ['Max Players', cfg.maximum_players ?? 20],
            ['Night Duration', `${cfg.night_duration ?? 60}s`],
            ['Discussion Duration', `${cfg.discussion_duration ?? 120}s`],
            ['Voting Duration', `${cfg.voting_duration ?? 60}s`],
            ['Tie Behavior', cfg.tie_behavior ?? 'NO_ELIMINATION'],
            ['Mafia Vote Mode', cfg.mafia_vote_mode ?? 'ANY'],
            ['Reveal on Elimination', cfg.reveal_role_on_elimination ? '✅ Yes' : '❌ No'],
            ['Allow Self Vote', cfg.allow_self_vote ? '✅ Yes' : '❌ No'],
            ['Auto Phase Transition', cfg.automatic_phase_transition ? '✅ Yes' : '❌ No'],
          ].map(([label, value]) => (
            <div key={label as string} className="flex justify-between bg-slate-900/40 rounded-lg px-3 py-2">
              <span className="text-slate-400">{label}</span>
              <span className="text-white font-medium">{value}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Role Distribution */}
      {template.role_distribution_data && template.role_distribution_data.length > 0 && (
        <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-6">
          <h2 className="text-white font-semibold mb-4">Role Distribution</h2>
          <div className="space-y-2">
            {template.role_distribution_data.map((rule, idx) => (
              <div key={idx} className="flex items-center justify-between bg-slate-900/40 rounded-lg px-3 py-2 text-sm">
                <span className="text-white">{rule.role_name || rule.role_code || rule.role}</span>
                <span className="text-slate-400">
                  {rule.distribution_type === 'EXACT' && `${rule.min_count}×`}
                  {rule.distribution_type === 'RANGE' && `${rule.min_count}–${rule.max_count}×`}
                  {rule.distribution_type === 'PERCENTAGE' && `${rule.percentage}%`}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Actions */}
      <div className="flex items-center gap-3">
        {template.is_owned_by_me && (
          <Link
            href={`/templates/new?edit=${template.id}`}
            className="flex items-center gap-2 px-4 py-2 bg-slate-700 hover:bg-slate-600 text-white text-sm rounded-lg transition"
          >
            <Edit className="w-4 h-4" /> Edit
          </Link>
        )}
        <button
          onClick={handleDuplicate}
          disabled={duplicating || duplicated}
          className="flex items-center gap-2 px-4 py-2 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white text-sm rounded-lg transition"
        >
          {duplicated ? <CheckCircle className="w-4 h-4" /> : duplicating ? <Loader2 className="w-4 h-4 animate-spin" /> : <Copy className="w-4 h-4" />}
          {duplicated ? 'Duplicated!' : duplicating ? 'Duplicating...' : 'Duplicate'}
        </button>
      </div>
    </div>
  );
}
