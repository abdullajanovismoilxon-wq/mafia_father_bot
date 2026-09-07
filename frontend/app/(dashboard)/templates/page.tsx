'use client';

import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import { Layers, Plus, Globe, Lock, Copy, ChevronRight, Loader2 } from 'lucide-react';
import { GameTemplate } from '@/types';
import { templatesService } from '@/services/templates.service';

type FilterType = 'all' | 'mine' | 'system' | 'public';

const FILTER_OPTIONS: { value: FilterType; label: string }[] = [
  { value: 'all', label: 'All' },
  { value: 'mine', label: 'My Templates' },
  { value: 'system', label: 'System' },
  { value: 'public', label: 'Public' },
];

const MODE_BADGE: Record<string, string> = {
  CLASSIC: 'bg-blue-900/30 text-blue-400',
  QUICK: 'bg-yellow-900/30 text-yellow-400',
  TOURNAMENT: 'bg-purple-900/30 text-purple-400',
  CUSTOM: 'bg-slate-700 text-slate-300',
};

export default function TemplatesPage() {
  const [templates, setTemplates] = useState<GameTemplate[]>([]);
  const [filter, setFilter] = useState<FilterType>('all');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [duplicating, setDuplicating] = useState<string | null>(null);

  const loadTemplates = async () => {
    setLoading(true);
    setError('');
    try {
      const data = await templatesService.list(filter);
      setTemplates(Array.isArray(data) ? data : []);
    } catch {
      setError('Failed to load templates.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadTemplates(); }, [filter]);

  const handleDuplicate = async (id: string, e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDuplicating(id);
    try {
      await templatesService.duplicate(id);
      await loadTemplates();
    } catch {
      setError('Failed to duplicate template.');
    } finally {
      setDuplicating(null);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Layers className="w-6 h-6 text-emerald-400" />
          <div>
            <h1 className="text-xl font-bold text-white">Game Templates</h1>
            <p className="text-slate-400 text-sm">Reusable game configurations</p>
          </div>
        </div>
        <Link
          href="/templates/new"
          className="flex items-center gap-2 px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white text-sm font-medium rounded-lg transition"
        >
          <Plus className="w-4 h-4" />
          New Template
        </Link>
      </div>

      {/* Filters */}
      <div className="flex gap-2">
        {FILTER_OPTIONS.map((opt) => (
          <button
            key={opt.value}
            onClick={() => setFilter(opt.value)}
            className={`px-3 py-1.5 text-sm rounded-lg font-medium transition ${
              filter === opt.value
                ? 'bg-emerald-600 text-white'
                : 'bg-slate-800 text-slate-300 hover:bg-slate-700'
            }`}
          >
            {opt.label}
          </button>
        ))}
      </div>

      {error && (
        <div className="p-3 rounded-lg bg-red-900/30 border border-red-500/30 text-red-400 text-sm">
          {error}
        </div>
      )}

      {loading ? (
        <div className="flex items-center gap-2 text-slate-400 text-sm py-12 justify-center">
          <Loader2 className="w-4 h-4 animate-spin" />
          Loading templates...
        </div>
      ) : templates.length === 0 ? (
        <div className="text-center py-16 text-slate-500">
          <Layers className="w-10 h-10 mx-auto mb-3 opacity-40" />
          <p className="text-sm">No templates found.</p>
          <Link href="/templates/new" className="text-emerald-400 hover:underline text-sm mt-2 inline-block">
            Create your first template →
          </Link>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {templates.map((tpl) => (
            <div
              key={tpl.id}
              className="group relative bg-slate-800/50 border border-slate-700 rounded-xl p-5 hover:border-emerald-500/40 transition"
            >
              {/* Visibility badge */}
              <div className="flex items-center justify-between mb-3">
                <span className={`inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded ${MODE_BADGE[tpl.game_mode] || MODE_BADGE.CUSTOM}`}>
                  {tpl.game_mode}
                </span>
                <span className="flex items-center gap-1 text-xs text-slate-500">
                  {tpl.visibility === 'PUBLIC' ? <Globe className="w-3 h-3" /> : <Lock className="w-3 h-3" />}
                  {tpl.visibility}
                </span>
              </div>

              <h3 className="text-white font-semibold text-base mb-1 truncate">{tpl.name}</h3>
              <p className="text-slate-400 text-xs mb-3 line-clamp-2">{tpl.description || 'No description'}</p>

              <div className="flex items-center gap-2 text-xs text-slate-500">
                <span className="bg-slate-700 px-1.5 py-0.5 rounded">
                  {tpl.template_type === 'SYSTEM' ? '⚙️ SYSTEM' : `👤 ${tpl.owner_email}`}
                </span>
                <span>v{tpl.version}</span>
              </div>

              {/* Actions */}
              <div className="flex items-center gap-2 mt-4">
                <button
                  onClick={(e) => handleDuplicate(tpl.id, e)}
                  disabled={duplicating === tpl.id}
                  className="flex items-center gap-1 px-3 py-1.5 text-xs bg-slate-700 hover:bg-slate-600 text-slate-300 rounded-lg transition"
                >
                  {duplicating === tpl.id ? <Loader2 className="w-3 h-3 animate-spin" /> : <Copy className="w-3 h-3" />}
                  Duplicate
                </button>
                <Link
                  href={`/templates/${tpl.id}`}
                  className="ml-auto flex items-center gap-1 px-3 py-1.5 text-xs bg-emerald-900/40 hover:bg-emerald-900/60 text-emerald-400 rounded-lg transition"
                >
                  View <ChevronRight className="w-3 h-3" />
                </Link>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
