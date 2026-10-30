import type { Metadata } from "next";

import MovieGrid, { pageNumber } from "@/components/MovieGrid";
import { api, safe } from "@/services/api";

export const metadata: Metadata = { title: "Search", robots: { index: false } };

type Params = { q?: string; language?: string; genre?: string; year?: string; sort?: string; page?: string };

const SORTS = [
  { value: "latest", label: "Newest added" },
  { value: "title", label: "Title A–Z" },
  { value: "year", label: "Release year" },
  { value: "popular", label: "Most watched" },
] as const;

export default async function SearchPage({ searchParams }: { searchParams: Promise<Params> }) {
  const params = await searchParams;
  const q = (params.q ?? "").slice(0, 100);
  const year = Number(params.year) || undefined;
  const sort = SORTS.some((s) => s.value === params.sort) ? (params.sort as (typeof SORTS)[number]["value"]) : "latest";
  const page = pageNumber(params.page);

  const [languages, genres, results] = await Promise.all([
    safe(api.languages(), []),
    safe(api.genres(), []),
    safe(
      api.search({ q, language: params.language, genre: params.genre, year, sort, page, page_size: 24 }),
      { items: [], total: 0, page: 1, page_size: 24, pages: 1 },
    ),
  ]);

  const hrefFor = (p: number) => {
    const sp = new URLSearchParams();
    for (const [k, v] of Object.entries({ ...params, page: String(p) })) if (v) sp.set(k, v);
    return `/search?${sp.toString()}`;
  };

  const field = "rounded-md border border-line bg-panel px-3 py-2 text-sm focus:border-accent focus:outline-none";

  return (
    <div className="py-8">
      <h1 className="mb-4 text-2xl font-extrabold sm:text-3xl">{q ? `Results for “${q}”` : "Search movies"}</h1>

      <form method="get" className="mb-6 grid grid-cols-2 gap-3 sm:grid-cols-6" data-testid="search-filters">
        <input name="q" defaultValue={q} placeholder="Title, director or cast" maxLength={100} className={`${field} col-span-2`} aria-label="Search text" />
        <select name="language" defaultValue={params.language ?? ""} className={field} aria-label="Language">
          <option value="">All languages</option>
          {languages.map((l) => (
            <option key={l.code} value={l.code}>{l.name}</option>
          ))}
        </select>
        <select name="genre" defaultValue={params.genre ?? ""} className={field} aria-label="Genre">
          <option value="">All genres</option>
          {genres.map((g) => (
            <option key={g.slug} value={g.slug}>{g.name}</option>
          ))}
        </select>
        <input name="year" type="number" min={1888} max={2100} defaultValue={params.year ?? ""} placeholder="Year" className={field} aria-label="Release year" />
        <select name="sort" defaultValue={sort} className={field} aria-label="Sort by">
          {SORTS.map((s) => (
            <option key={s.value} value={s.value}>{s.label}</option>
          ))}
        </select>
        <button type="submit" className="col-span-2 rounded-md bg-accent px-4 py-2 text-sm font-semibold text-accent-ink sm:col-span-6 sm:justify-self-start">
          Apply filters
        </button>
      </form>

      <p className="mb-4 text-sm text-muted">{results.total} movie{results.total === 1 ? "" : "s"} found</p>
      <MovieGrid page={results} hrefFor={hrefFor} emptyText="No movies match your search. Try fewer filters." />
    </div>
  );
}
