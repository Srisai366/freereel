"use client";

import { useEffect, useState } from "react";

import { useAdmin } from "@/components/admin/AdminShell";
import {
  MAX_POSTER_MB,
  MAX_VIDEO_MB,
  POSTER_TYPES,
  ProgressBar,
  VIDEO_TYPES,
  sizeError,
} from "@/components/admin/UploadPanel";
import { adminApi, formatBytes, uploadFile, type AdminMovie, type MovieInput } from "@/services/adminApi";
import type { Genre, Language } from "@/services/types";

interface Props {
  movie?: AdminMovie;
  onSaved: (movie: AdminMovie) => void;
}

const field = "mt-1 w-full rounded-md border border-line bg-ink px-3 py-2 text-sm focus:border-accent focus:outline-none";

function FilePicker(props: {
  label: string;
  hint: string;
  accept: string;
  maxMb: number;
  file: File | null;
  disabled: boolean;
  onPick: (file: File | null) => void;
  testId: string;
}) {
  const { notify } = useAdmin();
  return (
    <div className="rounded-lg border border-dashed border-line p-4" data-testid={props.testId}>
      <p className="text-sm font-semibold">{props.label}</p>
      <p className="mt-0.5 text-xs text-muted">{props.hint}</p>
      <div className="mt-3 flex flex-wrap items-center gap-3">
        <label className={`cursor-pointer rounded-md border border-line px-3 py-1.5 text-sm hover:border-accent ${props.disabled ? "pointer-events-none opacity-50" : ""}`}>
          {props.file ? "Change file" : `Choose ${props.label.toLowerCase()}`}
          <input
            type="file"
            accept={props.accept}
            className="sr-only"
            disabled={props.disabled}
            onChange={(e) => {
              const file = e.target.files?.[0] ?? null;
              e.target.value = "";
              const tooBig = file && sizeError(file, props.maxMb);
              if (tooBig) notify(tooBig, "error");
              else props.onPick(file);
            }}
          />
        </label>
        {props.file ? (
          <span className="flex items-center gap-2 text-sm">
            <span className="max-w-56 truncate">{props.file.name}</span>
            <span className="text-muted">({formatBytes(props.file.size)})</span>
            <button type="button" onClick={() => props.onPick(null)} disabled={props.disabled} className="text-xs text-muted hover:text-white">
              Remove
            </button>
          </span>
        ) : (
          <span className="text-sm text-muted">No file chosen</span>
        )}
      </div>
    </div>
  );
}

export default function MovieForm({ movie, onSaved }: Props) {
  const { notify } = useAdmin();
  const isNew = !movie;
  const [languages, setLanguages] = useState<Language[]>([]);
  const [genres, setGenres] = useState<Genre[]>([]);
  const [busy, setBusy] = useState(false);
  const [progress, setProgress] = useState<{ label: string; percent: number } | null>(null);

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
  const [publish, setPublish] = useState(movie ? movie.status === "published" : true);
  const initialUrl = movie?.video_url && !movie.latest_job ? movie.video_url : "";
  const [videoUrl, setVideoUrl] = useState(initialUrl);
  const [posterFile, setPosterFile] = useState<File | null>(null);
  const [videoFile, setVideoFile] = useState<File | null>(null);

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

  const upload = async (movieId: number, kind: "poster" | "video", file: File) => {
    const label = kind === "poster" ? "Uploading poster" : "Uploading video";
    setProgress({ label, percent: 0 });
    try {
      await uploadFile(`/api/admin/movies/${movieId}/${kind}`, file, (percent) => setProgress({ label, percent }));
    } finally {
      setProgress(null);
    }
  };

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    const external = videoFile ? "" : videoUrl.trim();
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
      video_url: external || null,
    };

    if (!isNew) {
      // Only touch video_url if the admin actually changed the external link.
      const payload: Partial<MovieInput> = { ...body };
      if (external === initialUrl) delete payload.video_url;
      try {
        const saved = await adminApi.updateMovie(movie.id, payload);
        notify("Changes saved");
        onSaved(saved);
      } catch (err) {
        notify(err instanceof Error ? err.message : "Save failed", "error");
      } finally {
        setBusy(false);
      }
      return;
    }

    let created: AdminMovie;
    try {
      created = await adminApi.createMovie(body);
    } catch (err) {
      notify(err instanceof Error ? err.message : "Save failed", "error");
      setBusy(false);
      return;
    }

    // The movie exists now; upload failures leave it saved so they can be retried from its page.
    try {
      if (posterFile) await upload(created.id, "poster", posterFile);
      if (videoFile) await upload(created.id, "video", videoFile);
      notify(
        videoFile
          ? "Movie saved and video uploaded. It will go live automatically once processing finishes."
          : "Movie saved.",
      );
    } catch (err) {
      notify(
        `Movie saved, but an upload failed: ${err instanceof Error ? err.message : "unknown error"}. You can retry on the next page.`,
        "error",
      );
    }
    onSaved(await adminApi.movie(created.id).catch(() => created));
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
          {isNew && <span className="mt-1 block text-xs text-muted">Filled in automatically from the video if left empty.</span>}
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

      {isNew && (
        <div className="grid gap-3 sm:grid-cols-2">
          <FilePicker
            label="Poster"
            hint={`JPG, PNG or WebP, up to ${MAX_POSTER_MB} MB. Portrait (2:3) looks best.`}
            accept={POSTER_TYPES}
            maxMb={MAX_POSTER_MB}
            file={posterFile}
            disabled={busy}
            onPick={setPosterFile}
            testId="new-poster"
          />
          <FilePicker
            label="Video file"
            hint="MP4, MOV, MKV, WebM or AVI, up to 4 GB. Converted to streaming quality automatically."
            accept={VIDEO_TYPES}
            maxMb={MAX_VIDEO_MB}
            file={videoFile}
            disabled={busy}
            onPick={setVideoFile}
            testId="new-video"
          />
        </div>
      )}

      <details className="rounded-lg border border-line px-4 py-3 text-sm" open={Boolean(initialUrl)}>
        <summary className="cursor-pointer text-muted">Video already hosted elsewhere? Use a link instead</summary>
        <label className="mt-3 block">
          External video URL
          <input
            className={field}
            type="url"
            value={videoFile ? "" : videoUrl}
            onChange={(e) => setVideoUrl(e.target.value)}
            disabled={Boolean(videoFile)}
            placeholder="https://…/master.m3u8 or https://…/film.mp4"
          />
          <span className="mt-1 block text-xs text-muted">
            {videoFile ? "Not used, because a video file is selected." : "Only for authorized streams. Most films should be uploaded as a file."}
          </span>
        </label>
      </details>

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

      {progress && <ProgressBar percent={progress.percent} label={progress.label} />}

      <button type="submit" disabled={busy} className="rounded-md bg-accent px-5 py-2.5 text-sm font-semibold text-accent-ink disabled:opacity-60">
        {busy ? (progress ? `${progress.label}…` : "Saving…") : isNew ? (videoFile ? "Create movie & upload" : "Create movie") : "Save changes"}
      </button>
    </form>
  );
}
