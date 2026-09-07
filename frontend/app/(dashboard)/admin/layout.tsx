'use client';

import React from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
  LayoutDashboard, Bot, Gamepad2, Users, CreditCard, ScrollText, ShieldAlert
} from 'lucide-react';

const adminTabs = [
  { name: 'Overview', href: '/admin', icon: LayoutDashboard },
  { name: 'Bots Control', href: '/admin/bots', icon: Bot },
  { name: 'Games Monitor', href: '/admin/games', icon: Gamepad2 },
  { name: 'User Management', href: '/admin/users', icon: Users },
  { name: 'Payment Orders', href: '/admin/payments', icon: CreditCard },
  { name: 'Audit Logs', href: '/admin/audit-logs', icon: ScrollText },
];

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between pb-4 border-b border-slate-800 gap-4">
        <div className="flex items-center gap-3">
          <div className="p-2.5 bg-rose-500/10 border border-rose-500/20 rounded-xl text-rose-400">
            <ShieldAlert className="w-6 h-6" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-white">Admin Control Plane</h1>
            <p className="text-sm text-slate-400">Platform governance, bot operations & virtual economy management</p>
          </div>
        </div>
      </div>

      {/* Tab Navigation */}
      <div className="flex items-center gap-2 overflow-x-auto border-b border-slate-800 pb-2">
        {adminTabs.map((tab) => {
          const isActive = pathname === tab.href;
          const Icon = tab.icon;
          return (
            <Link
              key={tab.name}
              href={tab.href}
              className={`flex items-center gap-2 px-3.5 py-2 rounded-lg text-sm font-medium transition whitespace-nowrap ${
                isActive
                  ? 'bg-rose-500/10 text-rose-400 border border-rose-500/20'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/60'
              }`}
            >
              <Icon className="w-4 h-4" />
              <span>{tab.name}</span>
            </Link>
          );
        })}
      </div>

      {children}
    </div>
  );
}
