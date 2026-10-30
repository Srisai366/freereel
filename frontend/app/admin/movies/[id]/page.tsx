"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { useAdmin } from "@/components/admin/AdminShell";
import MovieForm from "@/components/admin/MovieForm";
import StatusBadge from "@/components/admin/StatusBadge";
import UploadPanel from "@/components/admin/UploadPanel";
import { adminApi, AdminApiError, type AdminMovie } from "@/services/adminApi";

export default function EditMoviePage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const { session, notify } = useAdmin();
  const [movie, setMovie] = useState<AdminMovie | null>(null);
  const [missing, setMissing] = useState(false);
  // Remount the form after a save so it shows server-normalised values.
  const [formKey, setFormKey] = useState(0);

  useEffect(() => {
    adminApi
      .movie(Number(id))
      .then(setMovie)
      .catch((err) => {
        if (err instanceof AdminApiError && err.status === 404) setMissing(true);
        else notify(err.message, "error");
      });
  }, [id, notify]);

  const onChange = useCallback((m: AdminMovie) => setMovie(m), []);

  const remove = async () => {
    if (!movie || !window.confirm(`Delete "${movie.title}" and its files? This can't be undone.`)) return;
    try {
      await adminApi.deleteMovie(movie.id);
      notify("Movie deleted");
      router.replace("/admin/movies");
    } catch (err) {
      notify(err instanceof Error ? err.message : "Delete failed", "error");
    }
  };

  if (missing) {
    return (
      <p className="text-muted">
        Movie not found. <Link href="/admin/movies" className="text-accent">Back to movies</Link>
      </p>
    );
  }
  if (!movie) return <p className="text-muted">Loading…</p>;

  return (
    <div>
      <Link href="/admin/movies" className="text-sm text-muted hover:text-accent">← All movies</Link>
      <div className="mb-6 mt-2 flex flex-wrap items-center gap-3">
        <h1 className="text-2xl font-extrabold">{movie.title}</h1>
        <StatusBadge status={movie.status} />
        {movie.status === "published" && (
          <a href={`/movie/${movie.slug}`} target="_blank" className="text-sm text-accent hover:underline">View on site ↗</a>
        )}
      </div>

      <div className="grid gap-6 lg:grid-cols-[1fr_380px]">
        <MovieForm
          key={formKey}
          movie={movie}
          onSaved={(m) => {
            setMovie(m);
            setFormKey((k) => k + 1);
          }}
        />
        <div className="space-y-4">
          <UploadPanel movie={movie} onChange={onChange} />
          {session.user.role === "admin" && (
            <section className="rounded-xl p-5 ring-1 ring-red-900">
              <h2 className="font-bold text-red-300">Danger zone</h2>
              <p className="mt-1 text-sm text-muted">Deletes the movie, its poster and all video files.</p>
              <button type="button" onClick={remove} className="mt-3 rounded-md bg-red-700 px-4 py-2 text-sm font-semibold hover:bg-red-600">
                Delete movie
              </button>
            </section>
          )}
        </div>
      </div>
    </div>
  );
}
