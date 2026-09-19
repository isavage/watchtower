import { FormEvent, useState } from "react";
import { useAuth } from "../lib/auth";

export function Login() {
  const { login } = useAuth();
  const [username, setUsername] = useState("admin");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await login(username, password);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center px-4">
      <div className="w-full max-w-sm">
        <div className="mb-8 flex flex-col items-center text-center">
          <Logo />
          <h1 className="mt-4 text-xl font-semibold text-ink-900">Watchtower</h1>
          <p className="mt-1 text-sm text-ink-500">Sign in to your server monitor</p>
        </div>

        <form onSubmit={onSubmit} className="card space-y-4 p-6">
          <div>
            <label className="mb-1.5 block text-xs font-medium text-ink-600">Username</label>
            <input
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              autoComplete="username"
              className="w-full rounded-xl border border-ink-200 bg-ink-50 px-3.5 py-2.5 text-sm outline-none transition focus:border-ink-400 focus:bg-white focus:ring-2 focus:ring-ink-900/5"
            />
          </div>
          <div>
            <label className="mb-1.5 block text-xs font-medium text-ink-600">Password</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="current-password"
              className="w-full rounded-xl border border-ink-200 bg-ink-50 px-3.5 py-2.5 text-sm outline-none transition focus:border-ink-400 focus:bg-white focus:ring-2 focus:ring-ink-900/5"
            />
          </div>

          {error && (
            <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-600">{error}</p>
          )}

          <button
            type="submit"
            disabled={busy}
            className="w-full rounded-xl bg-ink-900 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-ink-800 disabled:opacity-60"
          >
            {busy ? "Signing in…" : "Sign in"}
          </button>
        </form>
      </div>
    </div>
  );
}

function Logo() {
  return (
    <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-ink-900 text-white shadow-card">
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M3 12h4l2 6 4-14 2 8h6" />
      </svg>
    </div>
  );
}
