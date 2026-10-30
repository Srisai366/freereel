import type { Metadata } from "next";
import { notFound } from "next/navigation";

import MovieGrid, { pageNumber } from "@/components/MovieGrid";
import { api } from "@/services/api";

interface Props {
  params: Promise<{ code: string }>;
  searchParams: Promise<{ page?: string }>;
}

async function findLanguage(code: string) {
  const languages = await api.languages();
  return languages.find((l) => l.code === code);
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const lang = await findLanguage((await params).code);
  return lang
    ? { title: `${lang.name} movies`, description: `Watch free, legal ${lang.name} movies online.` }
    : {};
}

export default async function LanguagePage({ params, searchParams }: Props) {
  const { code } = await params;
  const page = pageNumber((await searchParams).page);
  const lang = await findLanguage(code);
  if (!lang) notFound();
  const movies = await api.movies({ language: code, page, page_size: 24 });

  return (
    <div className="py-8">
      <h1 className="mb-6 text-2xl font-extrabold sm:text-3xl">{lang.name} movies</h1>
      <MovieGrid
        page={movies}
        hrefFor={(p) => `/language/${code}?page=${p}`}
        emptyText={`No ${lang.name} movies yet. We only add films we have the rights to stream, so check back soon.`}
      />
    </div>
  );
}
