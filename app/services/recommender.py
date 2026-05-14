"""
recommender.py
──────────────
Service layer that bridges API routes ↔ ML modules.
Routes call these functions; they delegate to app/ml/predict.py.
"""
from typing import Optional
from app.core.logging import logger


def get_similar(movie_id: int, user_id: Optional[int] = None, n: int = 12) -> dict:
    """Hybrid recommendations for a movie detail page."""
    try:
        from app.ml.predict import hybrid_recommend
        recs  = hybrid_recommend(seed_movie_id=movie_id, user_id=user_id, n=n)
        model = "hybrid" if user_id else "content"
        return {"recommendations": recs, "model": model}
    except FileNotFoundError:
        return {
            "recommendations": [],
            "model":   "not_trained",
            "message": "Run  python -m app.ml.train --fetch  to train the model.",
        }
    except Exception as exc:
        logger.exception(f"[recommender] get_similar error: {exc}")
        return {"recommendations": [], "model": "error", "message": str(exc)}


def get_for_user(user_id: int, n: int = 12) -> dict:
    """Personalised home-feed recommendations."""
    try:
        from app.ml.predict import user_recommendations
        recs = user_recommendations(user_id=user_id, n=n)
        return {"recommendations": recs, "model": "collaborative_or_popular"}
    except FileNotFoundError:
        return {"recommendations": [], "model": "not_trained"}
    except Exception as exc:
        logger.exception(f"[recommender] get_for_user error: {exc}")
        return {"recommendations": [], "model": "error", "message": str(exc)}


def is_content_ready() -> bool:
    try:
        from app.ml.predict import content_model_ready
        return content_model_ready()
    except Exception:
        return False


def is_collab_ready() -> bool:
    try:
        from app.ml.predict import collab_model_ready
        return collab_model_ready()
    except Exception:
        return False
