import uuid
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import JobStatus, Movie, MovieStatus, ProcessingJob
from app.services.storage import get_storage


def enqueue_video(db: Session, movie: Movie, local_path: Path, suffix: str) -> ProcessingJob:
    """Store an already-validated original privately and queue it for the worker.

    Commits. A movie that already has a playable video stays published while it is reprocessed.
    """
    key = f"originals/{movie.id}/{uuid.uuid4().hex}{suffix}"
    size = get_storage().put_file(local_path, key, public=False)
    previous_original = movie.original_key

    job = ProcessingJob(movie_id=movie.id, source_key=key, source_bytes=size)
    movie.original_key = key
    if not movie.video_url:
        movie.status = MovieStatus.PROCESSING
    db.add(job)
    db.commit()

    if previous_original and previous_original != key:
        get_storage().safe_delete(previous_original, public=False)
    return job


def latest_job(db: Session, movie_id: int) -> ProcessingJob | None:
    return db.scalar(
        select(ProcessingJob)
        .where(ProcessingJob.movie_id == movie_id)
        .order_by(ProcessingJob.id.desc())
        .limit(1)
    )


def requeue(db: Session, job: ProcessingJob) -> None:
    job.status = JobStatus.QUEUED
    job.error = None
    job.started_at = None
    job.finished_at = None
    job.attempts = 0
    if not job.movie.video_url:
        job.movie.status = MovieStatus.PROCESSING
    db.commit()
