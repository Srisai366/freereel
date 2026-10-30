// Mirrors backend/app/schemas/movie.py — keep in sync.

export interface Language {
  id: number;
  name: string;
  code: string;
}

export interface Genre {
  id: number;
  name: string;
  slug: string;
}

export interface LanguageWithCount extends Language {
  movie_count: number;
}

export interface GenreWithCount extends Genre {
  movie_count: number;
}

export interface MovieCard {
  id: number;
  title: string;
  slug: string;
  release_year: number | null;
  duration: number | null;
  poster_url: string | null;
  thumbnail_url: string | null;
  featured: boolean;
  language: Language | null;
  genres: Genre[];
  video_quality: string[];
  has_video: boolean;
}

export interface MovieDetail extends MovieCard {
  description: string;
  director: string | null;
  cast_members: string[];
  license: string | null;
  video_url: string | null;
  video_format: string | null;
  created_at: string;
  published_at: string | null;
}

export interface MoviePage {
  items: MovieCard[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

export interface Ad {
  id: number;
  title: string;
  placement: string;
  advertisement_url: string;
  image_url: string | null;
}
