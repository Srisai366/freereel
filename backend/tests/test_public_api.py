from app.models import MovieView


def titles(resp):
    return [m["title"] for m in resp.json()["items"]]


def test_health(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_list_only_published(client, catalog):
    resp = client.get("/api/movies")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 4
    assert "Secret Draft" not in titles(resp)
    card = body["items"][0]
    for key in (
        "title",
        "slug",
        "release_year",
        "language",
        "genres",
        "poster_url",
        "video_quality",
        "has_video",
    ):
        assert key in card
    assert "video_url" not in card  # cards don't leak stream URLs; details do


def test_pagination(client, catalog):
    first = client.get("/api/movies", params={"page_size": 3, "page": 1}).json()
    second = client.get("/api/movies", params={"page_size": 3, "page": 2}).json()
    assert first["pages"] == 2 and len(first["items"]) == 3 and len(second["items"]) == 1
    assert not {m["id"] for m in first["items"]} & {m["id"] for m in second["items"]}


def test_page_size_capped(client, catalog):
    assert client.get("/api/movies", params={"page_size": 500}).status_code == 422


def test_filter_by_language_genre_year(client, catalog):
    assert set(titles(client.get("/api/movies", params={"language": "ta"}))) == {
        "Village Story",
        "River Song 100%",
    }
    assert set(titles(client.get("/api/movies", params={"genre": "comedy"}))) == {
        "Laugh Riot",
        "River Song 100%",
    }
    assert set(titles(client.get("/api/movies", params={"year": 1968}))) == {"Night Terror"}
    combined = client.get("/api/movies", params={"language": "ta", "genre": "comedy", "year": 1950})
    assert titles(combined) == ["River Song 100%"]


def test_sort_by_title(client, catalog):
    names = titles(client.get("/api/movies", params={"sort": "title"}))
    assert names == sorted(names)


def test_search_title_director_cast(client, catalog):
    assert titles(client.get("/api/movies/search", params={"q": "night"})) == ["Night Terror"]
    assert titles(client.get("/api/movies/search", params={"q": "jane"})) == ["Laugh Riot"]
    assert titles(client.get("/api/movies/search", params={"q": "asha"})) == ["River Song 100%"]
    assert titles(client.get("/api/movies/search", params={"q": "secret"})) == []  # draft hidden


def test_search_treats_wildcards_literally(client, catalog):
    assert titles(client.get("/api/movies/search", params={"q": "%"})) == ["River Song 100%"]
    assert titles(client.get("/api/movies/search", params={"q": "_"})) == []


def test_search_with_filters(client, catalog):
    resp = client.get("/api/movies/search", params={"q": "o", "language": "ta"})
    assert set(titles(resp)) == {"Village Story", "River Song 100%"}


def test_invalid_filter_rejected(client):
    assert (
        client.get("/api/movies", params={"language": "'; DROP TABLE movies;--"}).status_code == 422
    )
    assert client.get("/api/movies", params={"year": 1500}).status_code == 422


def test_latest_and_featured(client, catalog):
    latest = client.get("/api/movies/latest", params={"limit": 2}).json()
    assert len(latest) == 2
    featured = client.get("/api/movies/featured").json()
    assert [m["title"] for m in featured] == ["Laugh Riot"]


def test_trending_orders_by_recent_views(client, catalog, db):
    night, village = catalog["night"], catalog["village"]
    db.add_all(
        [MovieView(movie_id=night.id, anonymous_session_id=f"session-{i:04d}") for i in range(3)]
    )
    db.add(MovieView(movie_id=village.id, anonymous_session_id="session-9999"))
    db.add(MovieView(movie_id=catalog["draft"].id, anonymous_session_id="session-8888"))
    db.commit()
    trending = [m["title"] for m in client.get("/api/movies/trending").json()]
    assert trending[:2] == ["Night Terror", "Village Story"]
    assert "Secret Draft" not in trending
    assert len(trending) == 4  # topped up with latest titles


def test_movie_details_by_id_and_slug(client, catalog):
    night = catalog["night"]
    by_id = client.get(f"/api/movies/{night.id}")
    by_slug = client.get(f"/api/movies/{night.slug}")
    assert by_id.status_code == by_slug.status_code == 200
    body = by_slug.json()
    assert body["id"] == night.id
    assert body["video_url"] == "https://cdn.example.com/n/master.m3u8"
    assert body["video_quality"] == ["360p", "720p"]
    assert body["has_video"] is True
    assert [g["slug"] for g in body["genres"]] == ["drama", "horror"]
    for internal in ("status", "poster_key", "original_key", "storage_bytes"):
        assert internal not in body


def test_draft_and_missing_movie_404(client, catalog):
    assert client.get(f"/api/movies/{catalog['draft'].id}").status_code == 404
    assert client.get("/api/movies/no-such-movie").status_code == 404
    assert client.get("/api/movies/BAD SLUG").status_code == 422


def test_languages_genres_categories_counts(client, catalog):
    langs = {lang["code"]: lang["movie_count"] for lang in client.get("/api/languages").json()}
    assert langs == {"en": 2, "ta": 2}  # draft not counted
    genres = {g["slug"]: g["movie_count"] for g in client.get("/api/genres").json()}
    assert genres == {"comedy": 2, "drama": 3, "horror": 1}
    cats = client.get("/api/categories").json()
    assert {"languages", "genres"} == set(cats)


def test_public_responses_are_cacheable(client, catalog):
    assert "max-age" in client.get("/api/movies").headers["cache-control"]
