import type { Metadata } from "next";
import { notFound } from "next/navigation";

import MovieGrid, { pageNumber } from "@/components/MovieGrid";
import { api } from "@/services/api";

interface Props {
  params: Promise<{ slug: string }>;
  searchParams: Promise<{ page?: string }>;
}

async function findGenre(slug: string) {
  const genres = await api.genres();
  return genres.find((g) => g.slug === slug);
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const genre = await findGenre((await params).slug);
  return genre ? { title: `${genre.name} movies`, description: `Watch free ${genre.name} movies online.` } : {};
}

export default async function GenrePage({ params, searchParams }: Props) {
  const { slug } = await params;
  const page = pageNumber((await searchParams).page);
  const genre = await findGenre(slug);
  if (!genre) notFound();
  const movies = await api.movies({ genre: slug, page, page_size: 24 });

  return (
    <div className="py-8">
      <h1 className="mb-6 text-2xl font-extrabold sm:text-3xl">{genre.name}</h1>
      <MovieGrid page={movies} hrefFor={(p) => `/genre/${slug}?page=${p}`} />
    </div>
  );
}
