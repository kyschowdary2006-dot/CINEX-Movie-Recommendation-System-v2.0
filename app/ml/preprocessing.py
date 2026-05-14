"""
preprocessing.py
────────────────
Loads movies from users.db, engineers a weighted text
feature per movie, and fits a TF-IDF matrix.

Artefacts saved to app/ml/store/:
  tfidf_vectorizer.pkl  movie_index.pkl
  tfidf_matrix.pkl      movie_meta.pkl
"""
import sys as _sys
from pathlib import Path as _Path
_PROJECT_ROOT = _Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in _sys.path:
    _sys.path.insert(0, str(_PROJECT_ROOT))
import json, pickle, logging
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from app.config import settings

logger = logging.getLogger("cinex.ml.preprocessing")
STORE  = settings.ml_store_path


def _build_soup(row: dict) -> str:
    parts = []
    try:
        genres = json.loads(row.get("genres") or "[]")
        parts += [g.replace(" ", "").lower() for g in genres] * 2
    except Exception:
        pass
    parts.append((row.get("overview") or "").lower())
    try:
        cast = json.loads(row.get("cast") or "[]")
        parts += [c.replace(" ", "").lower() for c in cast[:5]] * 3
    except Exception:
        pass
    try:
        kws = json.loads(row.get("keywords") or "[]")
        parts += [k.replace(" ", "").lower() for k in kws[:10]]
    except Exception:
        pass
    return " ".join(parts)


def load_movies_df() -> pd.DataFrame:
    from app.db.database import SessionLocal
    from app.models.movie import Movie
    db = SessionLocal()
    try:
        rows = db.query(Movie).all()
        if not rows:
            raise RuntimeError("No movies in DB — run train.py --fetch first.")
        return pd.DataFrame([{
            "id":           m.id,
            "title":        m.title,
            "overview":     m.overview or "",
            "genres":       m.genres   or "[]",
            "cast":         m.cast     or "[]",
            "keywords":     m.keywords or "[]",
            "poster_path":  m.poster_path,
            "vote_average": m.vote_average or 0.0,
            "popularity":   m.popularity   or 0.0,
            "release_date": m.release_date or "",
        } for m in rows])
    finally:
        db.close()


def run() -> dict:
    logger.info("[preprocessing] Loading movies …")
    df = load_movies_df()
    logger.info(f"[preprocessing] {len(df)} movies loaded")

    df["soup"] = df.apply(_build_soup, axis=1)
    df = df[df["soup"].str.strip() != ""].reset_index(drop=True)

    logger.info("[preprocessing] Fitting TF-IDF …")
    vectorizer = TfidfVectorizer(
        max_features=20_000, ngram_range=(1, 2),
        sublinear_tf=True, min_df=2,
        strip_accents="unicode", analyzer="word",
    )
    tfidf_matrix = vectorizer.fit_transform(df["soup"])
    movie_index  = {int(row["id"]): idx for idx, row in df.iterrows()}
    movie_meta   = df[["id","title","poster_path","vote_average","release_date"]].to_dict("records")

    _save("tfidf_vectorizer", vectorizer)
    _save("tfidf_matrix",     tfidf_matrix)
    _save("movie_index",      movie_index)
    _save("movie_meta",       movie_meta)

    stats = {
        "movies":   len(df),
        "features": tfidf_matrix.shape[1],
        "sparsity": f"{(1 - tfidf_matrix.getnnz() / (tfidf_matrix.shape[0]*tfidf_matrix.shape[1]))*100:.1f}%",
    }
    logger.info(f"[preprocessing] Done — {stats}")
    return stats


def _save(name: str, obj) -> None:
    path = STORE / f"{name}.pkl"
    with open(path, "wb") as f:
        pickle.dump(obj, f, protocol=pickle.HIGHEST_PROTOCOL)
    logger.info(f"[preprocessing] Saved {path.name}")


def load(name: str):
    path = STORE / f"{name}.pkl"
    if not path.exists():
        raise FileNotFoundError(f"Artefact '{name}' missing. Run train first.")
    with open(path, "rb") as f:
        return pickle.load(f)