import { notFound } from "next/navigation";
import { cache } from "react";

import { api, ApiError } from "@/services/api";

/** Load a movie for a page, de-duplicated between generateMetadata and the page render. */
export const loadMovie = cache(async (slug: string) => {
  try {
    return await api.movie(slug);
  } catch (err) {
    if (err instanceof ApiError && (err.status === 404 || err.status === 422)) notFound();
    throw err;
  }
});
