"use client";

import { useRouter } from "next/navigation";

import MovieForm from "@/components/admin/MovieForm";

export default function NewMoviePage() {
  const router = useRouter();
  return (
    <div className="max-w-3xl">
      <h1 className="mb-1 text-2xl font-extrabold">Add movie</h1>
      <p className="mb-6 text-sm text-muted">
        Fill in the details, choose the poster and video file, then click Create. The video is converted in the
        background and the movie goes live when it&apos;s ready.
      </p>
      <MovieForm onSaved={(movie) => router.push(`/admin/movies/${movie.id}?created=1`)} />
    </div>
  );
}
