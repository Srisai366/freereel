"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { useAdmin } from "@/components/admin/AdminShell";
import StatusBadge from "@/components/admin/StatusBadge";
import Poster from "@/components/Poster";
import { adminApi, type AdminMoviePage } from "@/services/adminApi";

const STATUSES = ["", "draft", "processing", "published", "failed"];

export default function AdminMoviesPage() {
  const { session, notify } = useAdmin();
  const isAdmin = session.user.role === "admin";
  const [q, setQ] = useState("");
  const [status, setStatus] = useState("");
  const [page, setPage] = useState(1);
  const [data, setData] = useState<AdminMoviePage | null>(null);
  const [reload, setReload] = useState(0);
  const [deleting, setDeleting] = useState<number | null>(null);

  useEffect(() => {
    const timer = setTimeout(() => {
      adminApi
        .movies({ q, status, page })
        .then(setData)
        .catch((err) => notify(err.message, "error"));
    }, 250); // debounce typing
    return () => clearTimeout(timer);
  }, [q, status, page, reload, notify]);

  const remove = async (id: number, title: string) => {
    if (!window.confirm(`Delete "${title}" and all its files? This can't be undone.`)) return;
    setDeleting(id);
    try {
      await adminApi.deleteMovie(id);
      notify(`Deleted "${title}"`);
      setReload((n) => n + 1);
    } catch (err) {
      notify(err instanceof Error ? err.message : "Delete failed", "error");
    } finally {
      setDeleting(null);
    }
  };

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-extrabold">Movies</h1>
        <Link href="/admin/movies/new" className="rounded-md bg-accent px-4 py-2 text-sm font-semibold text-accent-ink">
          + Add movie
        </Link>
      </div>

      <div className="mb-4 flex flex-wrap gap-3">
        <input
          value={q}
          onChange={(e) => { setQ(e.target.value); setPage(1); }}
          placeholder="Search by title"
          aria-label="Search by title"
          className="w-64 rounded-md border border-line bg-panel px-3 py-2 text-sm focus:border-accent focus:outline-none"
        />
        <select
          value={status}
          onChange={(e) => { setStatus(e.target.value); setPage(1); }}
          aria-label="Filter by status"
          className="rounded-md border border-line bg-panel px-3 py-2 text-sm"
        >
          {STATUSES.map((s) => (
            <option key={s} value={s}>{s ? s[0].toUpperCase() + s.slice(1) : "All statuses"}</option>
          ))}
        </select>
      </div>

      {!data ? (
        <p className="text-muted">Loading…</p>
      ) : data.items.length === 0 ? (
        <p className="py-10 text-center text-muted">No movies match.</p>
      ) : (
        <div className="overflow-x-auto rounded-xl ring-1 ring-line">
          <table className="w-full min-w-[640px] text-sm" data-testid="admin-movie-table">
            <thead className="bg-panel text-left text-xs uppercase tracking-wide text-muted">
              <tr>
                <th className="px-3 py-2">Movie</th>
                <th className="px-3 py-2">Language</th>
                <th className="px-3 py-2">Video</th>
                <th className="px-3 py-2">Status</th>
                <th className="px-3 py-2" />
              </tr>
            </thead>
            <tbody>
              {data.items.map((m) => (
                <tr key={m.id} className="border-t border-line">
                  <td className="px-3 py-2">
                    <div className="flex items-center gap-3">
                      <div className="aspect-[2/3] w-10 shrink-0 overflow-hidden rounded">
                        <Poster title={m.title} src={m.poster_url} />
                      </div>
                      <div>
                        <p className="font-semibold">{m.title}</p>
                        <p className="text-xs text-muted">{m.release_year ?? "—"}{m.featured ? " · Featured" : ""}</p>
                      </div>
                    </div>
                  </td>
                  <td className="px-3 py-2 text-muted">{m.language?.name ?? "—"}</td>
                  <td className="px-3 py-2 text-muted">
                    {m.has_video ? (m.video_quality.join(", ") || "Ready") : m.latest_job ? <StatusBadge status={m.latest_job.status} /> : "None"}
                  </td>
                  <td className="px-3 py-2"><StatusBadge status={m.status} /></td>
                  <td className="whitespace-nowrap px-3 py-2 text-right">
                    <Link href={`/admin/movies/${m.id}`} className="rounded-md border border-line px-3 py-1 hover:border-accent">
                      Edit
                    </Link>
                    {isAdmin && (
                      <button
                        type="button"
                        onClick={() => remove(m.id, m.title)}
                        disabled={deleting === m.id}
                        className="ml-2 rounded-md border border-red-900 px-3 py-1 text-red-300 hover:bg-red-950 disabled:opacity-50"
                        data-testid="delete-movie"
                      >
                        {deleting === m.id ? "Deleting…" : "Delete"}
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {data && data.pages > 1 && (
        <div className="mt-4 flex items-center justify-center gap-3 text-sm">
          <button type="button" disabled={page <= 1} onClick={() => setPage(page - 1)} className="rounded-md border border-line px-3 py-1.5 disabled:opacity-40">← Previous</button>
          <span className="text-muted">Page {data.page} of {data.pages}</span>
          <button type="button" disabled={page >= data.pages} onClick={() => setPage(page + 1)} className="rounded-md border border-line px-3 py-1.5 disabled:opacity-40">Next →</button>
        </div>
      )}
    </div>
  );
}
