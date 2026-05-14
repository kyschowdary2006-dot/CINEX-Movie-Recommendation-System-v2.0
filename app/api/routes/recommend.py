from fastapi import APIRouter, Depends, BackgroundTasks
from typing import Optional

from app.dependencies import get_current_user, get_optional_user, get_db
from app.services.recommender import get_similar, get_for_user, is_content_ready, is_collab_ready

router = APIRouter(prefix="/api/recommend", tags=["Recommendations"])


@router.get("/{movie_id}")
def movie_recommendations(
    movie_id: int,
    n:        int            = 12,
    payload:  Optional[dict] = Depends(get_optional_user),
):
    """
    Hybrid recommendations for a specific movie.
    - Anonymous   → pure content-based (TF-IDF cosine)
    - Logged-in   → blends content + collaborative SVD
    Falls back to TMDB /similar if model not trained yet.
    """
    user_id = payload["id"] if payload else None
    return get_similar(movie_id=movie_id, user_id=user_id, n=n)


@router.get("/user/me")
def personalised_feed(
    n:       int  = 12,
    payload: dict = Depends(get_current_user),
):
    """Personalised recommendations for the logged-in user's home feed."""
    return get_for_user(user_id=payload["id"], n=n)


@router.get("/status/models")
def model_status(db=Depends(get_db)):
    """Return which ML artefacts exist and DB row counts."""
    from pathlib import Path
    from app.config import settings
    from app.models.movie import Movie
    from app.models.rating import Rating
    from app.models.user import User

    store = settings.ml_store_path
    artefacts = [
        "tfidf_vectorizer", "tfidf_matrix", "movie_index", "movie_meta",
        "collab_predicted", "collab_user_map", "collab_movie_map",
    ]
    return {
        "artefacts":          {a: (store / f"{a}.pkl").exists() for a in artefacts},
        "content_ready":      is_content_ready(),
        "collab_ready":       is_collab_ready(),
        "db_users":           db.query(User).count(),
        "db_movies":          db.query(Movie).count(),
        "db_ratings":         db.query(Rating).count(),
    }


@router.post("/train")
def trigger_training(
    background_tasks: BackgroundTasks,
    fetch:   bool = False,
    pages:   int  = 25,
    payload: dict = Depends(get_current_user),
):
    """Trigger a full ML training pipeline in the background."""
    background_tasks.add_task(_run_training, fetch, pages)
    return {"status": "started", "fetch": fetch, "pages": pages}


def _run_training(fetch: bool, pages: int):
    from app.ml.train import train_all
    train_all(fetch=fetch, pages=pages)
