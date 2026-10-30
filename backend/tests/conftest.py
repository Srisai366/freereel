import io
import os
import shutil
import tempfile
from pathlib import Path

# Configure the environment before any app module reads settings.
_TMP = Path(tempfile.mkdtemp(prefix="freereel-tests-"))
os.environ.update(
    ENVIRONMENT="test",
    DATABASE_URL=f"sqlite:///{(_TMP / 'test.db').as_posix()}",
    SECRET_KEY="test-secret-key-0123456789-abcdefghijklmnop",
    LOCAL_STORAGE_DIR=str(_TMP / "storage"),
    UPLOAD_TMP_DIR=str(_TMP / "uploads"),
    MEDIA_PUBLIC_BASE_URL="http://testserver/media",
    CORS_ORIGINS="http://localhost:3000",
    RATE_LIMIT_PER_MINUTE="100000",
    LOGIN_RATE_LIMIT_PER_MINUTE="5",
    MAX_POSTER_MB="1",
    MAX_VIDEO_MB="2",
    RUN_WORKER_IN_PROCESS="false",
)

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from PIL import Image  # noqa: E402

from app.core.middleware import limiter  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.database.base import Base, utcnow  # noqa: E402
from app.database.session import SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import AdminUser, Genre, Language, Movie, MovieStatus  # noqa: E402

ADMIN_PASSWORD = "correct-horse-battery-staple"
# Minimal ISO-BMFF header: the bytes 4..8 are "ftyp", which is what upload sniffing checks.
FAKE_MP4 = b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isom" + b"\x00" * 2048


@pytest.fixture(autouse=True)
def _fresh_db():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    limiter.reset()
    yield


def pytest_sessionfinish(session, exitstatus):
    engine.dispose()
    shutil.rmtree(_TMP, ignore_errors=True)


@pytest.fixture
def db():
    with SessionLocal() as session:
        yield session


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def _make_admin(db, username: str, role: str, active: bool = True) -> AdminUser:
    admin = AdminUser(
        username=username, password_hash=hash_password(ADMIN_PASSWORD), role=role, is_active=active
    )
    db.add(admin)
    db.commit()
    return admin


def _login(client, username: str) -> dict:
    resp = client.post("/api/admin/login", json={"username": username, "password": ADMIN_PASSWORD})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


@pytest.fixture
def admin_user(db):
    return _make_admin(db, "admin", "admin")


@pytest.fixture
def admin_headers(client, admin_user):
    return _login(client, "admin")


@pytest.fixture
def editor_headers(client, db):
    _make_admin(db, "editor", "editor")
    return _login(client, "editor")


@pytest.fixture
def catalog(db):
    """Two languages, three genres, four published movies, one draft."""
    tamil = Language(name="Tamil", code="ta")
    english = Language(name="English", code="en")
    drama = Genre(name="Drama", slug="drama")
    comedy = Genre(name="Comedy", slug="comedy")
    horror = Genre(name="Horror", slug="horror")
    db.add_all([tamil, english, drama, comedy, horror])
    db.flush()

    def movie(title, year, lang, genres, featured=False, status=MovieStatus.PUBLISHED, **kw):
        m = Movie(
            title=title,
            slug=f"{title.lower().replace(' ', '-')}-{year}",
            release_year=year,
            language=lang,
            genres=genres,
            featured=featured,
            status=status,
            published_at=utcnow() if status == MovieStatus.PUBLISHED else None,
            **kw,
        )
        db.add(m)
        db.flush()
        return m

    movies = {
        "village": movie("Village Story", 1950, tamil, [drama]),
        "laugh": movie("Laugh Riot", 1961, english, [comedy], featured=True, director="Jane Doe"),
        "night": movie(
            "Night Terror",
            1968,
            english,
            [horror, drama],
            video_url="https://cdn.example.com/n/master.m3u8",
            video_format="hls",
            video_quality="360p,720p",
        ),  # fmt: skip
        "river": movie("River Song 100%", 1950, tamil, [drama, comedy], cast_members=["Asha Rao"]),
        "draft": movie("Secret Draft", 2020, english, [drama], status=MovieStatus.DRAFT),
    }
    db.commit()
    return movies


def png_bytes(size=(300, 450), color=(200, 30, 30)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, "PNG")
    return buf.getvalue()
