import Link from "next/link";

import MovieShelf from "@/components/MovieShelf";
import Poster from "@/components/Poster";
import { api, formatDuration, safe } from "@/services/api";

export const revalidate = 60;

export default async function HomePage() {
  const [featured, latest, trending, languages, genres] = await Promise.all([
    safe(api.featured(8), []),
    safe(api.latest(18), []),
    safe(api.trending(12), []),
    safe(api.languages(), []),
    safe(api.genres(), []),
  ]);
  const hero = featured[0] ?? latest[0];

  if (!hero) {
    return (
      <div className="py-24 text-center text-muted" data-testid="empty-catalog">
        <h1 className="text-2xl font-bold text-white">No movies yet</h1>
        <p className="mt-2">The catalogue is empty or the API is unreachable. Please check back soon.</p>
      </div>
    );
  }

  return (
    <>
      <section aria-label="Featured" className="relative mt-6 overflow-hidden rounded-2xl bg-panel ring-1 ring-line">
        <div className="grid gap-6 p-5 sm:grid-cols-[200px_1fr] sm:p-8">
          <div className="mx-auto aspect-[2/3] w-40 overflow-hidden rounded-lg sm:w-full">
            <Poster title={hero.title} src={hero.poster_url} eager />
          </div>
          <div className="flex flex-col justify-center">
            <p className="text-xs font-semibold uppercase tracking-widest text-accent">Featured</p>
            <h1 className="mt-1 text-3xl font-extrabold sm:text-5xl">{hero.title}</h1>
            <p className="mt-2 text-sm text-muted">
              {[hero.release_year, hero.language?.name, formatDuration(hero.duration), ...hero.genres.map((g) => g.name)]
                .filter(Boolean)
                .join(" · ")}
            </p>
            <div className="mt-6 flex gap-3">
              <Link
                href={hero.has_video ? `/watch/${hero.slug}` : `/movie/${hero.slug}`}
                className="rounded-md bg-accent px-5 py-2.5 font-semibold text-accent-ink hover:brightness-110"
              >
                {hero.has_video ? "▶ Watch now" : "View details"}
              </Link>
              <Link href={`/movie/${hero.slug}`} className="rounded-md border border-line px-5 py-2.5 font-semibold hover:bg-panel-2">
                More info
              </Link>
            </div>
          </div>
        </div>
      </section>

      <MovieShelf title="Featured" movies={featured} eager />
      <MovieShelf title="Trending this week" movies={trending} />
      <MovieShelf title="Latest movies" movies={latest} href="/latest" />

      <section aria-labelledby="languages-heading" className="mt-10">
        <h2 id="languages-heading" className="mb-3 text-lg font-bold sm:text-xl">Browse by language</h2>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-7">
          {languages.map((lang) => (
            <Link
              key={lang.code}
              href={`/language/${lang.code}`}
              className="rounded-lg bg-panel px-4 py-3 ring-1 ring-line hover:ring-accent"
            >
              <span className="block font-semibold">{lang.name}</span>
              <span className="text-xs text-muted">{lang.movie_count} movies</span>
            </Link>
          ))}
        </div>
      </section>

      <section aria-labelledby="genres-heading" className="mt-10">
        <h2 id="genres-heading" className="mb-3 text-lg font-bold sm:text-xl">Browse by genre</h2>
        <div className="flex flex-wrap gap-2">
          {genres.map((g) => (
            <Link
              key={g.slug}
              href={`/genre/${g.slug}`}
              className="rounded-full border border-line px-4 py-1.5 text-sm hover:border-accent hover:text-accent"
            >
              {g.name} <span className="text-muted">({g.movie_count})</span>
            </Link>
          ))}
        </div>
      </section>
    </>
  );
}
