# FreeReel

A legal, login-free movie streaming website. Visitors open the site and watch right away.
Only administrators sign in, to manage the catalogue, uploads, ads and analytics.

> **Content rule:** only public-domain films, Creative Commons films, or titles you hold
> written streaming rights for. Public-domain status is **per country**: a film that is
> public domain in the US can still be under copyright in India or the EU. Record the rights
> basis in each movie's `license` field.

## Stack

| | |
|---|---|
| Frontend | Next.js (App Router), React, TypeScript, Tailwind CSS, hls.js |
| Backend | Python 3.13, FastAPI, Pydantic v2, SQLAlchemy 2, Alembic |
| Database | PostgreSQL (prod), SQLite (local dev / tests) |
| Video | FFmpeg → HLS (360p–1080p, only up to the source resolution), DB-backed job queue + worker |
| Storage / CDN | Cloudflare R2 + Cloudflare CDN (S3-compatible, so AWS S3 + CloudFront also work) |
| Hosting (MVP) | Cloudflare (frontend), Render (API), Supabase or Neon (Postgres), your laptop (transcoding) |

Read [docs/architecture.md](docs/architecture.md) and [docs/cost-estimation.md](docs/cost-estimation.md).
Progress is tracked in [docs/CHECKLIST.md](docs/CHECKLIST.md).

## Project layout

```
movie-streaming-platform/
├── backend/
│   ├── app/
│   │   ├── api/          public.py (visitor API), admin.py (admin API), deps.py (auth)
│   │   ├── core/         config, security (Argon2 + JWT), middleware, logging
│   │   ├── database/     engine/session, declarative base
│   │   ├── models/       movies, taxonomy, admin/audit, ads, analytics, jobs
│   │   ├── schemas/      Pydantic request/response models
│   │   ├── services/     movie queries, storage (local/S3/R2), uploads, FFmpeg, analytics
│   │   ├── workers/      video_worker.py (HLS processing loop)
│   │   └── cli.py        create-admin, seed, enqueue-video
│   ├── alembic/          migrations
│   ├── tests/            pytest suite
│   └── Dockerfile
├── frontend/
│   ├── app/              routes (App Router)
│   ├── components/       UI components
│   ├── services/         API client + types
│   └── tests/            Playwright (Phase 7)
├── docs/
├── .github/workflows/    CI
└── docker-compose.yml
```

## Local development (Windows PowerShell)

### Prerequisites

```powershell
winget install Python.Python.3.13
winget install OpenJS.NodeJS.LTS
winget install Git.Git
winget install Gyan.FFmpeg        # needed for video processing
```

Open a new terminal afterwards so the new `PATH` takes effect.

### Backend

```powershell
cd movie-streaming-platform\backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
Copy-Item .env.example .env          # then edit SECRET_KEY

alembic upgrade head                 # create tables (SQLite by default)
python -m app.cli seed               # languages, genres, 10 public-domain / CC demo films
python -m app.cli create-admin --username admin   # prompts for a password (12+ chars)

uvicorn app.main:app --reload        # http://localhost:8000/api/docs
```

In a second terminal, run the video worker:

```powershell
cd movie-streaming-platform\backend; .\.venv\Scripts\Activate.ps1
python -m app.workers.video_worker
```

Run the tests and linting:

```powershell
pytest
ruff check . ; ruff format --check .
```

### Frontend

```powershell
cd movie-streaming-platform\frontend
Copy-Item .env.example .env.local
npm install
npm run dev                          # http://localhost:3000
```

## Uploading a film

1. In the admin dashboard (or `POST /api/admin/movies`), create the movie as a **draft**.
2. Upload the original file. The API checks it, stores it privately, and queues a job (`202 Accepted`).
3. The worker probes the file, transcodes HLS renditions up to the source resolution, makes a
   thumbnail, uploads everything and publishes the movie.

To keep large files off the free-tier API server, queue them straight from your laptop:

```powershell
python -m app.cli enqueue-video --movie-id 3 "D:\films\night_of_the_living_dead.mp4"
```

## API summary

Public (no auth): `GET /api/movies`, `/api/movies/latest`, `/api/movies/featured`,
`/api/movies/trending`, `/api/movies/search?q=`, `/api/movies/{id-or-slug}`, `/api/categories`,
`/api/languages`, `/api/genres`, `/api/ads`, `/api/health`; `POST /api/events` (anonymous analytics).

Admin (Bearer token from `POST /api/admin/login`): movie CRUD, `/movies/{id}/poster`,
`/movies/{id}/video`, `/jobs`, `/languages`, `/genres`, `/ads`, `/analytics`, `/audit-logs`.
Full interactive docs: `http://localhost:8000/api/docs` (disabled in production).

## Demo seed data

`seed` adds four Blender Foundation films (CC BY) and six US/Indian public-domain classics.
*Big Buck Bunny* and *Tears of Steel* point to public HLS test streams hosted by Mux and Unified
Streaming (both responded on 2026-10-30), so playback works before you upload anything. Those
are third-party demo endpoints and may change. Replace them with your own processed uploads
before launch. The other titles have metadata only and show "Coming soon" until you upload a file.
