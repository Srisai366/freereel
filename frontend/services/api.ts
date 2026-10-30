import type { Ad, GenreWithCount, LanguageWithCount, MovieCard, MovieDetail, MoviePage } from "./types";

const PUBLIC_API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

function baseUrl(): string {
  // On the server we may reach the API over a private URL (e.g. Docker network).
  if (typeof window === "undefined" && process.env.API_INTERNAL_URL) {
    return process.env.API_INTERNAL_URL;
  }
  return PUBLIC_API;
}

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

type Query = Record<string, string | number | undefined | null>;

function withQuery(path: string, query?: Query): string {
  if (!query) return path;
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) {
    if (value !== undefined && value !== null && value !== "") params.set(key, String(value));
  }
  const qs = params.toString();
  return qs ? `${path}?${qs}` : path;
}

async function get<T>(path: string, query?: Query, revalidate = 60): Promise<T> {
  const res = await fetch(`${baseUrl()}${withQuery(path, query)}`, {
    next: { revalidate },
    headers: { Accept: "application/json" },
  });
  if (!res.ok) throw new ApiError(res.status, `GET ${path} failed with ${res.status}`);
  return res.json() as Promise<T>;
}

export interface MovieFilters {
  q?: string;
  language?: string;
  genre?: string;
  year?: number;
  sort?: "latest" | "title" | "year" | "popular";
  page?: number;
  page_size?: number;
}

export const api = {
  latest: (limit = 12) => get<MovieCard[]>("/api/movies/latest", { limit }),
  featured: (limit = 8) => get<MovieCard[]>("/api/movies/featured", { limit }),
  trending: (limit = 12) => get<MovieCard[]>("/api/movies/trending", { limit }, 300),
  movies: (filters: MovieFilters = {}) => get<MoviePage>("/api/movies", { ...filters }),
  search: (filters: MovieFilters) => get<MoviePage>("/api/movies/search", { ...filters }, 30),
  movie: (ref: string) => get<MovieDetail>(`/api/movies/${encodeURIComponent(ref)}`),
  languages: () => get<LanguageWithCount[]>("/api/languages", undefined, 300),
  genres: () => get<GenreWithCount[]>("/api/genres", undefined, 300),
  ads: (placement: string) => get<Ad[]>("/api/ads", { placement }, 120),
};

/** Fetch that resolves to a fallback instead of throwing, so one failing section doesn't blank the page. */
export async function safe<T>(promise: Promise<T>, fallback: T): Promise<T> {
  try {
    return await promise;
  } catch (err) {
    console.error(err);
    return fallback;
  }
}

export function formatDuration(seconds: number | null): string | null {
  if (!seconds) return null;
  const h = Math.floor(seconds / 3600);
  const m = Math.round((seconds % 3600) / 60);
  return h ? `${h}h ${m}m` : `${m}m`;
}
