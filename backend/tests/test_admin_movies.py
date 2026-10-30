from pathlib import Path

from app.core.config import get_settings
from app.models import AuditLog, JobStatus, Movie, MovieStatus, ProcessingJob
from tests.conftest import FAKE_MP4, png_bytes


def _create(client, headers, **body):
    payload = {"title": "My Film", "release_year": 1955, **body}
    return client.post("/api/admin/movies", json=payload, headers=headers)


def test_create_movie(client, admin_headers, catalog, db):
    drama = db.query(Movie).first().genres[0]
    resp = _create(
        client, admin_headers, title="  The   Open Road ", description="A trip.",
        language_id=catalog["village"].language_id, genre_ids=[drama.id],
        cast_members=["A. Actor", " ", "B. Actor"], status="published",
    )  # fmt: skip
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["title"] == "The Open Road"
    assert body["slug"] == "the-open-road-1955"
    assert body["cast_members"] == ["A. Actor", "B. Actor"]
    assert body["status"] == "published" and body["published_at"]
    assert body["genres"][0]["id"] == drama.id
    assert client.get(f"/api/movies/{body['slug']}").status_code == 200
    assert db.query(AuditLog).filter_by(action="movie.create").count() == 1


def test_create_draft_is_not_public(client, admin_headers):
    slug = _create(client, admin_headers).json()["slug"]
    assert client.get(f"/api/movies/{slug}").status_code == 404


def test_duplicate_titles_get_unique_slugs(client, admin_headers):
    first = _create(client, admin_headers).json()["slug"]
    second = _create(client, admin_headers).json()["slug"]
    assert first == "my-film-1955" and second == "my-film-1955-2"


def test_explicit_duplicate_slug_conflicts(client, admin_headers):
    _create(client, admin_headers, slug="custom-slug")
    assert _create(client, admin_headers, slug="custom-slug").status_code == 409


def test_create_validation(client, admin_headers):
    assert _create(client, admin_headers, title="").status_code == 422
    assert _create(client, admin_headers, title="   ").status_code == 422
    assert _create(client, admin_headers, release_year=1500).status_code == 422
    assert _create(client, admin_headers, slug="Bad Slug!").status_code == 422
    assert _create(client, admin_headers, slug="12345").status_code == 422
    assert _create(client, admin_headers, genre_ids=[999]).status_code == 422
    assert _create(client, admin_headers, language_id=999).status_code == 422
    assert _create(client, admin_headers, video_url="javascript:alert(1)").status_code == 422
    assert _create(client, admin_headers, video_url="http://evil.example/x.m3u8").status_code == 422


def test_validation_errors_do_not_echo_input(client, admin_headers):
    resp = _create(client, admin_headers, release_year="<script>alert(1)</script>")
    assert resp.status_code == 422
    assert "<script>" not in resp.text


def test_external_video_url(client, admin_headers):
    body = _create(client, admin_headers, video_url="https://cdn.example.com/a/master.m3u8").json()
    assert body["video_format"] == "hls" and body["has_video"] is True


def test_update_movie(client, admin_headers, catalog):
    movie = catalog["draft"]
    resp = client.put(
        f"/api/admin/movies/{movie.id}",
        json={
            "title": "No Longer Secret",
            "status": "published",
            "featured": True,
            "genre_ids": [],
        },
        headers=admin_headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["title"] == "No Longer Secret" and body["featured"] is True
    assert body["status"] == "published" and body["published_at"]
    assert body["genres"] == []
    assert body["slug"] == movie.slug  # slug is stable unless changed explicitly
    assert client.get(f"/api/movies/{movie.slug}").status_code == 200


def test_update_slug_conflict_and_missing(client, admin_headers, catalog):
    resp = client.put(
        f"/api/admin/movies/{catalog['draft'].id}",
        json={"slug": catalog["night"].slug},
        headers=admin_headers,
    )
    assert resp.status_code == 409
    assert client.put("/api/admin/movies/9999", json={}, headers=admin_headers).status_code == 404


def test_admin_list_includes_drafts_and_filters(client, admin_headers, catalog):
    all_movies = client.get("/api/admin/movies", headers=admin_headers).json()
    assert all_movies["total"] == 5
    drafts = client.get(
        "/api/admin/movies", params={"status": "draft"}, headers=admin_headers
    ).json()
    assert [m["title"] for m in drafts["items"]] == ["Secret Draft"]


def test_delete_movie_removes_files(client, admin_headers, catalog):
    movie = catalog["village"]
    poster = client.post(
        f"/api/admin/movies/{movie.id}/poster",
        files={"file": ("p.png", png_bytes(), "image/png")},
        headers=admin_headers,
    )
    assert poster.status_code == 200
    movie_dir = get_settings().public_storage_dir / "movies" / str(movie.id)
    assert movie_dir.exists()

    assert client.delete(f"/api/admin/movies/{movie.id}", headers=admin_headers).status_code == 204
    assert client.get(f"/api/admin/movies/{movie.id}", headers=admin_headers).status_code == 404
    assert not movie_dir.exists()


# ---- uploads -------------------------------------------------------------------


def test_poster_upload_is_reencoded_to_webp(client, admin_headers, catalog):
    movie = catalog["village"]
    resp = client.post(
        f"/api/admin/movies/{movie.id}/poster",
        files={"file": ("poster.png", png_bytes(size=(1200, 1800)), "image/png")},
        headers=admin_headers,
    )
    assert resp.status_code == 200, resp.text
    url = resp.json()["poster_url"]
    assert url.startswith("http://testserver/media/movies/") and url.endswith(".webp")

    stored = client.get(url.replace("http://testserver", ""))
    assert stored.status_code == 200
    assert stored.content[:4] == b"RIFF" and stored.content[8:12] == b"WEBP"

    from io import BytesIO

    from PIL import Image

    with Image.open(BytesIO(stored.content)) as img:
        assert img.size[0] <= 600 and img.size[1] <= 900


def test_replacing_poster_deletes_old_file(client, admin_headers, catalog):
    movie = catalog["village"]
    url = f"/api/admin/movies/{movie.id}/poster"
    first = client.post(
        url, files={"file": ("a.png", png_bytes(), "image/png")}, headers=admin_headers
    )
    second = client.post(
        url, files={"file": ("b.png", png_bytes(), "image/png")}, headers=admin_headers
    )
    old = first.json()["poster_url"].replace("http://testserver", "")
    new = second.json()["poster_url"].replace("http://testserver", "")
    assert client.get(old).status_code == 404
    assert client.get(new).status_code == 200


def test_poster_rejects_disguised_file(client, admin_headers, catalog):
    resp = client.post(
        f"/api/admin/movies/{catalog['village'].id}/poster",
        files={"file": ("evil.png", b"<?php system($_GET['c']); ?>", "image/png")},
        headers=admin_headers,
    )
    assert resp.status_code == 415


def test_poster_rejects_truncated_image(client, admin_headers, catalog):
    resp = client.post(
        f"/api/admin/movies/{catalog['village'].id}/poster",
        files={"file": ("broken.png", png_bytes()[:40], "image/png")},
        headers=admin_headers,
    )
    assert resp.status_code == 415


def test_poster_rejects_bad_extension(client, admin_headers, catalog):
    resp = client.post(
        f"/api/admin/movies/{catalog['village'].id}/poster",
        files={"file": ("poster.svg", b"<svg onload=alert(1)>", "image/svg+xml")},
        headers=admin_headers,
    )
    assert resp.status_code == 415


def test_poster_too_large(client, admin_headers, catalog):
    big = png_bytes() + b"\x00" * (1024 * 1024 + 10)  # limit is 1 MB in tests
    resp = client.post(
        f"/api/admin/movies/{catalog['village'].id}/poster",
        files={"file": ("big.png", big, "image/png")},
        headers=admin_headers,
    )
    assert resp.status_code == 413


def test_video_upload_queues_job(client, admin_headers, catalog, db):
    movie = catalog["village"]
    resp = client.post(
        f"/api/admin/movies/{movie.id}/video",
        files={"file": ("film.mp4", FAKE_MP4, "video/mp4")},
        headers=admin_headers,
    )
    assert resp.status_code == 202, resp.text
    job = db.get(ProcessingJob, resp.json()["id"])
    assert job.status == JobStatus.QUEUED
    db.refresh(movie)
    assert movie.status == MovieStatus.PROCESSING
    # Original is stored privately, not under the public /media root.
    settings = get_settings()
    assert (settings.private_storage_dir / job.source_key).is_file()
    assert not (settings.public_storage_dir / job.source_key).exists()
    assert client.get(f"/media/{job.source_key}").status_code == 404
    # Temp upload files are cleaned up.
    assert list(Path(settings.upload_tmp_dir).glob("*.mp4")) == []

    detail = client.get(f"/api/admin/movies/{movie.id}", headers=admin_headers).json()
    assert detail["latest_job"]["status"] == "queued"


def test_video_upload_keeps_published_movie_live(client, admin_headers, catalog, db):
    movie = catalog["night"]  # already has a playable stream
    client.post(
        f"/api/admin/movies/{movie.id}/video",
        files={"file": ("film.mp4", FAKE_MP4, "video/mp4")},
        headers=admin_headers,
    )
    db.refresh(movie)
    assert movie.status == MovieStatus.PUBLISHED


def test_video_rejects_wrong_content(client, admin_headers, catalog):
    resp = client.post(
        f"/api/admin/movies/{catalog['village'].id}/video",
        files={"file": ("film.mp4", b"MZ\x90\x00 this is an exe" * 100, "video/mp4")},
        headers=admin_headers,
    )
    assert resp.status_code == 415


def test_video_rejects_wrong_extension(client, admin_headers, catalog):
    resp = client.post(
        f"/api/admin/movies/{catalog['village'].id}/video",
        files={"file": ("film.exe", FAKE_MP4, "application/octet-stream")},
        headers=admin_headers,
    )
    assert resp.status_code == 415


def test_video_too_large_rejected_by_content_length(client, admin_headers, catalog):
    resp = client.post(
        f"/api/admin/movies/{catalog['village'].id}/video",
        files={"file": ("film.mp4", FAKE_MP4 + b"\x00" * (4 * 1024 * 1024), "video/mp4")},
        headers=admin_headers,
    )
    assert resp.status_code == 413


def test_empty_upload_rejected(client, admin_headers, catalog):
    resp = client.post(
        f"/api/admin/movies/{catalog['village'].id}/video",
        files={"file": ("film.mp4", b"", "video/mp4")},
        headers=admin_headers,
    )
    assert resp.status_code == 400


def test_retry_failed_job(client, admin_headers, catalog, db):
    movie = catalog["village"]
    job = ProcessingJob(movie_id=movie.id, source_key="originals/x.mp4", status=JobStatus.FAILED,
                        error="boom", attempts=1)  # fmt: skip
    db.add(job)
    db.commit()
    resp = client.post(f"/api/admin/jobs/{job.id}/retry", headers=admin_headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "queued" and resp.json()["error"] is None
    assert client.post(f"/api/admin/jobs/{job.id}/retry", headers=admin_headers).status_code == 409
