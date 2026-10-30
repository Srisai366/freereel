# Development checklist

Legend: `[x]` done and verified · `[~]` written but not yet verified · `[ ]` not started

## Phase 1 — Architecture
- [x] Final architecture, diagrams, data flow ([architecture.md](architecture.md))
- [x] Stack selection with justification
- [x] Free-tier facts checked (2026-10-30) and cost scenarios ([cost-estimation.md](cost-estimation.md))
- [x] Folder structure and roadmap (README)

## Phase 2 — Project initialization
- [x] Repository structure
- [x] FastAPI app, settings from environment, `.env.example`
- [x] SQLAlchemy models + Alembic initial migration (SQLite dev, PostgreSQL prod)
- [~] Next.js + TypeScript + Tailwind project files (needs Node.js to install/build)
- [~] Dockerfiles + docker-compose (needs Docker to verify)

## Phase 3 — Frontend
- [~] Homepage sections (featured hero, latest, trending, recent, languages, genres, ads)
- [~] Movie cards, navigation, search with filters + pagination
- [~] Movie details page with SEO metadata / Open Graph
- [~] HLS video player (hls.js, quality menu, loading/error states, no autoplay with sound)
- [~] Responsive layouts
- [~] sitemap.xml, robots.txt

## Phase 4 — Backend
- [x] Public APIs (movies, latest, featured, trending, details, search, categories, languages, genres, health)
- [x] Admin auth (Argon2id + JWT, login rate limit, roles)
- [x] Admin APIs (movies CRUD, poster, video, taxonomy, ads, jobs, analytics, audit log)
- [x] Validation, error handling, security headers, CORS, rate limiting, body size limits

## Phase 5 — Video processing
- [x] Upload validation (extension + magic bytes + size)
- [x] DB-backed job queue + worker process (no processing inside HTTP requests)
- [x] FFmpeg HLS multi-rendition + thumbnail code; unit tested with FFmpeg mocked
- [ ] Real FFmpeg run (needs FFmpeg installed)
- [x] Storage abstraction: local + S3/R2

## Phase 6 — Admin dashboard
- [~] Login, dashboard stats, movie management, uploads, taxonomy, ads (frontend)

## Phase 7 — Testing
- [x] pytest backend suite executed
- [ ] Playwright suite executed (needs Node.js)
- [ ] Integration: real FFmpeg → HLS → playback

## Phase 8 — Deployment
- [~] GitHub Actions CI workflow (written)
- [ ] Cloudflare R2 bucket + custom domain
- [ ] Supabase/Neon database
- [ ] Render backend
- [ ] Cloudflare frontend (OpenNext)
- [ ] Domain, HTTPS, monitoring, budget alerts

## Phase 9 — Monetization & scaling
- [x] Admin-managed ad placements (API)
- [ ] AdSense application (needs live site with original content + privacy policy)
- [ ] Scaling roadmap review once real traffic exists
