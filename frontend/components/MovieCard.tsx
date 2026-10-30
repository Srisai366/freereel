import Link from "next/link";

import Poster from "@/components/Poster";
import type { MovieCard as Movie } from "@/services/types";

function topQuality(qualities: string[]): string | null {
  const numeric = qualities.map((q) => parseInt(q, 10)).filter((n) => !Number.isNaN(n));
  if (numeric.length) return `${Math.max(...numeric)}p`;
  return qualities.includes("auto") ? "HD" : null;
}

export default function MovieCard({ movie, eager = false }: { movie: Movie; eager?: boolean }) {
  const quality = topQuality(movie.video_quality);
  return (
    <Link
      href={`/movie/${movie.slug}`}
      className="group block w-full"
      data-testid="movie-card"
    >
      <div className="relative aspect-[2/3] overflow-hidden rounded-lg bg-panel ring-1 ring-line transition group-hover:ring-accent">
        <Poster title={movie.title} src={movie.poster_url} eager={eager} className="transition duration-300 group-hover:scale-105" />
        {quality && (
          <span className="absolute right-2 top-2 rounded bg-accent px-1.5 py-0.5 text-[10px] font-bold text-accent-ink">
            {quality}
          </span>
        )}
        {!movie.has_video && (
          <span className="absolute left-2 top-2 rounded bg-black/70 px-1.5 py-0.5 text-[10px] font-medium text-muted">
            Coming soon
          </span>
        )}
      </div>
      <h3 className="mt-2 line-clamp-1 text-sm font-semibold group-hover:text-accent">{movie.title}</h3>
      <p className="line-clamp-1 text-xs text-muted">
        {[movie.release_year, movie.language?.name, movie.genres[0]?.name].filter(Boolean).join(" · ")}
      </p>
    </Link>
  );
}
