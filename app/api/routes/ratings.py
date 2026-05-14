from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional

from app.dependencies import get_db, get_current_user, get_optional_user
from app.schemas.rating_schema import (
    RatingCreate, RatingStats,
    CommentCreate, CommentOut,
)
from app.services import rating_service

router = APIRouter(prefix="/api/ratings", tags=["Ratings & Comments"])


# ── Ratings ───────────────────────────────────────────

@router.get("/{movie_id}", response_model=RatingStats)
def get_ratings(
    movie_id: int,
    db:       Session         = Depends(get_db),
    payload:  Optional[dict]  = Depends(get_optional_user),
):
    """Get community avg + total + (optionally) the caller's own rating."""
    user_id = payload["id"] if payload else None
    return rating_service.get_rating_stats(db, movie_id, user_id)


@router.post("", response_model=RatingStats)
def rate_movie(
    data:    RatingCreate,
    payload: dict    = Depends(get_current_user),
    db:      Session = Depends(get_db),
):
    """
    Submit or update a 1-5 star rating.
    Automatically triggers a background collaborative-filter retrain.
    """
    result = rating_service.upsert_rating(db, payload["id"], data)
    _trigger_collab_retrain()
    return result


def _trigger_collab_retrain():
    import threading
    def _run():
        try:
            from app.ml.train import _train_collab, _reload_caches
            _train_collab()
            _reload_caches()
        except Exception:
            pass
    threading.Thread(target=_run, daemon=True).start()


# ── Comments ──────────────────────────────────────────

@router.get("/comments/{movie_id}", response_model=list[CommentOut])
def get_comments(movie_id: int, db: Session = Depends(get_db)):
    """Get the 50 most recent comments for a movie."""
    return rating_service.get_comments(db, movie_id)


@router.post("/comments", response_model=CommentOut, status_code=201)
def post_comment(
    data:    CommentCreate,
    payload: dict    = Depends(get_current_user),
    db:      Session = Depends(get_db),
):
    """Post a comment on a movie (max 500 chars)."""
    comment = rating_service.add_comment(db, payload["id"], data)
    return {
        "id":         comment.id,
        "text":       comment.text,
        "username":   payload["username"],
        "user_id":    payload["id"],
        "created_at": comment.created_at,
    }


@router.delete("/comments/{comment_id}", status_code=204)
def delete_comment(
    comment_id: int,
    payload:    dict    = Depends(get_current_user),
    db:         Session = Depends(get_db),
):
    """Delete your own comment."""
    if not rating_service.delete_comment(db, comment_id, payload["id"]):
        raise HTTPException(status_code=404, detail="Comment not found or not yours")
