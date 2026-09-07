import './globals.css';
import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'MAFIA BOT FATHER — SaaS Platform',
  description: 'Platform for creating, configuring, deploying and managing Telegram Mafia game bots',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="bg-slate-900 text-slate-100 min-h-screen">
        {children}
      </body>
    </html>
  );
}
