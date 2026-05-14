"""
predict.py — Inference
───────────────────────
Content-based (TF-IDF cosine) + Collaborative (SVD) + Hybrid blending.
All artefacts are loaded once and cached in module-level variables.
"""
import sys as _sys
from pathlib import Path as _Path
_PROJECT_ROOT = _Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in _sys.path:
    _sys.path.insert(0, str(_PROJECT_ROOT))
import logging, numpy as np
from typing import Optional
from sklearn.metrics.pairwise import cosine_similarity
from app.ml.preprocessing import load
from app.config import settings

logger = logging.getLogger("cinex.ml.predict")

# ── Module-level artefact caches ──────────────────────
_tfidf_matrix   = None
_movie_index    = None   # {tmdb_id → row}
_movie_meta     = None   # [{id, title, poster_path, …}]
_idx_to_id      = None
_collab_pred    = None   # np.ndarray users × movies
_collab_user    = None   # {user_id → row}
_collab_movie   = None   # {movie_id → col}
_collab_inv     = None   # {col → movie_id}
_collab_meta    = None


def _load_content():
    global _tfidf_matrix, _movie_index, _movie_meta, _idx_to_id
    if _tfidf_matrix is not None:
        return
    _tfidf_matrix = load("tfidf_matrix")
    _movie_index  = load("movie_index")
    _movie_meta   = load("movie_meta")
    _idx_to_id    = {v: k for k, v in _movie_index.items()}
    logger.info(f"[predict] Content model loaded — {_tfidf_matrix.shape[0]} movies")


def _load_collab():
    global _collab_pred, _collab_user, _collab_movie, _collab_inv, _collab_meta
    if _collab_pred is not None:
        return
    _collab_pred  = load("collab_predicted")
    _collab_user  = load("collab_user_map")
    _collab_movie = load("collab_movie_map")
    _collab_inv   = {v: k for k, v in _collab_movie.items()}
    _collab_meta  = load("collab_movie_meta")
    logger.info(f"[predict] Collab model loaded — {_collab_pred.shape}")


def reload_all():
    global _tfidf_matrix, _movie_index, _movie_meta, _idx_to_id
    global _collab_pred, _collab_user, _collab_movie, _collab_inv, _collab_meta
    _tfidf_matrix = _movie_index = _movie_meta = _idx_to_id = None
    _collab_pred  = _collab_user = _collab_movie = _collab_inv = _collab_meta = None
    logger.info("[predict] Caches cleared — will reload on next request")


def content_model_ready() -> bool:
    try:
        _load_content(); return True
    except FileNotFoundError:
        return False


def collab_model_ready() -> bool:
    try:
        _load_collab(); return True
    except FileNotFoundError:
        return False


# ── Content-based ─────────────────────────────────────

def content_similar(movie_id: int, n: int = 36) -> list[dict]:
    _load_content()
    idx = _movie_index.get(movie_id)
    if idx is None:
        return []
    scores = cosine_similarity(_tfidf_matrix[idx], _tfidf_matrix).flatten()
    top    = np.argsort(scores)[::-1]
    top    = [i for i in top if i != idx][:n]
    meta   = {m["id"]: m for m in _movie_meta}
    return [
        {**meta.get(_idx_to_id[i], {}),
         "similarity_score": round(float(scores[i]), 4)}
        for i in top if _idx_to_id.get(i)
    ]


# ── Collaborative ─────────────────────────────────────

def collab_predicted_scores(user_id: int, movie_ids: list[int]) -> dict[int, float]:
    try:
        _load_collab()
    except FileNotFoundError:
        return {mid: 0.0 for mid in movie_ids}
    ui = _collab_user.get(user_id)
    if ui is None:
        return {mid: 0.0 for mid in movie_ids}
    return {mid: float(_collab_pred[ui, _collab_movie[mid]])
            for mid in movie_ids if mid in _collab_movie}


def user_recommendations(user_id: int, n: int = 12) -> list[dict]:
    try:
        _load_collab()
    except FileNotFoundError:
        return _popular_fallback(n)

    ui = _collab_user.get(user_id)
    if ui is None:
        return _popular_fallback(n)

    from app.db.database import SessionLocal
    from app.models.rating import Rating
    db = SessionLocal()
    try:
        rated = {r.movie_id for r in db.query(Rating).filter_by(user_id=user_id).all()}
    finally:
        db.close()

    row = _collab_pred[ui].copy()
    for mid in rated:
        col = _collab_movie.get(mid)
        if col is not None:
            row[col] = -999.0

    top  = np.argsort(row)[::-1][:n]
    meta = {m["id"]: m for m in _collab_meta}
    result = []
    for col in top:
        mid = _collab_inv.get(int(col))
        if mid:
            result.append({**meta.get(mid, {}),
                           "predicted_rating": round(float(row[col]), 2),
                           "source": "collaborative"})
    return result


def _popular_fallback(n: int) -> list[dict]:
    try:
        _load_content()
        top = sorted(_movie_meta, key=lambda m: m.get("vote_average", 0), reverse=True)[:n]
        for m in top:
            m["source"] = "popular"
        return top
    except FileNotFoundError:
        return []


# ── Hybrid ────────────────────────────────────────────

ALPHA_COLD, BETA_COLD = 0.85, 0.15
ALPHA_WARM, BETA_WARM = 0.45, 0.55


def hybrid_recommend(seed_movie_id: int, user_id: Optional[int] = None, n: int = 12) -> list[dict]:
    cb  = content_similar(seed_movie_id, n=n * 3)
    if not cb:
        return []

    cids    = [r["id"] for r in cb]
    c_score = {r["id"]: r["similarity_score"] for r in cb}

    # Collaborative
    has_collab = False
    col_norm   = {}
    if user_id is not None:
        try:
            raw        = collab_predicted_scores(user_id, cids)
            has_collab = any(v > 0 for v in raw.values())
            col_norm   = {mid: v / 5.0 for mid, v in raw.items()}
        except Exception:
            pass

    alpha = ALPHA_WARM if has_collab else ALPHA_COLD
    beta  = BETA_WARM  if has_collab else BETA_COLD

    blended = sorted(
        [(mid, alpha * c_score.get(mid, 0) + beta * col_norm.get(mid, 0)) for mid in cids],
        key=lambda x: x[1], reverse=True,
    )[:n]

    cb_meta = {r["id"]: r for r in cb}
    source  = "hybrid" if has_collab else "content"
    return [
        {**cb_meta.get(mid, {}),
         "hybrid_score": round(score, 4),
         "source":       source}
        for mid, score in blended
    ]