import re
from datetime import UTC, datetime, timedelta

import jwt
import pytest

from app.core.config import get_settings
from app.main import app
from app.models import AuditLog
from tests.conftest import ADMIN_PASSWORD


def test_login_success(client, admin_user, db):
    resp = client.post("/api/admin/login", json={"username": "admin", "password": ADMIN_PASSWORD})
    assert resp.status_code == 200
    body = resp.json()
    assert body["token_type"] == "bearer" and body["expires_in"] == 3600
    assert body["admin"] == {"id": admin_user.id, "username": "admin", "role": "admin"}
    assert "password_hash" not in resp.text
    assert db.query(AuditLog).filter_by(action="admin.login").count() == 1


@pytest.mark.parametrize(
    "username,password", [("admin", "wrong-password"), ("nobody", ADMIN_PASSWORD)]
)
def test_login_failures_are_indistinguishable(client, admin_user, username, password):
    resp = client.post("/api/admin/login", json={"username": username, "password": password})
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Invalid username or password"


def test_inactive_admin_cannot_login(client, db, admin_user):
    admin_user.is_active = False
    db.commit()
    resp = client.post("/api/admin/login", json={"username": "admin", "password": ADMIN_PASSWORD})
    assert resp.status_code == 401


def test_login_rate_limited(client, admin_user):
    for _ in range(5):
        client.post("/api/admin/login", json={"username": "admin", "password": "nope"})
    resp = client.post("/api/admin/login", json={"username": "admin", "password": ADMIN_PASSWORD})
    assert resp.status_code == 429
    assert resp.headers["retry-after"] == "60"


def _admin_routes():
    # The OpenAPI schema lists every mounted route, however routers are nested.
    for path, operations in app.openapi()["paths"].items():
        if path.startswith("/api/admin") and path != "/api/admin/login":
            for method in operations:
                yield method.upper(), re.sub(r"\{[^}]+\}", "1", path)


def test_every_admin_route_requires_auth(client):
    routes = list(_admin_routes())
    assert len(routes) >= 20
    for method, path in routes:
        resp = client.request(method, path)
        assert resp.status_code == 401, f"{method} {path} returned {resp.status_code}"


def _token(key: str | None = None, **overrides):
    settings = get_settings()
    now = datetime.now(UTC)
    payload = {"sub": "1", "role": "admin", "iss": settings.jwt_issuer, "iat": now,
               "exp": now + timedelta(minutes=5), "typ": "admin"}  # fmt: skip
    payload.update(overrides)
    return jwt.encode(payload, key or settings.secret_key, algorithm="HS256")


@pytest.mark.parametrize(
    "token",
    [
        "not-a-jwt",
        _token(exp=datetime.now(UTC) - timedelta(minutes=1)),
        _token(key="some-other-secret-key-that-is-long-enough"),
        _token(iss="someone-else"),
        _token(typ="refresh"),
        _token(sub="999"),
    ],
    ids=["garbage", "expired", "wrong-key", "wrong-issuer", "wrong-type", "unknown-user"],
)
def test_bad_tokens_rejected(client, admin_user, token):
    resp = client.get("/api/admin/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401


def test_alg_none_token_rejected(client, admin_user):
    token = jwt.encode({"sub": "1", "typ": "admin"}, key=None, algorithm="none")
    assert (
        client.get("/api/admin/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401
    )


def test_deactivated_admin_token_stops_working(client, db, admin_user, admin_headers):
    assert client.get("/api/admin/me", headers=admin_headers).status_code == 200
    admin_user.is_active = False
    db.commit()
    assert client.get("/api/admin/me", headers=admin_headers).status_code == 401


def test_editor_cannot_do_admin_only_actions(client, editor_headers, catalog):
    movie_id = catalog["village"].id
    assert client.get("/api/admin/movies", headers=editor_headers).status_code == 200
    assert client.delete(f"/api/admin/movies/{movie_id}", headers=editor_headers).status_code == 403
    assert client.post("/api/admin/languages", json={"name": "Kannada", "code": "kn"},
                       headers=editor_headers).status_code == 403  # fmt: skip
    assert client.get("/api/admin/audit-logs", headers=editor_headers).status_code == 403
