"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { adminApi, getSession } from "@/services/adminApi";

export default function AdminLoginPage() {
  const router = useRouter();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (getSession()) router.replace("/admin");
    else if (new URLSearchParams(window.location.search).get("expired")) {
      setError("Your session expired. Please sign in again.");
    }
  }, [router]);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await adminApi.login(username.trim(), password);
      router.replace("/admin");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Sign-in failed");
      setBusy(false);
    }
  };

  const field = "mt-1 w-full rounded-md border border-line bg-ink px-3 py-2 focus:border-accent focus:outline-none";

  return (
    <div className="grid min-h-screen place-items-center px-4">
      <form onSubmit={submit} className="w-full max-w-sm rounded-xl bg-panel p-6 ring-1 ring-line" data-testid="admin-login">
        <h1 className="text-xl font-extrabold">
          Free<span className="text-accent">Reel</span> admin
        </h1>
        <p className="mt-1 text-sm text-muted">For site staff only. Visitors don&apos;t need an account.</p>

        <label className="mt-6 block text-sm">
          Username
          <input
            className={field}
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            autoComplete="username"
            required
            maxLength={50}
          />
        </label>
        <label className="mt-4 block text-sm">
          Password
          <input
            className={field}
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="current-password"
            required
          />
        </label>

        {error && (
          <p role="alert" className="mt-4 rounded-md bg-red-950 px-3 py-2 text-sm text-red-100">
            {error}
          </p>
        )}

        <button
          type="submit"
          disabled={busy}
          className="mt-6 w-full rounded-md bg-accent py-2.5 font-semibold text-accent-ink disabled:opacity-60"
        >
          {busy ? "Signing in…" : "Sign in"}
        </button>
      </form>
    </div>
  );
}
