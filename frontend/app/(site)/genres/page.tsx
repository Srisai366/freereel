import type { Metadata } from "next";
import Link from "next/link";

import { api, safe } from "@/services/api";

export const metadata: Metadata = { title: "Genres", description: "Browse free movies by genre." };

// Needs live API data, so don't pre-render at build time.
export const dynamic = "force-dynamic";

export default async function GenresPage() {
  const genres = await safe(api.genres(), []);
  return (
    <div className="py-8">
      <h1 className="mb-6 text-2xl font-extrabold sm:text-3xl">Genres</h1>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
        {genres.map((g) => (
          <Link
            key={g.slug}
            href={`/genre/${g.slug}`}
            className="rounded-lg bg-panel px-4 py-5 ring-1 ring-line hover:ring-accent"
          >
            <span className="block text-lg font-semibold">{g.name}</span>
            <span className="text-xs text-muted">{g.movie_count} movies</span>
          </Link>
        ))}
      </div>
    </div>
  );
}
