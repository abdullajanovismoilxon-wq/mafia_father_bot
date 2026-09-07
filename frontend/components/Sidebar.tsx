'use client';

import React from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useLanguageStore } from '../store/useLanguageStore';
import { useAuthStore } from '../store/useAuthStore';
import {
  LayoutDashboard, Bot, Gamepad2, Layers, Shield, Trophy,
  CreditCard, UserCheck, ShieldAlert, Award, Users
} from 'lucide-react';

export function Sidebar() {
  const pathname = usePathname();
  const { t } = useLanguageStore();
  const { user } = useAuthStore();

  const isSuperAdmin = user?.role === 'SUPERADMIN' || (user as any)?.is_platform_owner || (user as any)?.is_superadmin;

  const navigation = [
    { key: 'dashboard', name: t('dashboard'), href: '/dashboard', icon: LayoutDashboard },
    { key: 'my_bots', name: t('my_bots'), href: '/bots', icon: Bot },
    { key: 'games', name: t('games'), href: '/games', icon: Gamepad2 },
    { key: 'top20', name: '🏆 Top 20 Oʻyinchilar', href: '/top20', icon: Award },
    { key: 'co_admins', name: '👥 Guruh Adminlari', href: '/co-admins', icon: Users },
    { key: 'templates', name: t('templates'), href: '/templates', icon: Layers },
    { key: 'roles', name: t('roles'), href: '/roles', icon: Shield },
    { key: 'tournaments', name: t('tournaments'), href: '/tournaments', icon: Trophy },
    { key: 'profile_wallet', name: t('profile_wallet'), href: '/profile', icon: UserCheck },
    { key: 'subscription', name: t('subscription'), href: '/billing', icon: CreditCard },
  ];

  if (isSuperAdmin) {
    navigation.push({ key: 'admin_panel', name: t('admin_panel'), href: '/admin', icon: ShieldAlert });
  }

  return (
    <aside className="w-64 border-r border-slate-800 bg-slate-900 min-h-[calc(100vh-4rem)] p-4 flex flex-col justify-between">
      <nav className="space-y-1">
        {navigation.map((item) => {
          const isActive = pathname === item.href || (item.href !== '/dashboard' && pathname.startsWith(item.href));
          const Icon = item.icon;
          return (
            <Link
              key={item.key}
              href={item.href}
              className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition ${
                isActive
                  ? 'bg-emerald-600/10 text-emerald-400 border border-emerald-500/20'
                  : 'text-slate-300 hover:bg-slate-800'
              }`}
            >
              <Icon className="w-4 h-4" />
              <span>{item.name}</span>
            </Link>
          );
        })}
      </nav>
      <div className="pt-4 border-t border-slate-800">
        <div className="px-3 py-2 bg-slate-950/60 rounded-lg border border-slate-800">
          <div className="flex items-center justify-between text-xs text-slate-400">
            <span>{t('system_status')}</span>
            <span className="flex items-center gap-1.5 text-emerald-400">
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
              {t('operational')}
            </span>
          </div>
        </div>
      </div>
    </aside>
  );
}
