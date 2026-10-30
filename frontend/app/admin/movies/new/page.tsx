"use client";

import { useRouter } from "next/navigation";

import MovieForm from "@/components/admin/MovieForm";

export default function NewMoviePage() {
  const router = useRouter();
  return (
    <div className="max-w-3xl">
      <h1 className="mb-1 text-2xl font-extrabold">Add movie</h1>
      <p className="mb-6 text-sm text-muted">
        Step 1 of 2: enter the details. Next you&apos;ll upload the poster and the video file.
      </p>
      <MovieForm onSaved={(movie) => router.push(`/admin/movies/${movie.id}?created=1`)} />
    </div>
  );
}
