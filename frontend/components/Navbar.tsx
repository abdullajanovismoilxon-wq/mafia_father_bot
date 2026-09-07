'use client';

import React from 'react';
import { useAuthStore } from '../store/useAuthStore';
import { useLanguageStore } from '../store/useLanguageStore';
import { LogOut, User as UserIcon, Globe } from 'lucide-react';
import { useRouter } from 'next/navigation';
import { Language } from '../lib/i18n';

export function Navbar() {
  const { user, logout } = useAuthStore();
  const { language, setLanguage, t } = useLanguageStore();
  const router = useRouter();

  const handleLogout = () => {
    logout();
    router.push('/login');
  };

  return (
    <header className="h-16 border-b border-slate-800 bg-slate-900/80 backdrop-blur px-6 flex items-center justify-between sticky top-0 z-10">
      <div className="flex items-center gap-3">
        <h1 className="font-bold text-lg text-emerald-400">MAFIA BOT FATHER</h1>
        <span className="text-xs px-2 py-0.5 rounded bg-emerald-950 text-emerald-400 border border-emerald-800 font-mono">
          {t('control_plane')}
        </span>
      </div>

      <div className="flex items-center gap-4">
        {/* Language Selector Dropdown */}
        <div className="flex items-center gap-1.5 bg-slate-800 border border-slate-700 rounded-lg px-2 py-1 text-xs">
          <Globe className="w-3.5 h-3.5 text-emerald-400" />
          <select
            value={language}
            onChange={(e) => setLanguage(e.target.value as Language)}
            className="bg-transparent text-slate-200 focus:outline-none cursor-pointer"
          >
            <option value="uz" className="bg-slate-900 text-white">🇺🇿 Oʻzbek</option>
            <option value="ru" className="bg-slate-900 text-white">🇷🇺 Русский</option>
            <option value="en" className="bg-slate-900 text-white">🇬🇧 English</option>
          </select>
        </div>

        {user && (
          <div className="flex items-center gap-2 text-sm text-slate-300">
            <UserIcon className="w-4 h-4 text-emerald-400" />
            <span className="hidden sm:inline">{user.email}</span>
          </div>
        )}
        <button
          onClick={handleLogout}
          className="flex items-center gap-1.5 text-sm text-slate-400 hover:text-rose-400 transition"
        >
          <LogOut className="w-4 h-4" />
          <span>{t('logout')}</span>
        </button>
      </div>
    </header>
  );
}
