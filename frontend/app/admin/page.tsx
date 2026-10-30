"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { useAdmin } from "@/components/admin/AdminShell";
import StatusBadge from "@/components/admin/StatusBadge";
import { adminApi, formatBytes, type Analytics } from "@/services/adminApi";

function Stat({ label, value, hint }: { label: string; value: string | number; hint?: string }) {
  return (
    <div className="rounded-xl bg-panel p-4 ring-1 ring-line">
      <p className="text-xs uppercase tracking-wide text-muted">{label}</p>
      <p className="mt-1 text-2xl font-extrabold tabular-nums">{value}</p>
      {hint && <p className="mt-1 text-xs text-muted">{hint}</p>}
    </div>
  );
}

function Panel({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="rounded-xl bg-panel p-4 ring-1 ring-line">
      <h2 className="mb-3 font-bold">{title}</h2>
      {children}
    </section>
  );
}

export default function AdminDashboard() {
  const { notify } = useAdmin();
  const [data, setData] = useState<Analytics | null>(null);

  useEffect(() => {
    adminApi
      .analytics(30)
      .then(setData)
      .catch((err) => notify(err.message, "error"));
  }, [notify]);

  if (!data) return <p className="text-muted">Loading dashboard…</p>;
  const t = data.totals;
  const hours = Math.round(t.watch_seconds / 360) / 10;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-extrabold">Dashboard</h1>
        <Link href="/admin/movies/new" className="rounded-md bg-accent px-4 py-2 text-sm font-semibold text-accent-ink">
          + Add movie
        </Link>
      </div>

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Stat label="Movies" value={t.movies} hint={`${t.movies_by_status.published ?? 0} published`} />
        <Stat label="Total plays" value={t.views} hint={`${t.views_in_period} in last 30 days`} />
        <Stat label="Visits" value={t.visits} hint={`${t.unique_visitors_in_period} unique visitors (30 days)`} />
        <Stat label="Storage used" value={formatBytes(t.storage_bytes)} hint={`${hours} hours watched`} />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Panel title="Video processing">
          {data.active_jobs.length === 0 && data.processing_failures.length === 0 ? (
            <p className="text-sm text-muted">Nothing queued. Upload a video from a movie&apos;s edit page.</p>
          ) : (
            <ul className="space-y-2 text-sm">
              {data.active_jobs.map((j) => (
                <li key={j.id} className="flex items-center justify-between gap-2">
                  <Link href={`/admin/movies/${j.movie_id}`} className="hover:text-accent">{j.title}</Link>
                  <StatusBadge status={j.status} />
                </li>
              ))}
              {data.processing_failures.map((j) => (
                <li key={j.id}>
                  <div className="flex items-center justify-between gap-2">
                    <Link href={`/admin/movies/${j.movie_id}`} className="hover:text-accent">{j.title}</Link>
                    <StatusBadge status="failed" />
                  </div>
                  {j.error && <p className="mt-0.5 line-clamp-2 text-xs text-red-300">{j.error}</p>}
                </li>
              ))}
            </ul>
          )}
        </Panel>

        <Panel title="Most watched">
          {data.most_watched.length === 0 ? (
            <p className="text-sm text-muted">No plays recorded yet.</p>
          ) : (
            <table className="w-full text-sm">
              <tbody>
                {data.most_watched.map((m) => (
                  <tr key={m.id} className="border-t border-line first:border-0">
                    <td className="py-1.5">
                      <Link href={`/admin/movies/${m.id}`} className="hover:text-accent">{m.title}</Link>
                    </td>
                    <td className="py-1.5 text-right tabular-nums text-muted">{m.views} plays</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Panel>

        <Panel title="Recently added">
          <ul className="space-y-2 text-sm">
            {data.recent_movies.map((m) => (
              <li key={m.id} className="flex items-center justify-between gap-2">
                <Link href={`/admin/movies/${m.id}`} className="hover:text-accent">{m.title}</Link>
                <StatusBadge status={m.status} />
              </li>
            ))}
          </ul>
        </Panel>

        <Panel title="Audience (last 30 days)">
          <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-sm">
            {Object.entries(data.devices).map(([device, count]) => (
              <div key={device} className="contents">
                <dt className="capitalize text-muted">{device}</dt>
                <dd className="text-right tabular-nums">{count} visits</dd>
              </div>
            ))}
            {data.popular_genres.slice(0, 5).map((g) => (
              <div key={g.name} className="contents">
                <dt className="text-muted">{g.name}</dt>
                <dd className="text-right tabular-nums">{g.views} plays</dd>
              </div>
            ))}
          </dl>
          {Object.keys(data.devices).length === 0 && <p className="text-sm text-muted">No visits recorded yet.</p>}
        </Panel>
      </div>
    </div>
  );
}
