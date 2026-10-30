"use client";

import { useEffect, useState } from "react";

import { useAdmin } from "@/components/admin/AdminShell";
import { adminApi, type AdminMovie, type MovieInput } from "@/services/adminApi";
import type { Genre, Language } from "@/services/types";

interface Props {
  movie?: AdminMovie;
  onSaved: (movie: AdminMovie) => void;
}

const field = "mt-1 w-full rounded-md border border-line bg-ink px-3 py-2 text-sm focus:border-accent focus:outline-none";

export default function MovieForm({ movie, onSaved }: Props) {
  const { notify } = useAdmin();
  const [languages, setLanguages] = useState<Language[]>([]);
  const [genres, setGenres] = useState<Genre[]>([]);
  const [busy, setBusy] = useState(false);

  const [title, setTitle] = useState(movie?.title ?? "");
  const [year, setYear] = useState(movie?.release_year?.toString() ?? "");
  const [languageId, setLanguageId] = useState(movie?.language_id?.toString() ?? "");
  const [genreIds, setGenreIds] = useState<number[]>(movie?.genres.map((g) => g.id) ?? []);
  const [minutes, setMinutes] = useState(movie?.duration ? String(Math.round(movie.duration / 60)) : "");
  const [director, setDirector] = useState(movie?.director ?? "");
  const [cast, setCast] = useState(movie?.cast_members.join(", ") ?? "");
  const [description, setDescription] = useState(movie?.description ?? "");
  const [license, setLicense] = useState(movie?.license ?? "");
  const [featured, setFeatured] = useState(movie?.featured ?? false);
  const [publish, setPublish] = useState(movie ? movie.status === "published" : false);
  const [videoUrl, setVideoUrl] = useState(movie?.video_url && !movie.latest_job ? movie.video_url : "");

  useEffect(() => {
    Promise.all([adminApi.languages(), adminApi.genres()])
      .then(([l, g]) => {
        setLanguages(l);
        setGenres(g);
      })
      .catch((err) => notify(err.message, "error"));
  }, [notify]);

  const toggleGenre = (id: number) =>
    setGenreIds((ids) => (ids.includes(id) ? ids.filter((x) => x !== id) : [...ids, id]));

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    const body: MovieInput = {
      title: title.trim(),
      description: description.trim(),
      release_year: year ? Number(year) : null,
      language_id: languageId ? Number(languageId) : null,
      genre_ids: genreIds,
      duration: minutes ? Math.round(Number(minutes) * 60) : null,
      director: director.trim() || null,
      cast_members: cast.split(",").map((c) => c.trim()).filter(Boolean),
      license: license.trim() || null,
      featured,
      status: publish ? "published" : "draft",
      video_url: videoUrl.trim() || null,
    };
    // When a processed upload exists, don't overwrite its URL from this form.
    const payload: Partial<MovieInput> = { ...body };
    if (movie?.latest_job && !videoUrl.trim()) delete payload.video_url;
    try {
      const saved = movie ? await adminApi.updateMovie(movie.id, payload) : await adminApi.createMovie(body);
      notify(movie ? "Changes saved" : "Movie created. Now upload a poster and video.");
      onSaved(saved);
    } catch (err) {
      notify(err instanceof Error ? err.message : "Save failed", "error");
    } finally {
      setBusy(false);
    }
  };

  return (
    <form onSubmit={submit} className="space-y-4 rounded-xl bg-panel p-5 ring-1 ring-line" data-testid="movie-form">
      <div className="grid gap-4 sm:grid-cols-2">
        <label className="block text-sm sm:col-span-2">
          Title *
          <input className={field} value={title} onChange={(e) => setTitle(e.target.value)} required maxLength={200} />
        </label>
        <label className="block text-sm">
          Release year
          <input className={field} type="number" min={1888} max={2100} value={year} onChange={(e) => setYear(e.target.value)} />
        </label>
        <label className="block text-sm">
          Duration (minutes)
          <input className={field} type="number" min={1} max={600} value={minutes} onChange={(e) => setMinutes(e.target.value)} />
        </label>
        <label className="block text-sm">
          Language
          <select className={field} value={languageId} onChange={(e) => setLanguageId(e.target.value)}>
            <option value="">— Select —</option>
            {languages.map((l) => (
              <option key={l.id} value={l.id}>{l.name}</option>
            ))}
          </select>
        </label>
        <label className="block text-sm">
          Director
          <input className={field} value={director} onChange={(e) => setDirector(e.target.value)} maxLength={200} />
        </label>
      </div>

      <fieldset>
        <legend className="text-sm">Genres</legend>
        <div className="mt-2 flex flex-wrap gap-2">
          {genres.map((g) => {
            const on = genreIds.includes(g.id);
            return (
              <button
                key={g.id}
                type="button"
                aria-pressed={on}
                onClick={() => toggleGenre(g.id)}
                className={`rounded-full border px-3 py-1 text-sm ${on ? "border-accent bg-accent text-accent-ink" : "border-line text-muted hover:text-white"}`}
              >
                {g.name}
              </button>
            );
          })}
        </div>
      </fieldset>

      <label className="block text-sm">
        Cast (comma separated)
        <input className={field} value={cast} onChange={(e) => setCast(e.target.value)} placeholder="Actor One, Actor Two" />
      </label>
      <label className="block text-sm">
        Description
        <textarea className={`${field} min-h-28`} value={description} onChange={(e) => setDescription(e.target.value)} maxLength={5000} />
      </label>
      <label className="block text-sm">
        Rights / licence *
        <input
          className={field}
          value={license}
          onChange={(e) => setLicense(e.target.value)}
          required
          maxLength={200}
          placeholder='e.g. "Public domain (US)", "CC BY 3.0", "Licensed from …"'
        />
        <span className="mt-1 block text-xs text-muted">Only add films you have the right to stream. This is shown on the movie page.</span>
      </label>
      <label className="block text-sm">
        External video URL (optional)
        <input
          className={field}
          type="url"
          value={videoUrl}
          onChange={(e) => setVideoUrl(e.target.value)}
          placeholder="https://…/master.m3u8. Leave empty if you'll upload a file."
        />
      </label>

      <div className="flex flex-wrap gap-6 text-sm">
        <label className="flex items-center gap-2">
          <input type="checkbox" checked={publish} onChange={(e) => setPublish(e.target.checked)} className="accent-[var(--color-accent)]" />
          Published (visible to visitors)
        </label>
        <label className="flex items-center gap-2">
          <input type="checkbox" checked={featured} onChange={(e) => setFeatured(e.target.checked)} className="accent-[var(--color-accent)]" />
          Featured on homepage
        </label>
      </div>

      <button type="submit" disabled={busy} className="rounded-md bg-accent px-5 py-2.5 text-sm font-semibold text-accent-ink disabled:opacity-60">
        {busy ? "Saving…" : movie ? "Save changes" : "Create movie"}
      </button>
    </form>
  );
}
