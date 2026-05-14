import json
import asyncio
import httpx
from typing import Optional
from sqlalchemy.orm import Session
from app.models.movie import Movie, Watchlist
from app.schemas.movie_schema import WatchlistAdd
from app.config import settings
from app.core.logging import logger


# ── TMDB helpers ──────────────────────────────────────

async def _tmdb_get(client: httpx.AsyncClient, path: str, **params) -> dict:
    params["api_key"] = settings.TMDB_API_KEY
    r = await client.get(f"{settings.TMDB_BASE_URL}{path}", params=params, timeout=15)
    r.raise_for_status()
    return r.json()


async def _fetch_movie_details(client: httpx.AsyncClient, movie_id: int) -> Optional[dict]:
    try:
        detail, credits, kw = await asyncio.gather(
            _tmdb_get(client, f"/movie/{movie_id}"),
            _tmdb_get(client, f"/movie/{movie_id}/credits"),
            _tmdb_get(client, f"/movie/{movie_id}/keywords"),
        )
        return {
            "id":            movie_id,
            "title":         detail.get("title", ""),
            "overview":      detail.get("overview", ""),
            "genres":        json.dumps([g["name"] for g in detail.get("genres", [])]),
            "cast":          json.dumps([c["name"] for c in credits.get("cast", [])[:8]]),
            "keywords":      json.dumps([k["name"] for k in kw.get("keywords", [])[:15]]),
            "poster_path":   detail.get("poster_path"),
            "backdrop_path": detail.get("backdrop_path"),
            "vote_average":  detail.get("vote_average"),
            "popularity":    detail.get("popularity"),
            "release_date":  detail.get("release_date", ""),
        }
    except Exception as exc:
        logger.warning(f"[movie_service] skip {movie_id}: {exc}")
        return None


async def fetch_movies_from_tmdb(pages: int = settings.TMDB_FETCH_PAGES) -> list[dict]:
    movie_ids: list[int] = []
    async with httpx.AsyncClient() as client:
        for page in range(1, pages + 1):
            try:
                data = await _tmdb_get(client, "/movie/popular", page=page)
                movie_ids.extend(m["id"] for m in data.get("results", []))
            except Exception as exc:
                logger.warning(f"[movie_service] page {page} failed: {exc}")

        logger.info(f"[movie_service] Fetched {len(movie_ids)} IDs — pulling details …")
        results, BATCH = [], 20
        for i in range(0, len(movie_ids), BATCH):
            batch   = movie_ids[i : i + BATCH]
            details = await asyncio.gather(*[_fetch_movie_details(client, mid) for mid in batch])
            results.extend(d for d in details if d)
            await asyncio.sleep(0.3)

    return results


def upsert_movies(db: Session, movies: list[dict]) -> int:
    for m in movies:
        existing = db.query(Movie).filter_by(id=m["id"]).first()
        if existing:
            for k, v in m.items():
                setattr(existing, k, v)
        else:
            db.add(Movie(**m))
    db.commit()
    return len(movies)


def fetch_and_store(db: Session, pages: int = settings.TMDB_FETCH_PAGES) -> int:
    """
    Run the async TMDB fetch in a dedicated event loop.
    Using asyncio.run() directly inside a background thread on Windows
    can conflict with the running uvicorn event loop — so we create
    a brand-new loop, run on it, then close it cleanly.
    """
    loop = asyncio.new_event_loop()
    try:
        movies = loop.run_until_complete(fetch_movies_from_tmdb(pages))
    finally:
        loop.close()
    return upsert_movies(db, movies)


# ── Watchlist ─────────────────────────────────────────

def get_watchlist(db: Session, user_id: int) -> list[Watchlist]:
    return (
        db.query(Watchlist)
          .filter_by(user_id=user_id)
          .order_by(Watchlist.added_at.desc())
          .all()
    )


def add_to_watchlist(db: Session, user_id: int, item: WatchlistAdd) -> Watchlist:
    existing = db.query(Watchlist).filter_by(user_id=user_id, movie_id=item.movie_id).first()
    if existing:
        return existing
    entry = Watchlist(user_id=user_id, movie_id=item.movie_id,
                      title=item.title, poster_path=item.poster_path)
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def remove_from_watchlist(db: Session, user_id: int, movie_id: int) -> None:
    db.query(Watchlist).filter_by(user_id=user_id, movie_id=movie_id).delete()
    db.commit()