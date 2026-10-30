"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { createContext, useCallback, useContext, useEffect, useState } from "react";

import { clearSession, getSession, type AdminSession } from "@/services/adminApi";

type ToastKind = "success" | "error";
interface Toast {
  id: number;
  kind: ToastKind;
  message: string;
}

interface AdminContextValue {
  session: AdminSession;
  notify: (message: string, kind?: ToastKind) => void;
}

const AdminContext = createContext<AdminContextValue | null>(null);

export function useAdmin(): AdminContextValue {
  const ctx = useContext(AdminContext);
  if (!ctx) throw new Error("useAdmin must be used inside the admin area");
  return ctx;
}

const NAV = [
  { href: "/admin", label: "Dashboard" },
  { href: "/admin/movies", label: "Movies" },
  { href: "/admin/movies/new", label: "Add movie" },
];

export default function AdminShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const isLogin = pathname === "/admin/login";
  const [session, setSession] = useState<AdminSession | null>(null);
  const [checked, setChecked] = useState(false);
  const [toasts, setToasts] = useState<Toast[]>([]);

  useEffect(() => {
    const current = getSession();
    setSession(current);
    setChecked(true);
    if (!current && !isLogin) router.replace("/admin/login");
  }, [isLogin, pathname, router]);

  const notify = useCallback((message: string, kind: ToastKind = "success") => {
    const id = Date.now() + Math.random();
    setToasts((t) => [...t, { id, kind, message }]);
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), kind === "error" ? 8000 : 4000);
  }, []);

  const logout = () => {
    clearSession();
    router.replace("/admin/login");
  };

  if (isLogin) return <div className="min-h-screen bg-ink">{children}</div>;
  if (!checked || !session) {
    return <div className="grid min-h-screen place-items-center text-muted">Checking sign-in…</div>;
  }

  return (
    <AdminContext.Provider value={{ session, notify }}>
      <div className="min-h-screen bg-ink">
        <header className="border-b border-line bg-panel">
          <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-6 gap-y-2 px-4 py-3">
            <Link href="/admin" className="font-extrabold">
              Free<span className="text-accent">Reel</span> <span className="text-sm font-medium text-muted">Admin</span>
            </Link>
            <nav aria-label="Admin" className="flex gap-1">
              {NAV.map((item) => {
                const active = item.href === "/admin" ? pathname === "/admin" : pathname === item.href;
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    className={`rounded-md px-3 py-1.5 text-sm ${active ? "bg-panel-2 text-white" : "text-muted hover:text-white"}`}
                  >
                    {item.label}
                  </Link>
                );
              })}
            </nav>
            <div className="ml-auto flex items-center gap-3 text-sm">
              <span data-testid="admin-user">
                {session.user.username}{" "}
                <span className="rounded bg-panel-2 px-1.5 py-0.5 text-xs text-muted">{session.user.role}</span>
              </span>
              <Link href="/" className="text-muted hover:text-white" target="_blank">
                View site ↗
              </Link>
              <button type="button" onClick={logout} className="rounded-md border border-line px-3 py-1.5 hover:border-accent">
                Log out
              </button>
            </div>
          </div>
        </header>
        <main className="mx-auto max-w-6xl px-4 py-8">{children}</main>

        <div className="fixed bottom-4 right-4 z-50 flex w-80 max-w-[calc(100vw-2rem)] flex-col gap-2" aria-live="polite">
          {toasts.map((t) => (
            <div
              key={t.id}
              role={t.kind === "error" ? "alert" : "status"}
              className={`rounded-lg px-4 py-3 text-sm shadow-lg ring-1 ${
                t.kind === "error" ? "bg-red-950 text-red-100 ring-red-800" : "bg-emerald-950 text-emerald-100 ring-emerald-800"
              }`}
            >
              {t.message}
            </div>
          ))}
        </div>
      </div>
    </AdminContext.Provider>
  );
}
