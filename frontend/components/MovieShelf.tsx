import Link from "next/link";

import MovieCard from "@/components/MovieCard";
import type { MovieCard as Movie } from "@/services/types";

interface Props {
  title: string;
  movies: Movie[];
  href?: string;
  eager?: boolean;
}

export default function MovieShelf({ title, movies, href, eager = false }: Props) {
  if (!movies.length) return null;
  return (
    <section aria-labelledby={`shelf-${title}`} className="mt-10">
      <div className="mb-3 flex items-baseline justify-between">
        <h2 id={`shelf-${title}`} className="text-lg font-bold sm:text-xl">
          {title}
        </h2>
        {href && (
          <Link href={href} className="text-sm text-muted hover:text-accent">
            See all →
          </Link>
        )}
      </div>
      <div className="shelf -mx-4 flex gap-3 overflow-x-auto px-4 pb-2 sm:gap-4">
        {movies.map((m, i) => (
          <div key={m.id} className="w-[38%] shrink-0 sm:w-[22%] lg:w-[15%]">
            <MovieCard movie={m} eager={eager && i < 4} />
          </div>
        ))}
      </div>
    </section>
  );
}
