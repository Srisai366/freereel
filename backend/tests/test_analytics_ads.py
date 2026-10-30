from app.models import MovieView, SiteEvent

PHONE = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) Mobile/15E148"
DESKTOP = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/130.0"
TABLET = "Mozilla/5.0 (Linux; Android 14; SM-X710) AppleWebKit/537.36 Chrome/130.0 Safari/537.36"
BOT = "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"
SESSION = "3f1c2a9e-8b7d-4c6e-9a5f-1b2c3d4e5f60"


def send(client, ua=DESKTOP, **event):
    return client.post(
        "/api/events", json={"session_id": SESSION, **event}, headers={"User-Agent": ua}
    )


def test_visit_records_device_without_pii(client, db):
    assert send(client, PHONE, type="visit", path="/").status_code == 204
    assert send(client, TABLET, type="visit", path="/").status_code == 204
    events = db.query(SiteEvent).all()
    assert [e.device_category for e in events] == ["mobile", "tablet"]
    columns = set(SiteEvent.__table__.columns.keys())
    assert not columns & {"ip", "ip_address", "user_agent", "email"}


def test_bots_are_ignored(client, db, catalog):
    send(client, BOT, type="visit", path="/")
    send(client, BOT, type="play", movie_id=catalog["night"].id)
    assert db.query(SiteEvent).count() == 0 and db.query(MovieView).count() == 0


def test_play_deduplicated_and_progress_tracked(client, db, catalog):
    movie = catalog["night"]
    movie.duration = 600
    db.commit()
    send(client, type="play", movie_id=movie.id)
    send(client, type="play", movie_id=movie.id)  # refresh within 30 min: same view
    send(client, type="progress", movie_id=movie.id, watch_seconds=120)
    send(client, type="progress", movie_id=movie.id, watch_seconds=60)  # never decreases
    views = db.query(MovieView).all()
    assert len(views) == 1 and views[0].watch_duration == 120
    send(client, type="progress", movie_id=movie.id, watch_seconds=5000)
    db.refresh(views[0])
    assert views[0].watch_duration == 600  # capped at film length


def test_events_for_drafts_are_dropped(client, db, catalog):
    send(client, type="play", movie_id=catalog["draft"].id)
    assert db.query(MovieView).count() == 0


def test_event_validation(client):
    assert send(client, type="play", session_id="x").status_code == 422
    assert (
        client.post("/api/events", json={"type": "hack", "session_id": SESSION}).status_code == 422
    )
    assert send(client, type="progress", movie_id=1, watch_seconds=-5).status_code == 422


def test_dashboard(client, admin_headers, catalog):
    night = catalog["night"]
    send(client, PHONE, type="visit", path="/")
    send(client, DESKTOP, type="visit", path="/")
    send(client, type="play", movie_id=night.id)
    send(client, type="progress", movie_id=night.id, watch_seconds=90)

    data = client.get("/api/admin/analytics", headers=admin_headers).json()
    totals = data["totals"]
    assert totals["movies"] == 5
    assert totals["movies_by_status"] == {"published": 4, "draft": 1}
    assert totals["views"] == 1 and totals["visits"] == 2 and totals["watch_seconds"] == 90
    assert totals["unique_visitors_in_period"] == 1
    assert data["most_watched"][0]["title"] == "Night Terror"
    assert {g["name"] for g in data["popular_genres"]} == {"Drama", "Horror"}
    assert data["popular_languages"] == [{"name": "English", "views": 1}]
    assert data["devices"] == {"mobile": 1, "desktop": 1}
    assert data["trend"][0]["visits"] == 2 and data["trend"][0]["plays"] == 1
    assert len(data["recent_movies"]) == 5


# ---- advertisements ---------------------------------------------------------------

AD = {"title": "Film festival", "placement": "home_top",
      "advertisement_url": "https://festival.example.org", "image_url": "https://cdn.example.org/b.png"}  # fmt: skip


def test_ad_lifecycle(client, admin_headers):
    created = client.post("/api/admin/ads", json=AD, headers=admin_headers)
    assert created.status_code == 201
    ad_id = created.json()["id"]

    public = client.get("/api/ads", params={"placement": "home_top"}).json()
    assert [a["id"] for a in public] == [ad_id]
    assert "impressions" not in public[0]

    client.post(f"/api/ads/{ad_id}/impression", headers={"User-Agent": DESKTOP})
    client.post(f"/api/ads/{ad_id}/impression", headers={"User-Agent": DESKTOP})
    client.post(f"/api/ads/{ad_id}/click", headers={"User-Agent": DESKTOP})
    client.post(f"/api/ads/{ad_id}/click", headers={"User-Agent": BOT})
    stats = client.get("/api/admin/analytics", headers=admin_headers).json()["ads"][0]
    assert stats["impressions"] == 2 and stats["clicks"] == 1 and stats["ctr"] == 50.0

    client.put(f"/api/admin/ads/{ad_id}", json={**AD, "status": "inactive"}, headers=admin_headers)
    assert client.get("/api/ads").json() == []
    assert client.delete(f"/api/admin/ads/{ad_id}", headers=admin_headers).status_code == 204


def test_ad_validation(client, admin_headers):
    bad = [{**AD, "advertisement_url": "javascript:alert(1)"}, {**AD, "placement": "popup"},
           {**AD, "image_url": "data:text/html,<script>"}]  # fmt: skip
    for body in bad:
        assert client.post("/api/admin/ads", json=body, headers=admin_headers).status_code == 422


# ---- taxonomy -------------------------------------------------------------------------


def test_language_and_genre_management(client, admin_headers, catalog):
    resp = client.post(
        "/api/admin/languages", json={"name": "Kannada", "code": "kn"}, headers=admin_headers
    )
    assert resp.status_code == 201
    dup = client.post(
        "/api/admin/languages", json={"name": "Kannada 2", "code": "kn"}, headers=admin_headers
    )
    assert dup.status_code == 409
    in_use = catalog["village"].language_id
    assert client.delete(f"/api/admin/languages/{in_use}", headers=admin_headers).status_code == 409
    assert (
        client.delete(
            f"/api/admin/languages/{resp.json()['id']}", headers=admin_headers
        ).status_code
        == 204
    )

    genre = client.post("/api/admin/genres", json={"name": "Sci-Fi"}, headers=admin_headers)
    assert genre.status_code == 201 and genre.json()["slug"] == "sci-fi"
    drama_id = next(g.id for g in catalog["night"].genres if g.slug == "drama")
    assert client.delete(f"/api/admin/genres/{drama_id}", headers=admin_headers).status_code == 204
    night = client.get(f"/api/movies/{catalog['night'].slug}").json()
    assert [g["slug"] for g in night["genres"]] == ["horror"]
