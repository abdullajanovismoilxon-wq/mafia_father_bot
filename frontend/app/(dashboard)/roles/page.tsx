'use client';

import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import { Shield, Plus, Trash2, Loader2 } from 'lucide-react';
import { Role } from '@/types';
import { rolesService } from '@/services/configurations.service';

const TEAM_BADGE: Record<string, string> = {
  CIVILIAN: 'bg-blue-900/30 text-blue-400',
  MAFIA: 'bg-red-900/30 text-red-400',
  NEUTRAL: 'bg-yellow-900/30 text-yellow-400',
};

export default function RolesPage() {
  const [roles, setRoles] = useState<Role[]>([]);
  const [loading, setLoading] = useState(true);
  const [deleting, setDeleting] = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    try {
      const data = await rolesService.list();
      setRoles(Array.isArray(data) ? data : []);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const handleDelete = async (role: Role) => {
    if (!role.is_mine || role.is_system) return;
    if (!confirm(`Deactivate role "${role.name}"?`)) return;
    setDeleting(role.id);
    try {
      await rolesService.delete(role.id);
      await load();
    } finally {
      setDeleting(null);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Shield className="w-6 h-6 text-emerald-400" />
          <div>
            <h1 className="text-xl font-bold text-white">Roles</h1>
            <p className="text-slate-400 text-sm">System roles and your custom roles</p>
          </div>
        </div>
        <Link
          href="/roles/new"
          className="flex items-center gap-2 px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white text-sm font-medium rounded-lg transition"
        >
          <Plus className="w-4 h-4" />
          Create Role
        </Link>
      </div>

      {loading ? (
        <div className="flex justify-center py-12">
          <Loader2 className="w-5 h-5 animate-spin text-slate-400" />
        </div>
      ) : (
        <div className="overflow-x-auto rounded-xl border border-slate-700">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-700 bg-slate-800/80">
                <th className="px-4 py-3 text-left text-slate-400 font-medium">Role</th>
                <th className="px-4 py-3 text-left text-slate-400 font-medium">Code</th>
                <th className="px-4 py-3 text-left text-slate-400 font-medium">Team</th>
                <th className="px-4 py-3 text-left text-slate-400 font-medium">Abilities</th>
                <th className="px-4 py-3 text-left text-slate-400 font-medium">Type</th>
                <th className="px-4 py-3 text-left text-slate-400 font-medium">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-700">
              {roles.map((role) => (
                <tr key={role.id} className="bg-slate-800/30 hover:bg-slate-800/60 transition">
                  <td className="px-4 py-3">
                    <span className="text-white font-medium">{role.name}</span>
                    {role.description && (
                      <p className="text-slate-500 text-xs truncate max-w-[180px]">{role.description}</p>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    <code className="text-xs bg-slate-700 px-1.5 py-0.5 rounded text-slate-300">{role.code}</code>
                  </td>
                  <td className="px-4 py-3">
                    <span className={`text-xs px-2 py-0.5 rounded ${TEAM_BADGE[role.team] || 'bg-slate-700 text-slate-300'}`}>
                      {role.team}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    {role.abilities && role.abilities.length > 0 ? (
                      <div className="flex gap-1 flex-wrap">
                        {role.abilities.map((a, i) => (
                          <span key={i} className="text-xs bg-slate-700 px-1.5 py-0.5 rounded text-slate-300">
                            {a.ability_type}
                          </span>
                        ))}
                      </div>
                    ) : (
                      <span className="text-slate-600 text-xs">—</span>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    {role.is_system ? (
                      <span className="text-xs text-slate-500">⚙️ System</span>
                    ) : (
                      <span className="text-xs text-emerald-400">👤 Custom</span>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    {!role.is_system && role.is_mine && (
                      <button
                        onClick={() => handleDelete(role)}
                        disabled={deleting === role.id}
                        className="p-1.5 rounded text-red-400 hover:bg-red-900/30 transition"
                        title="Deactivate role"
                      >
                        {deleting === role.id ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Trash2 className="w-3.5 h-3.5" />}
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {roles.length === 0 && (
            <div className="text-center py-12 text-slate-500 text-sm">No roles found.</div>
          )}
        </div>
      )}
    </div>
  );
}
