"""Video processing worker.

Run as its own process (production, or on the admin's laptop against the cloud DB + R2):

    python -m app.workers.video_worker          # loop forever
    python -m app.workers.video_worker --once   # process at most one job and exit

Or set RUN_WORKER_IN_PROCESS=true to run it as a thread inside the API (dev convenience).
"""

import argparse
import logging
import shutil
import tempfile
import threading
from datetime import timedelta
from pathlib import Path

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.database.base import utcnow
from app.database.session import SessionLocal
from app.models import JobStatus, MovieStatus, ProcessingJob
from app.services import video
from app.services.storage import Storage, get_storage

logger = logging.getLogger("app.worker")


def recover_stale_jobs(db: Session) -> None:
    """Requeue jobs whose worker died mid-run (crash, laptop closed, deploy)."""
    settings = get_settings()
    cutoff = utcnow() - timedelta(seconds=settings.ffmpeg_timeout_seconds + 600)
    stale = db.scalars(
        select(ProcessingJob).where(
            ProcessingJob.status == JobStatus.RUNNING,
            or_(ProcessingJob.started_at.is_(None), ProcessingJob.started_at < cutoff),
        )
    ).all()
    for job in stale:
        if job.attempts >= settings.worker_max_attempts:
            job.status = JobStatus.FAILED
            job.error = "worker stopped responding too many times"
            job.finished_at = utcnow()
        else:
            job.status = JobStatus.QUEUED
        logger.warning("recovered stale job", extra={"job_id": job.id})
    db.commit()


def claim_next_job(db: Session) -> int | None:
    stmt = (
        select(ProcessingJob)
        .where(ProcessingJob.status == JobStatus.QUEUED)
        .order_by(ProcessingJob.id)
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    job = db.scalar(stmt)
    if job is None:
        db.rollback()
        return None
    job.status = JobStatus.RUNNING
    job.started_at = utcnow()
    job.attempts += 1
    db.commit()
    return job.id


def run_job(job_id: int, storage: Storage | None = None) -> bool:
    """Process one claimed job. Returns True on success. Never raises."""
    settings = get_settings()
    storage = storage or get_storage()
    tmp_root = Path(settings.upload_tmp_dir)
    tmp_root.mkdir(parents=True, exist_ok=True)
    workdir = Path(tempfile.mkdtemp(prefix=f"job{job_id}-", dir=tmp_root))
    log = {"job_id": job_id}

    with SessionLocal() as db:
        job = db.get(ProcessingJob, job_id)
        if job is None:
            return False
        movie = job.movie
        log["movie_id"] = movie.id
        try:
            src = workdir / f"source{Path(job.source_key).suffix}"
            storage.get_file(job.source_key, src, public=False)

            info = video.probe(src)
            logger.info("probed %sx%s %.0fs", info.width, info.height, info.duration, extra=log)
            hls_dir = workdir / "hls"
            hls_dir.mkdir()
            qualities = video.transcode_to_hls(src, hls_dir, info)
            thumb = workdir / "thumbnail.jpg"
            video.extract_thumbnail(src, thumb, info)

            prefix = f"movies/{movie.id}/hls/{job.id}"
            hls_bytes = storage.put_directory(hls_dir, prefix, public=True)
            thumb_key = f"movies/{movie.id}/thumbs/{job.id}.jpg"
            thumb_bytes = storage.put_file(thumb, thumb_key, public=True)

            old_prefix, old_thumb = movie.hls_prefix, _thumb_key_from(movie.thumbnail_url, storage)
            movie.video_url = storage.public_url(f"{prefix}/master.m3u8")
            movie.video_format = "hls"
            movie.video_quality = ",".join(qualities)
            movie.thumbnail_url = storage.public_url(thumb_key)
            movie.duration = round(info.duration)
            movie.hls_prefix = prefix
            keep_original = settings.keep_originals
            movie.storage_bytes = (
                hls_bytes + thumb_bytes + (job.source_bytes if keep_original else 0)
            )
            if job.publish_on_success:
                movie.status = MovieStatus.PUBLISHED
                movie.published_at = movie.published_at or utcnow()
            job.status = JobStatus.SUCCEEDED
            job.error = None
            job.finished_at = utcnow()
            db.commit()
            logger.info("job succeeded: %s", ",".join(qualities), extra=log)

            if old_prefix and old_prefix != prefix:
                storage.safe_delete_prefix(old_prefix, public=True)
            if old_thumb and old_thumb != thumb_key:
                storage.safe_delete(old_thumb, public=True)
            if not keep_original:
                storage.safe_delete(job.source_key, public=False)
                movie.original_key = None
                db.commit()
            return True
        except Exception as exc:
            db.rollback()
            logger.exception("job failed", extra=log)
            job = db.get(ProcessingJob, job_id)
            job.status = JobStatus.FAILED
            job.error = str(exc)[:2000] or exc.__class__.__name__
            job.finished_at = utcnow()
            if not job.movie.video_url:
                job.movie.status = MovieStatus.FAILED
            db.commit()
            return False
        finally:
            shutil.rmtree(workdir, ignore_errors=True)


def _thumb_key_from(url: str | None, storage: Storage) -> str | None:
    base = storage.public_base_url + "/"
    if url and url.startswith(base):
        return url[len(base) :]
    return None


def run_once() -> bool:
    """Claim and process one job. Returns True if a job was found."""
    with SessionLocal() as db:
        recover_stale_jobs(db)
        job_id = claim_next_job(db)
    if job_id is None:
        return False
    run_job(job_id)
    return True


def run_forever(stop: threading.Event) -> None:
    interval = get_settings().worker_poll_seconds
    logger.info("video worker started (poll every %ss)", interval)
    while not stop.is_set():
        try:
            if run_once():
                continue  # immediately look for the next job
        except Exception:
            logger.exception("worker loop error")
        stop.wait(interval)
    logger.info("video worker stopped")


def start_background_worker() -> threading.Event:
    stop = threading.Event()
    threading.Thread(target=run_forever, args=(stop,), name="video-worker", daemon=True).start()
    return stop


def main(argv: list[str] | None = None) -> None:
    from app.core.logging import configure_logging

    parser = argparse.ArgumentParser(description="FreeReel video processing worker")
    parser.add_argument("--once", action="store_true", help="process at most one job and exit")
    args = parser.parse_args(argv)
    configure_logging()
    if args.once:
        found = run_once()
        logger.info("processed a job" if found else "no queued jobs")
        return
    stop = threading.Event()
    try:
        run_forever(stop)
    except KeyboardInterrupt:
        stop.set()


if __name__ == "__main__":
    main()
