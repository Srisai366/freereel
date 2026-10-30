"use client";

import type Hls from "hls.js";
import { useEffect, useRef, useState } from "react";

import { track } from "@/services/analytics";

interface Props {
  src: string;
  title: string;
  movieId: number;
  poster?: string | null;
}

interface Level {
  index: number;
  label: string;
}

const PROGRESS_EVERY_SECONDS = 30;

export default function VideoPlayer({ src, title, movieId, poster }: Props) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const hlsRef = useRef<Hls | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [levels, setLevels] = useState<Level[]>([]);
  const [level, setLevel] = useState(-1); // -1 = automatic
  const [attempt, setAttempt] = useState(0);

  // Attach the stream: hls.js where needed, native HLS on Safari/iOS, direct src for MP4.
  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;
    let cancelled = false;
    setError(null);
    setLoading(true);
    setLevels([]);

    const isHls = src.toLowerCase().includes(".m3u8");
    const native = video.canPlayType("application/vnd.apple.mpegurl") !== "";

    if (!isHls || native) {
      video.src = src;
      return () => {
        video.removeAttribute("src");
        video.load();
      };
    }

    import("hls.js").then(({ default: HlsLib }) => {
      if (cancelled) return;
      if (!HlsLib.isSupported()) {
        setError("This browser can't play this video. Try Chrome, Firefox, Edge or Safari.");
        setLoading(false);
        return;
      }
      const hls = new HlsLib({ capLevelToPlayerSize: true });
      hlsRef.current = hls;
      let recoveredMedia = false;

      hls.on(HlsLib.Events.MANIFEST_PARSED, (_e, data) => {
        const list = data.levels
          .map((l, index) => ({ index, label: l.height ? `${l.height}p` : `Level ${index + 1}` }))
          .sort((a, b) => parseInt(b.label) - parseInt(a.label));
        setLevels(list);
        setLoading(false);
      });
      hls.on(HlsLib.Events.ERROR, (_e, data) => {
        if (!data.fatal) return;
        if (data.type === HlsLib.ErrorTypes.MEDIA_ERROR && !recoveredMedia) {
          recoveredMedia = true;
          hls.recoverMediaError();
          return;
        }
        setLoading(false);
        setError(
          data.type === HlsLib.ErrorTypes.NETWORK_ERROR
            ? "We couldn't load the video. Check your connection and try again."
            : "Something went wrong while playing this video.",
        );
        hls.destroy();
        hlsRef.current = null;
      });
      hls.loadSource(src);
      hls.attachMedia(video);
    });

    return () => {
      cancelled = true;
      hlsRef.current?.destroy();
      hlsRef.current = null;
    };
  }, [src, attempt]);

  // Anonymous play + approximate watch-time pings.
  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;
    let started = false;
    let lastSent = 0;
    const onPlay = () => {
      if (!started) {
        started = true;
        track("play", { movie_id: movieId });
      }
    };
    const onTime = () => {
      const t = Math.floor(video.currentTime);
      if (t - lastSent >= PROGRESS_EVERY_SECONDS) {
        lastSent = t;
        track("progress", { movie_id: movieId, watch_seconds: t });
      }
    };
    const onEnd = () => track("progress", { movie_id: movieId, watch_seconds: Math.floor(video.currentTime) });
    video.addEventListener("play", onPlay);
    video.addEventListener("timeupdate", onTime);
    video.addEventListener("pause", onEnd);
    video.addEventListener("ended", onEnd);
    return () => {
      video.removeEventListener("play", onPlay);
      video.removeEventListener("timeupdate", onTime);
      video.removeEventListener("pause", onEnd);
      video.removeEventListener("ended", onEnd);
    };
  }, [movieId]);

  const chooseLevel = (value: number) => {
    setLevel(value);
    if (hlsRef.current) hlsRef.current.currentLevel = value;
  };

  return (
    <div className="relative overflow-hidden rounded-xl bg-black ring-1 ring-line" data-testid="video-player">
      {/* Native controls give play/pause, volume, seek bar and fullscreen on every device. No autoplay. */}
      <video
        ref={videoRef}
        controls
        playsInline
        preload="metadata"
        poster={poster ?? undefined}
        aria-label={`Video: ${title}`}
        className="aspect-video w-full bg-black"
        onWaiting={() => setLoading(true)}
        onCanPlay={() => setLoading(false)}
        onPlaying={() => setLoading(false)}
        onLoadedData={() => setLoading(false)}
        onError={() => {
          if (!hlsRef.current) {
            setLoading(false);
            setError("This video couldn't be loaded.");
          }
        }}
      />

      {loading && !error && (
        <div className="pointer-events-none absolute inset-0 grid place-items-center" role="status" aria-label="Loading video">
          <div className="h-12 w-12 animate-spin rounded-full border-4 border-white/20 border-t-accent" />
        </div>
      )}

      {error && (
        <div className="absolute inset-0 grid place-items-center bg-black/80 p-6 text-center" role="alert">
          <div>
            <p className="font-semibold">{error}</p>
            <button
              type="button"
              onClick={() => setAttempt((n) => n + 1)}
              className="mt-4 rounded-md bg-accent px-4 py-2 text-sm font-semibold text-accent-ink"
            >
              Try again
            </button>
          </div>
        </div>
      )}

      {levels.length > 1 && !error && (
        <label className="absolute right-3 top-3 flex items-center gap-2 rounded-md bg-black/70 px-2 py-1 text-xs">
          <span className="text-muted">Quality</span>
          <select
            value={level}
            onChange={(e) => chooseLevel(Number(e.target.value))}
            className="bg-transparent font-semibold focus:outline-none"
            aria-label="Video quality"
          >
            <option value={-1} className="bg-panel">Auto</option>
            {levels.map((l) => (
              <option key={l.index} value={l.index} className="bg-panel">
                {l.label}
              </option>
            ))}
          </select>
        </label>
      )}
    </div>
  );
}
