import type { Metadata } from "next";
import Link from "next/link";

import MovieShelf from "@/components/MovieShelf";
import Poster from "@/components/Poster";
import { api, formatDuration, safe } from "@/services/api";
import { loadMovie } from "@/services/movie";

interface Props {
  params: Promise<{ slug: string }>;
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const movie = await loadMovie((await params).slug);
  const title = movie.release_year ? `${movie.title} (${movie.release_year})` : movie.title;
  const description = movie.description.slice(0, 160) || `Watch ${movie.title} free and legally.`;
  return {
    title,
    description,
    alternates: { canonical: `/movie/${movie.slug}` },
    openGraph: {
      type: "video.movie",
      title,
      description,
      images: movie.poster_url ? [{ url: movie.poster_url }] : undefined,
    },
  };
}

export default async function MovieDetailsPage({ params }: Props) {
  const movie = await loadMovie((await params).slug);
  const firstGenre = movie.genres[0]?.slug;
  const related = firstGenre
    ? (await safe(api.movies({ genre: firstGenre, page_size: 12 }), null))?.items.filter((m) => m.id !== movie.id) ?? []
    : [];

  const facts: [string, string | null][] = [
    ["Year", movie.release_year ? String(movie.release_year) : null],
    ["Language", movie.language?.name ?? null],
    ["Duration", formatDuration(movie.duration)],
    ["Genre", movie.genres.map((g) => g.name).join(", ") || null],
    ["Quality", movie.video_quality.filter((q) => q !== "auto").join(", ") || (movie.has_video ? "Adaptive" : null)],
    ["Director", movie.director],
    ["Cast", movie.cast_members.join(", ") || null],
    ["Rights", movie.license],
  ];

  // JSON-LD helps search engines show rich results for the film.
  const jsonLd = {
    "@context": "https://schema.org",
    "@type": "Movie",
    name: movie.title,
    description: movie.description,
    dateCreated: movie.release_year ? String(movie.release_year) : undefined,
    image: movie.poster_url ?? undefined,
    director: movie.director ? { "@type": "Person", name: movie.director } : undefined,
    actor: movie.cast_members.map((name) => ({ "@type": "Person", name })),
    genre: movie.genres.map((g) => g.name),
  };

  return (
    <article className="py-8">
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd).replace(/</g, "\\u003c") }} />
      <div className="grid gap-8 sm:grid-cols-[240px_1fr]">
        <div className="mx-auto aspect-[2/3] w-48 overflow-hidden rounded-xl ring-1 ring-line sm:w-full">
          <Poster title={movie.title} src={movie.poster_url} eager />
        </div>
        <div>
          <h1 className="text-3xl font-extrabold sm:text-4xl">{movie.title}</h1>
          <p className="mt-2 text-sm text-muted">
            {[movie.release_year, movie.language?.name, formatDuration(movie.duration)].filter(Boolean).join(" · ")}
          </p>

          <div className="mt-5">
            {movie.has_video ? (
              <Link
                href={`/watch/${movie.slug}`}
                className="inline-block rounded-md bg-accent px-6 py-3 font-semibold text-accent-ink hover:brightness-110"
                data-testid="watch-now"
              >
                ▶ Watch now
              </Link>
            ) : (
              <span className="inline-block rounded-md border border-line px-6 py-3 text-muted">
                Video coming soon
              </span>
            )}
          </div>

          {movie.description && <p className="mt-6 max-w-3xl leading-relaxed">{movie.description}</p>}

          <dl className="mt-6 grid max-w-3xl grid-cols-[110px_1fr] gap-x-4 gap-y-2 text-sm">
            {facts
              .filter(([, value]) => value)
              .map(([label, value]) => (
                <div key={label} className="contents">
                  <dt className="text-muted">{label}</dt>
                  <dd>{value}</dd>
                </div>
              ))}
          </dl>
        </div>
      </div>

      <MovieShelf title="More like this" movies={related} />
    </article>
  );
}
