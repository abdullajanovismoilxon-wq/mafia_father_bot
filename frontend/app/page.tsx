import Link from 'next/link';

export default function Home() {
  return (
    <div className="min-h-screen flex flex-col justify-center items-center px-4 bg-slate-950 text-white">
      <div className="text-center max-w-2xl">
        <h1 className="text-5xl font-extrabold tracking-tight text-emerald-400 mb-4">
          MAFIA BOT FATHER
        </h1>
        <p className="text-xl text-slate-300 mb-8">
          The ultimate SaaS platform for creating, configuring, deploying, and managing multiple Telegram Mafia game bots.
        </p>
        <div className="flex justify-center gap-4">
          <Link
            href="/login"
            className="px-6 py-3 bg-emerald-600 hover:bg-emerald-500 rounded-lg font-semibold transition"
          >
            Login
          </Link>
          <Link
            href="/register"
            className="px-6 py-3 bg-slate-800 hover:bg-slate-700 border border-slate-700 rounded-lg font-semibold transition"
          >
            Register
          </Link>
        </div>
      </div>
    </div>
  );
}
