"""Management commands.

    python -m app.cli create-admin --username admin [--role admin|editor]
    python -m app.cli seed
    python -m app.cli enqueue-video --movie-id 3 C:\\path\\to\\film.mp4

create-admin reads the password from ADMIN_PASSWORD, or prompts for it.
enqueue-video lets you add a large file straight from your laptop to storage without
sending it through the (small, free-tier) API server.
"""

import argparse
import getpass
import os
import sys
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.database.base import utcnow
from app.database.session import SessionLocal
from app.models import ROLES, AdminUser, Genre, Language, Movie, MovieStatus
from app.services import uploads, video_jobs
from app.services.text import slugify

LANGUAGES = [
    ("Tamil", "ta"), ("Telugu", "te"), ("Hindi", "hi"), ("Malayalam", "ml"),
    ("Kannada", "kn"), ("English", "en"), ("Silent", "zxx"),
]  # fmt: skip

GENRES = [
    "Action", "Adventure", "Animation", "Comedy", "Documentary", "Drama", "Family",
    "Fantasy", "Horror", "Mystery", "Romance", "Sci-Fi", "Thriller",
]  # fmt: skip

# Only public-domain or Creative-Commons titles. Public-domain status differs by country,
# so check each title for the countries you serve before publishing.
# Synopses are original text written for this project.
DEMO_MOVIES = [
    {
        "title": "Big Buck Bunny", "release_year": 2008, "language": "en", "duration": 596,
        "genres": ["Animation", "Comedy", "Family"], "featured": True,
        "director": "Sacha Goedegebure", "cast_members": [],
        "license": "CC BY 3.0, Blender Foundation (peach.blender.org)",
        "description": "A gentle giant rabbit's peaceful morning in the meadow is ruined by three "
        "mischievous rodents, so he plans an elaborate and very funny revenge.",
        "video_url": "https://test-streams.mux.dev/x36xhzz/x36xhzz.m3u8",
    },
    {
        "title": "Sintel", "release_year": 2010, "language": "en", "duration": 888,
        "genres": ["Animation", "Fantasy", "Adventure"], "featured": True,
        "director": "Colin Levy", "cast_members": ["Halina Reijn", "Thom Hoffman"],
        "license": "CC BY 3.0, Blender Foundation (durian.blender.org)",
        "description": "A lone young woman crosses frozen wastes and hostile cities to find the "
        "baby dragon she once rescued, and learns too late what the search has cost her.",
    },
    {
        "title": "Tears of Steel", "release_year": 2012, "language": "en", "duration": 734,
        "genres": ["Sci-Fi", "Action"], "featured": True,
        "director": "Ian Hubert", "cast_members": ["Derek de Lint", "Sergio Hasselbaink"],
        "license": "CC BY 3.0, Blender Foundation (mango.blender.org)",
        "description": "In a future Amsterdam, a group of scientists and warriors stage a desperate "
        "experiment to change the outcome of a battle against rogue robots.",
        "video_url": "https://demo.unified-streaming.com/k8s/features/stable/video/tears-of-steel/"
        "tears-of-steel.ism/.m3u8",
    },
    {
        "title": "Elephants Dream", "release_year": 2006, "language": "en", "duration": 654,
        "genres": ["Animation", "Sci-Fi"], "director": "Bassam Kurdali",
        "cast_members": ["Tygo Gernandt", "Cas Jansen"],
        "license": "CC BY 2.5, Blender Foundation (orange.blender.org)",
        "description": "Two men explore a vast surreal machine. One sees wonders, the other sees "
        "only danger, and their argument shapes the world around them.",
    },
    {
        "title": "Night of the Living Dead", "release_year": 1968, "language": "en", "duration": 5760,
        "genres": ["Horror", "Thriller"], "director": "George A. Romero",
        "cast_members": ["Duane Jones", "Judith O'Dea"],
        "license": "Public domain (US): released without a copyright notice",
        "description": "Strangers barricade themselves in a farmhouse as the recently dead rise "
        "and surround them, and the danger inside the house grows as fast as the one outside.",
    },
    {
        "title": "Nosferatu", "release_year": 1922, "language": "zxx", "duration": 5640,
        "genres": ["Horror", "Fantasy"], "director": "F. W. Murnau", "cast_members": ["Max Schreck"],
        "license": "Public domain",
        "description": "A young estate agent travels to a remote castle to close a property sale "
        "and brings back a plague-carrying count to his seaside town.",
    },
    {
        "title": "The General", "release_year": 1926, "language": "zxx", "duration": 4620,
        "genres": ["Comedy", "Action", "Adventure"], "director": "Buster Keaton",
        "cast_members": ["Buster Keaton", "Marion Mack"],
        "license": "Public domain",
        "description": "A determined railway engineer chases his stolen locomotive, and the woman "
        "he loves, deep behind enemy lines in a run of famous stunts.",
    },
    {
        "title": "His Girl Friday", "release_year": 1940, "language": "en", "duration": 5520,
        "genres": ["Comedy", "Romance"], "director": "Howard Hawks",
        "cast_members": ["Cary Grant", "Rosalind Russell"],
        "license": "Public domain (US): copyright not renewed",
        "description": "A newspaper editor uses every trick he knows to stop his star reporter, "
        "who is also his ex-wife, from leaving the job and remarrying.",
    },
    {
        "title": "Charade", "release_year": 1963, "language": "en", "duration": 6780,
        "genres": ["Mystery", "Romance", "Thriller"], "director": "Stanley Donen",
        "cast_members": ["Cary Grant", "Audrey Hepburn"],
        "license": "Public domain (US): released without a valid copyright notice",
        "description": "After her husband is murdered, a woman in Paris is pursued by men who want "
        "his missing fortune, and she can't tell whether the charming stranger helping her can be trusted.",
    },
    {
        "title": "Raja Harishchandra", "release_year": 1913, "language": "zxx", "duration": 2400,
        "genres": ["Drama", "Fantasy"], "director": "Dadasaheb Phalke",
        "cast_members": ["D. D. Dabke", "P. G. Sane"],
        "license": "Public domain (India): film copyright term expired",
        "description": "India's first full-length feature film retells the legend of an honest "
        "king who gives up his kingdom and family to keep his word. Only part of the film survives.",
    },
]  # fmt: skip


def create_admin(args: argparse.Namespace) -> None:
    password = os.environ.get("ADMIN_PASSWORD")
    if not password:
        password = getpass.getpass("Password (min 12 chars): ")
        if password != getpass.getpass("Repeat password: "):
            sys.exit("Passwords do not match")
    if len(password) < 12:
        sys.exit("Password must be at least 12 characters")
    with SessionLocal() as db:
        existing = db.scalar(select(AdminUser).where(AdminUser.username == args.username))
        if existing:
            existing.password_hash = hash_password(password)
            existing.role = args.role
            existing.is_active = True
            print(f"Updated admin '{args.username}'")
        else:
            db.add(
                AdminUser(
                    username=args.username, password_hash=hash_password(password), role=args.role
                )
            )
            print(f"Created admin '{args.username}' ({args.role})")
        db.commit()


def seed_taxonomy(db: Session) -> None:
    for name, code in LANGUAGES:
        if db.scalar(select(Language).where(Language.code == code)) is None:
            db.add(Language(name=name, code=code))
    for name in GENRES:
        slug = slugify(name)
        if db.scalar(select(Genre).where(Genre.slug == slug)) is None:
            db.add(Genre(name=name, slug=slug))
    db.flush()


def seed(_args: argparse.Namespace) -> None:
    with SessionLocal() as db:
        seed_taxonomy(db)
        langs = {lang.code: lang for lang in db.scalars(select(Language))}
        genres = {g.name: g for g in db.scalars(select(Genre))}
        created = 0
        for data in DEMO_MOVIES:
            slug = f"{slugify(data['title'])}-{data['release_year']}"
            if db.scalar(select(Movie.id).where(Movie.slug == slug)):
                continue
            video_url = data.get("video_url")
            movie = Movie(
                title=data["title"],
                slug=slug,
                description=data["description"],
                release_year=data["release_year"],
                language=langs[data["language"]],
                duration=data["duration"],
                director=data.get("director"),
                cast_members=data.get("cast_members", []),
                license=data.get("license"),
                featured=data.get("featured", False),
                genres=[genres[g] for g in data["genres"]],
                video_url=video_url,
                video_format="hls" if video_url else None,
                video_quality="auto" if video_url else None,
                status=MovieStatus.PUBLISHED,
                published_at=utcnow(),
            )
            db.add(movie)
            created += 1
        db.commit()
        print(f"Seeded {len(LANGUAGES)} languages, {len(GENRES)} genres, {created} new movies")


def enqueue_video(args: argparse.Namespace) -> None:
    path = Path(args.path)
    if not path.is_file():
        sys.exit(f"File not found: {path}")
    ext = uploads.extension_of(path.name, uploads.VIDEO_EXTENSIONS)
    uploads.validate_video_file(path)
    with SessionLocal() as db:
        movie = db.get(Movie, args.movie_id)
        if movie is None:
            sys.exit(f"Movie {args.movie_id} not found")
        job = video_jobs.enqueue_video(db, movie, path, ext)
        print(f"Queued job {job.id} for '{movie.title}'. Run the worker to process it.")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("create-admin", help="create or reset an administrator")
    p.add_argument("--username", required=True)
    p.add_argument("--role", choices=ROLES, default="admin")
    p.set_defaults(func=create_admin)

    p = sub.add_parser("seed", help="insert languages, genres and demo public-domain movies")
    p.set_defaults(func=seed)

    p = sub.add_parser("enqueue-video", help="upload a local video file and queue processing")
    p.add_argument("--movie-id", type=int, required=True)
    p.add_argument("path")
    p.set_defaults(func=enqueue_video)

    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
