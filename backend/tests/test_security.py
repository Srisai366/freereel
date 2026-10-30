import pytest

from app.core.config import Settings, get_settings
from app.services.storage import validate_key


def test_security_headers(client):
    headers = client.get("/api/health").headers
    assert headers["x-content-type-options"] == "nosniff"
    assert headers["x-frame-options"] == "DENY"
    assert headers["content-security-policy"].startswith("default-src 'none'")
    assert headers["referrer-policy"] == "strict-origin-when-cross-origin"
    assert "x-request-id" in headers


def test_cors_allows_configured_origin_only(client):
    ok = client.get("/api/health", headers={"Origin": "http://localhost:3000"})
    assert ok.headers.get("access-control-allow-origin") == "http://localhost:3000"
    bad = client.get("/api/health", headers={"Origin": "https://evil.example"})
    assert "access-control-allow-origin" not in bad.headers


def test_json_body_size_limit(client):
    resp = client.post(
        "/api/events",
        content=b"{" + b" " * (3 * 1024 * 1024) + b"}",
        headers={"Content-Type": "application/json"},
    )
    assert resp.status_code == 413


def test_public_rate_limit(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "rate_limit_per_minute", 3)
    codes = [client.get("/api/movies").status_code for _ in range(4)]
    assert codes == [200, 200, 200, 429]
    assert client.get("/api/health").status_code == 200  # health checks are never limited


def test_rate_limit_uses_cloudfront_viewer_ip(client, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "rate_limit_per_minute", 2)
    monkeypatch.setattr(settings, "trust_proxy_headers", True)

    def get(viewer):
        return client.get("/api/movies", headers={"CloudFront-Viewer-Address": viewer}).status_code

    assert [get("203.0.113.7:51234") for _ in range(3)] == [200, 200, 429]
    # A different visitor behind the same CloudFront edge has its own budget (IPv6 too).
    assert get("2001:db8::1:443") == 200


def test_proxy_headers_ignored_unless_trusted(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "rate_limit_per_minute", 2)
    codes = [
        client.get(
            "/api/movies", headers={"CloudFront-Viewer-Address": f"198.51.100.{i}:80"}
        ).status_code
        for i in range(3)
    ]
    assert codes == [200, 200, 429]  # spoofed headers don't buy extra requests


def test_production_rejects_weak_secret():
    with pytest.raises(ValueError, match="SECRET_KEY"):
        Settings(environment="production", secret_key="short")


def test_postgres_url_uses_psycopg_driver():
    s = Settings(database_url="postgres://u:p@host:5432/db")
    assert s.sqlalchemy_url == "postgresql+psycopg://u:p@host:5432/db"


@pytest.mark.parametrize("key", ["../etc/passwd", "/abs/path", "a/../../b", "a\\b", ""])
def test_storage_rejects_path_traversal(key):
    with pytest.raises(ValueError):
        validate_key(key)


def test_media_mount_blocks_traversal(client):
    assert client.get("/media/../tests/conftest.py").status_code == 404
