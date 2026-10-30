import type { Metadata } from "next";

import MovieGrid, { pageNumber } from "@/components/MovieGrid";
import { api } from "@/services/api";

export const metadata: Metadata = { title: "Latest movies", description: "Recently added free movies." };

export default async function LatestPage({ searchParams }: { searchParams: Promise<{ page?: string }> }) {
  const page = pageNumber((await searchParams).page);
  const movies = await api.movies({ sort: "latest", page, page_size: 24 });
  return (
    <div className="py-8">
      <h1 className="mb-6 text-2xl font-extrabold sm:text-3xl">Latest movies</h1>
      <MovieGrid page={movies} hrefFor={(p) => `/latest?page=${p}`} />
    </div>
  );
}
