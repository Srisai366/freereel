import shutil
import subprocess
from pathlib import Path

import pytest

from app.core.config import get_settings
from app.database.session import SessionLocal
from app.models import JobStatus, MovieStatus, ProcessingJob
from app.services import video
from app.services.video import ProbeResult, VideoProcessingError
from app.workers import video_worker
from tests.conftest import FAKE_MP4

INFO_1080 = ProbeResult(duration=120.0, width=1920, height=1080, video_codec="h264", has_audio=True)


@pytest.mark.parametrize(
    "height,expected",
    [(2160, ["360p", "480p", "720p", "1080p"]), (1080, ["360p", "480p", "720p", "1080p"]),
     (720, ["360p", "480p", "720p"]), (480, ["360p", "480p"]), (360, ["360p"]), (240, ["240p"])],
)  # fmt: skip
def test_select_renditions_never_upscales(height, expected):
    assert [r.name for r in video.select_renditions(height)] == expected


def test_master_playlist():
    playlist = video.master_playlist(INFO_1080, video.select_renditions(720))
    lines = playlist.strip().splitlines()
    assert lines[0] == "#EXTM3U"
    assert "RESOLUTION=640x360" in playlist and "RESOLUTION=1280x720" in playlist
    assert 'CODECS="avc1.4d401f,mp4a.40.2"' in playlist
    assert [line for line in lines if not line.startswith("#")] == [
        "360p/index.m3u8", "480p/index.m3u8", "720p/index.m3u8",
    ]  # fmt: skip


def test_master_playlist_without_audio():
    silent = ProbeResult(duration=60, width=1280, height=720, video_codec="h264", has_audio=False)
    assert "mp4a" not in video.master_playlist(silent, video.select_renditions(720))


def test_hls_args_are_safe_list(tmp_path):
    weird = tmp_path / "film; rm -rf ~ $(whoami).mp4"
    args = video.hls_args(weird, tmp_path, INFO_1080, video.RENDITIONS[2])
    assert isinstance(args, list)
    assert str(weird) in args  # passed as one argument, never shell-interpreted
    assert args[args.index("-hls_playlist_type") + 1] == "vod"
    assert "-map" in args and "0:a:0" in args


def test_run_reports_missing_binary(monkeypatch):
    monkeypatch.setattr(get_settings(), "ffprobe_path", "definitely-not-ffprobe-xyz")
    with pytest.raises(VideoProcessingError, match="not found"):
        video.probe(Path("x.mp4"))


# ---- worker pipeline (FFmpeg mocked) ---------------------------------------------


@pytest.fixture
def queued_job(client, admin_headers, catalog):
    movie = catalog["village"]
    resp = client.post(
        f"/api/admin/movies/{movie.id}/video",
        files={"file": ("film.mp4", FAKE_MP4, "video/mp4")},
        headers=admin_headers,
    )
    assert resp.status_code == 202
    return resp.json()["id"], movie.id


def _fake_pipeline(monkeypatch):
    def fake_transcode(src, out_dir, info):
        for name in ("360p", "720p"):
            (out_dir / name).mkdir(parents=True)
            (out_dir / name / "index.m3u8").write_text("#EXTM3U\n")
            (out_dir / name / "seg_00000.ts").write_bytes(b"\x47" * 188)
        (out_dir / "master.m3u8").write_text("#EXTM3U\n")
        return ["360p", "720p"]

    monkeypatch.setattr(video, "probe", lambda src: ProbeResult(5400.4, 1280, 720, "h264", True))
    monkeypatch.setattr(video, "transcode_to_hls", fake_transcode)
    monkeypatch.setattr(
        video, "extract_thumbnail", lambda src, dest, info: dest.write_bytes(b"\xff\xd8\xff")
    )


def test_worker_processes_and_publishes(client, queued_job, monkeypatch):
    _fake_pipeline(monkeypatch)
    job_id, movie_id = queued_job
    assert video_worker.run_once() is True
    assert video_worker.run_once() is False  # queue now empty

    with SessionLocal() as db:
        job = db.get(ProcessingJob, job_id)
        assert job.status == JobStatus.SUCCEEDED and job.attempts == 1
        movie = job.movie
        assert movie.status == MovieStatus.PUBLISHED
        assert movie.video_format == "hls" and movie.video_quality == "360p,720p"
        assert movie.duration == 5400
        assert movie.video_url.endswith(f"/movies/{movie_id}/hls/{job_id}/master.m3u8")
        assert movie.storage_bytes > 0

    detail = client.get(f"/api/movies/{movie_id}").json()
    assert detail["has_video"] is True and detail["video_quality"] == ["360p", "720p"]
    master = client.get(detail["video_url"].replace("http://testserver", ""))
    assert master.status_code == 200
    assert master.headers["content-type"].startswith("application/vnd.apple.mpegurl")


def test_reprocessing_replaces_old_hls(client, admin_headers, queued_job, monkeypatch):
    _fake_pipeline(monkeypatch)
    first_job, movie_id = queued_job
    video_worker.run_once()
    client.post(
        f"/api/admin/movies/{movie_id}/video",
        files={"file": ("film2.mp4", FAKE_MP4, "video/mp4")},
        headers=admin_headers,
    )
    video_worker.run_once()
    hls_root = get_settings().public_storage_dir / "movies" / str(movie_id) / "hls"
    assert [p.name for p in hls_root.iterdir()] == [str(first_job + 1)]


def test_worker_failure_marks_job_and_movie(client, queued_job, monkeypatch):
    def broken_probe(src):
        raise VideoProcessingError("file has no video stream")

    monkeypatch.setattr(video, "probe", broken_probe)
    job_id, movie_id = queued_job
    video_worker.run_once()
    with SessionLocal() as db:
        job = db.get(ProcessingJob, job_id)
        assert job.status == JobStatus.FAILED
        assert "no video stream" in job.error
        assert job.movie.status == MovieStatus.FAILED
    assert client.get(f"/api/movies/{movie_id}").status_code == 404
    assert list(Path(get_settings().upload_tmp_dir).glob("job*")) == []  # workdir cleaned


def test_stale_running_job_is_requeued(queued_job, monkeypatch):
    job_id, _ = queued_job
    with SessionLocal() as db:
        job = db.get(ProcessingJob, job_id)
        job.status = JobStatus.RUNNING
        job.started_at = None
        db.commit()
    _fake_pipeline(monkeypatch)
    assert video_worker.run_once() is True
    with SessionLocal() as db:
        assert db.get(ProcessingJob, job_id).status == JobStatus.SUCCEEDED


# ---- real FFmpeg (runs only when FFmpeg is installed) -------------------------------

HAVE_FFMPEG = shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None


@pytest.mark.skipif(not HAVE_FFMPEG, reason="FFmpeg not installed")
def test_real_ffmpeg_pipeline(tmp_path):
    src = tmp_path / "sample.mp4"
    subprocess.run(
        ["ffmpeg", "-hide_banner", "-y", "-f", "lavfi", "-i", "testsrc=duration=4:size=854x480:rate=24",
         "-f", "lavfi", "-i", "sine=frequency=440:duration=4", "-shortest",
         "-c:v", "libx264", "-c:a", "aac", str(src)],
        check=True, capture_output=True,
    )  # fmt: skip
    info = video.probe(src)
    assert (info.width, info.height, info.has_audio) == (854, 480, True)
    out = tmp_path / "hls"
    out.mkdir()
    assert video.transcode_to_hls(src, out, info) == ["360p", "480p"]
    assert (out / "master.m3u8").is_file()
    assert list((out / "480p").glob("seg_*.ts"))
    thumb = tmp_path / "t.jpg"
    video.extract_thumbnail(src, thumb, info)
    assert thumb.read_bytes()[:3] == b"\xff\xd8\xff"
