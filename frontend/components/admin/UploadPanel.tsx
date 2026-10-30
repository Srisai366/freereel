"use client";

import { useEffect, useRef, useState } from "react";

import { useAdmin } from "@/components/admin/AdminShell";
import StatusBadge from "@/components/admin/StatusBadge";
import Poster from "@/components/Poster";
import { adminApi, formatBytes, uploadFile, type AdminMovie, type Job } from "@/services/adminApi";

const POSTER_TYPES = ".jpg,.jpeg,.png,.webp";
const VIDEO_TYPES = ".mp4,.m4v,.mov,.mkv,.webm,.avi";
const MAX_POSTER_MB = 5;
const MAX_VIDEO_MB = 4096;

interface Props {
  movie: AdminMovie;
  onChange: (movie: AdminMovie) => void;
}

function ProgressBar({ percent }: { percent: number }) {
  return (
    <div className="mt-3" role="progressbar" aria-valuenow={percent} aria-valuemin={0} aria-valuemax={100}>
      <div className="h-2 overflow-hidden rounded-full bg-panel-2">
        <div className="h-full bg-accent transition-all" style={{ width: `${percent}%` }} />
      </div>
      <p className="mt-1 text-xs text-muted">{percent < 100 ? `Uploading… ${percent}%` : "Upload complete, saving…"}</p>
    </div>
  );
}

export default function UploadPanel({ movie, onChange }: Props) {
  const { notify } = useAdmin();
  const posterInput = useRef<HTMLInputElement>(null);
  const videoInput = useRef<HTMLInputElement>(null);
  const [posterProgress, setPosterProgress] = useState<number | null>(null);
  const [videoProgress, setVideoProgress] = useState<number | null>(null);
  const job = movie.latest_job;
  const jobActive = job?.status === "queued" || job?.status === "running";

  // While the worker is processing, refresh every 5 s so the status updates by itself.
  useEffect(() => {
    if (!jobActive) return;
    const timer = setInterval(async () => {
      try {
        const fresh = await adminApi.movie(movie.id);
        onChange(fresh);
        if (fresh.latest_job?.status === "succeeded") notify(`"${fresh.title}" is processed and ready to watch.`);
        if (fresh.latest_job?.status === "failed") notify(`Processing failed: ${fresh.latest_job.error ?? "unknown error"}`, "error");
      } catch {
        // transient; try again on the next tick
      }
    }, 5000);
    return () => clearInterval(timer);
  }, [jobActive, movie.id, onChange, notify]);

  const pick = (input: HTMLInputElement | null, maxMb: number): File | null => {
    const file = input?.files?.[0] ?? null;
    if (input) input.value = "";
    if (file && file.size > maxMb * 1024 * 1024) {
      notify(`File is too large (max ${maxMb >= 1024 ? `${maxMb / 1024} GB` : `${maxMb} MB`}).`, "error");
      return null;
    }
    return file;
  };

  const uploadPoster = async () => {
    const file = pick(posterInput.current, MAX_POSTER_MB);
    if (!file) return;
    setPosterProgress(0);
    try {
      const updated = await uploadFile<AdminMovie>(`/api/admin/movies/${movie.id}/poster`, file, setPosterProgress);
      onChange(updated);
      notify("Poster uploaded");
    } catch (err) {
      notify(err instanceof Error ? err.message : "Poster upload failed", "error");
    } finally {
      setPosterProgress(null);
    }
  };

  const uploadVideo = async () => {
    const file = pick(videoInput.current, MAX_VIDEO_MB);
    if (!file) return;
    setVideoProgress(0);
    try {
      await uploadFile<Job>(`/api/admin/movies/${movie.id}/video`, file, setVideoProgress);
      onChange(await adminApi.movie(movie.id));
      notify("Video uploaded. Processing has started; this page updates automatically.");
    } catch (err) {
      notify(err instanceof Error ? err.message : "Video upload failed", "error");
    } finally {
      setVideoProgress(null);
    }
  };

  const retry = async () => {
    if (!job) return;
    try {
      await adminApi.retryJob(job.id);
      onChange(await adminApi.movie(movie.id));
      notify("Processing restarted");
    } catch (err) {
      notify(err instanceof Error ? err.message : "Retry failed", "error");
    }
  };

  const busy = posterProgress !== null || videoProgress !== null;

  return (
    <div className="space-y-4">
      <section className="rounded-xl bg-panel p-5 ring-1 ring-line" data-testid="poster-upload">
        <h2 className="font-bold">Poster</h2>
        <div className="mt-3 flex gap-4">
          <div className="aspect-[2/3] w-28 shrink-0 overflow-hidden rounded-lg ring-1 ring-line">
            <Poster title={movie.title} src={movie.poster_url} />
          </div>
          <div className="text-sm text-muted">
            <p>JPG, PNG or WebP, up to {MAX_POSTER_MB} MB. Portrait (2:3) looks best. It&apos;s resized automatically.</p>
            <label className="mt-3 inline-block cursor-pointer rounded-md border border-line px-3 py-1.5 text-white hover:border-accent">
              {movie.poster_url ? "Replace poster" : "Choose poster"}
              <input ref={posterInput} type="file" accept={POSTER_TYPES} className="sr-only" onChange={uploadPoster} disabled={busy} />
            </label>
          </div>
        </div>
        {posterProgress !== null && <ProgressBar percent={posterProgress} />}
      </section>

      <section className="rounded-xl bg-panel p-5 ring-1 ring-line" data-testid="video-upload">
        <h2 className="font-bold">Video</h2>
        <div className="mt-2 text-sm">
          {movie.has_video ? (
            <p>
              Ready to stream{movie.video_quality.length ? ` in ${movie.video_quality.join(", ")}` : ""}.{" "}
              <a href={`/watch/${movie.slug}`} target="_blank" className="text-accent hover:underline">Watch ↗</a>
            </p>
          ) : (
            <p className="text-muted">No video yet.</p>
          )}
        </div>

        {job && (
          <div className="mt-3 rounded-lg bg-ink p-3 text-sm ring-1 ring-line">
            <div className="flex items-center justify-between gap-2">
              <span>
                Last upload: {formatBytes(job.source_bytes)} · {new Date(job.created_at).toLocaleString()}
              </span>
              <StatusBadge status={job.status} />
            </div>
            {jobActive && (
              <p className="mt-2 text-xs text-muted">
                {job.status === "queued"
                  ? "Waiting for the video worker to pick this up."
                  : "Converting to streaming formats. A full-length film can take a while."}
              </p>
            )}
            {job.status === "failed" && (
              <div className="mt-2">
                <p className="text-xs text-red-300">{job.error}</p>
                <button type="button" onClick={retry} className="mt-2 rounded-md border border-line px-3 py-1 text-xs hover:border-accent">
                  Retry processing
                </button>
              </div>
            )}
          </div>
        )}

        <p className="mt-3 text-xs text-muted">
          MP4, MOV, MKV, WebM or AVI, up to 4 GB. It&apos;s converted to 360p–1080p (never above the original&apos;s quality) and published
          automatically when done. Only upload films you have the right to stream.
        </p>
        <label
          className={`mt-3 inline-block cursor-pointer rounded-md bg-accent px-4 py-2 text-sm font-semibold text-accent-ink ${busy || jobActive ? "pointer-events-none opacity-50" : ""}`}
        >
          {movie.has_video || job ? "Upload a new video" : "Upload video"}
          <input ref={videoInput} type="file" accept={VIDEO_TYPES} className="sr-only" onChange={uploadVideo} disabled={busy || jobActive} />
        </label>
        {videoProgress !== null && <ProgressBar percent={videoProgress} />}
      </section>
    </div>
  );
}
