"use client";

import type { Genre, Language, MovieDetail } from "./types";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const SESSION_KEY = "fr_admin_session";

export interface AdminUser {
  id: number;
  username: string;
  role: "admin" | "editor";
}

export interface AdminSession {
  token: string;
  user: AdminUser;
  expiresAt: number; // epoch ms
}

export interface Job {
  id: number;
  movie_id: number;
  status: "queued" | "running" | "succeeded" | "failed";
  attempts: number;
  error: string | null;
  source_bytes: number;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
}

export interface AdminMovie extends MovieDetail {
  status: "draft" | "processing" | "published" | "failed";
  language_id: number | null;
  storage_bytes: number;
  updated_at: string;
  latest_job: Job | null;
}

export interface AdminMoviePage {
  items: AdminMovie[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

export interface MovieInput {
  title: string;
  description: string;
  release_year: number | null;
  language_id: number | null;
  genre_ids: number[];
  duration: number | null;
  director: string | null;
  cast_members: string[];
  license: string | null;
  featured: boolean;
  status: "draft" | "published";
  video_url: string | null;
}

export interface Analytics {
  period_days: number;
  totals: {
    movies: number;
    movies_by_status: Record<string, number>;
    views: number;
    views_in_period: number;
    watch_seconds: number;
    visits: number;
    visits_in_period: number;
    unique_visitors_in_period: number;
    storage_bytes: number;
  };
  most_watched: { id: number; title: string; slug: string; views: number; watch_seconds: number }[];
  popular_genres: { name: string; views: number }[];
  popular_languages: { name: string; views: number }[];
  devices: Record<string, number>;
  trend: { date: string; visits: number; plays: number }[];
  recent_movies: { id: number; title: string; slug: string; status: string; created_at: string }[];
  jobs_by_status: Record<string, number>;
  active_jobs: { id: number; movie_id: number; title: string; status: string; created_at: string }[];
  processing_failures: { id: number; movie_id: number; title: string; error: string | null; finished_at: string | null }[];
  ads: { id: number; title: string; placement: string; status: string; impressions: number; clicks: number; ctr: number }[];
}

// ---- session (sessionStorage: cleared when the tab closes) -------------------------

export function getSession(): AdminSession | null {
  try {
    const raw = sessionStorage.getItem(SESSION_KEY);
    if (!raw) return null;
    const session = JSON.parse(raw) as AdminSession;
    if (Date.now() >= session.expiresAt) {
      sessionStorage.removeItem(SESSION_KEY);
      return null;
    }
    return session;
  } catch {
    return null;
  }
}

function saveSession(session: AdminSession) {
  try {
    sessionStorage.setItem(SESSION_KEY, JSON.stringify(session));
  } catch {
    // storage blocked: the session lasts only for this page load
  }
}

export function clearSession() {
  try {
    sessionStorage.removeItem(SESSION_KEY);
  } catch {
    // ignore
  }
}

// ---- requests --------------------------------------------------------------------

export class AdminApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

async function errorMessage(res: Response): Promise<string> {
  try {
    const body = await res.json();
    if (typeof body.detail === "string") return body.detail;
    if (Array.isArray(body.detail)) {
      return body.detail
        .map((e: { loc?: (string | number)[]; msg: string }) => {
          const field = e.loc?.filter((p) => p !== "body").join(".");
          return field ? `${field}: ${e.msg}` : e.msg;
        })
        .join("; ");
    }
  } catch {
    // not JSON
  }
  return `Request failed (${res.status})`;
}

function handleExpired(status: number) {
  if (status === 401 && typeof window !== "undefined" && !window.location.pathname.startsWith("/admin/login")) {
    clearSession();
    window.location.href = "/admin/login?expired=1";
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const session = getSession();
  const headers = new Headers(init.headers);
  if (session) headers.set("Authorization", `Bearer ${session.token}`);
  if (init.body && !(init.body instanceof FormData)) headers.set("Content-Type", "application/json");

  let res: Response;
  try {
    res = await fetch(`${API}${path}`, { ...init, headers, cache: "no-store" });
  } catch {
    throw new AdminApiError(0, "Can't reach the server. Check that the API is running.");
  }
  if (!res.ok) {
    handleExpired(res.status);
    throw new AdminApiError(res.status, await errorMessage(res));
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

const json = (body: unknown) => JSON.stringify(body);

export const adminApi = {
  async login(username: string, password: string): Promise<AdminSession> {
    const data = await request<{ access_token: string; expires_in: number; admin: AdminUser }>("/api/admin/login", {
      method: "POST",
      body: json({ username, password }),
    });
    const session = {
      token: data.access_token,
      user: data.admin,
      expiresAt: Date.now() + (data.expires_in - 30) * 1000,
    };
    saveSession(session);
    return session;
  },
  movies: (params: { page?: number; q?: string; status?: string } = {}) => {
    const qs = new URLSearchParams();
    for (const [k, v] of Object.entries(params)) if (v) qs.set(k, String(v));
    return request<AdminMoviePage>(`/api/admin/movies?${qs}`);
  },
  movie: (id: number) => request<AdminMovie>(`/api/admin/movies/${id}`),
  createMovie: (body: MovieInput) => request<AdminMovie>("/api/admin/movies", { method: "POST", body: json(body) }),
  updateMovie: (id: number, body: Partial<MovieInput>) =>
    request<AdminMovie>(`/api/admin/movies/${id}`, { method: "PUT", body: json(body) }),
  deleteMovie: (id: number) => request<void>(`/api/admin/movies/${id}`, { method: "DELETE" }),
  languages: () => request<Language[]>("/api/admin/languages"),
  genres: () => request<Genre[]>("/api/admin/genres"),
  retryJob: (id: number) => request<Job>(`/api/admin/jobs/${id}/retry`, { method: "POST" }),
  analytics: (days = 30) => request<Analytics>(`/api/admin/analytics?days=${days}`),
};

/** Multipart upload with progress (fetch can't report upload progress, XHR can). */
export function uploadFile<T>(path: string, file: File, onProgress: (percent: number) => void): Promise<T> {
  return new Promise((resolve, reject) => {
    const session = getSession();
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${API}${path}`);
    if (session) xhr.setRequestHeader("Authorization", `Bearer ${session.token}`);
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) onProgress(Math.round((e.loaded / e.total) * 100));
    };
    xhr.onload = () => {
      let body: { detail?: unknown } | null = null;
      try {
        body = JSON.parse(xhr.responseText);
      } catch {
        // ignore
      }
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(body as T);
        return;
      }
      handleExpired(xhr.status);
      const detail = typeof body?.detail === "string" ? body.detail : `Upload failed (${xhr.status})`;
      reject(new AdminApiError(xhr.status, detail));
    };
    xhr.onerror = () => reject(new AdminApiError(0, "Upload failed: network error."));
    const form = new FormData();
    form.append("file", file);
    xhr.send(form);
  });
}

export function formatBytes(bytes: number): string {
  if (!bytes) return "0 B";
  const units = ["B", "KB", "MB", "GB", "TB"];
  const i = Math.min(units.length - 1, Math.floor(Math.log(bytes) / Math.log(1024)));
  return `${(bytes / 1024 ** i).toFixed(i ? 1 : 0)} ${units[i]}`;
}
