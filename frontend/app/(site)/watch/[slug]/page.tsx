import type { Metadata } from "next";
import Link from "next/link";

import VideoPlayer from "@/components/VideoPlayer";
import { loadMovie } from "@/services/movie";

interface Props {
  params: Promise<{ slug: string }>;
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const movie = await loadMovie((await params).slug);
  // The details page is the canonical, indexable URL for each film.
  return { title: `Watch ${movie.title}`, alternates: { canonical: `/movie/${movie.slug}` }, robots: { index: false } };
}

export default async function WatchPage({ params }: Props) {
  const movie = await loadMovie((await params).slug);

  return (
    <div className="py-6">
      <Link href={`/movie/${movie.slug}`} className="text-sm text-muted hover:text-accent">
        ← Back to {movie.title}
      </Link>
      <h1 className="mb-4 mt-2 text-xl font-bold sm:text-2xl">{movie.title}</h1>
      {movie.video_url ? (
        <VideoPlayer src={movie.video_url} title={movie.title} movieId={movie.id} poster={movie.thumbnail_url ?? movie.poster_url} />
      ) : (
        <div className="grid aspect-video place-items-center rounded-xl bg-panel text-muted ring-1 ring-line">
          This video is still being prepared. Please check back soon.
        </div>
      )}
      {movie.license && <p className="mt-3 text-xs text-muted">Rights: {movie.license}</p>}
    </div>
  );
}
