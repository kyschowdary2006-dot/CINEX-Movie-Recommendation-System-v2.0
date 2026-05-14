from fastapi import APIRouter, Depends, BackgroundTasks
from sqlalchemy.orm import Session

from app.dependencies import get_db, get_current_user
from app.schemas.movie_schema import WatchlistAdd, WatchlistItem
from app.services import movie_service

router = APIRouter(prefix="/api/movies", tags=["Movies"])


# ── Watchlist ─────────────────────────────────────────

@router.get("/watchlist", response_model=list[WatchlistItem])
def get_watchlist(
    payload: dict  = Depends(get_current_user),
    db: Session    = Depends(get_db),
):
    """Return all watchlist entries for the logged-in user."""
    return movie_service.get_watchlist(db, payload["id"])


@router.post("/watchlist", status_code=201)
def add_watchlist(
    item:    WatchlistAdd,
    payload: dict    = Depends(get_current_user),
    db:      Session = Depends(get_db),
):
    """Add a movie to the user's watchlist (idempotent)."""
    movie_service.add_to_watchlist(db, payload["id"], item)
    return {"success": True}


@router.delete("/watchlist/{movie_id}")
def remove_watchlist(
    movie_id: int,
    payload:  dict    = Depends(get_current_user),
    db:       Session = Depends(get_db),
):
    """Remove a movie from the user's watchlist."""
    movie_service.remove_from_watchlist(db, payload["id"], movie_id)
    return {"success": True}


# ── TMDB fetch + ML training trigger ─────────────────

@router.post("/fetch")
def fetch_movies(
    background_tasks: BackgroundTasks,
    pages:   int     = 25,
    payload: dict    = Depends(get_current_user),
    db:      Session = Depends(get_db),
):
    """
    Trigger a background TMDB fetch (stores movies in users.db)
    followed by ML re-training.
    """
    background_tasks.add_task(_bg_fetch_and_train, pages)
    return {"status": "started", "pages": pages}


def _bg_fetch_and_train(pages: int):
    from app.db.database import SessionLocal
    from app.ml.train import train_all
    db = SessionLocal()
    try:
        movie_service.fetch_and_store(db, pages=pages)
    finally:
        db.close()
    train_all(fetch=False)
