import Link from "next/link";

import MovieCard from "@/components/MovieCard";
import type { MoviePage } from "@/services/types";

interface Props {
  page: MoviePage;
  /** Builds the URL for another page number, keeping the current filters. */
  hrefFor: (page: number) => string;
  emptyText?: string;
}

export default function MovieGrid({ page, hrefFor, emptyText = "No movies found." }: Props) {
  if (!page.items.length) {
    return <p className="py-16 text-center text-muted" data-testid="empty-results">{emptyText}</p>;
  }
  return (
    <>
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4 lg:grid-cols-6">
        {page.items.map((m, i) => (
          <MovieCard key={m.id} movie={m} eager={i < 6} />
        ))}
      </div>
      {page.pages > 1 && (
        <nav aria-label="Pagination" className="mt-8 flex items-center justify-center gap-3 text-sm">
          {page.page > 1 ? (
            <Link href={hrefFor(page.page - 1)} className="rounded-md border border-line px-4 py-2 hover:border-accent">
              ← Previous
            </Link>
          ) : (
            <span className="rounded-md border border-line px-4 py-2 opacity-40">← Previous</span>
          )}
          <span className="text-muted">
            Page {page.page} of {page.pages}
          </span>
          {page.page < page.pages ? (
            <Link href={hrefFor(page.page + 1)} className="rounded-md border border-line px-4 py-2 hover:border-accent">
              Next →
            </Link>
          ) : (
            <span className="rounded-md border border-line px-4 py-2 opacity-40">Next →</span>
          )}
        </nav>
      )}
    </>
  );
}

export function pageNumber(value: string | string[] | undefined): number {
  const n = Number(Array.isArray(value) ? value[0] : value);
  return Number.isInteger(n) && n > 0 ? n : 1;
}
