"""
train.py — ML Training Pipeline
────────────────────────────────
Run from the project root (Cinex/ folder):

  python -m app.ml.train --fetch        <- recommended
  python -m app.ml.train
  python -m app.ml.train --fetch-only
  python -m app.ml.train --status
"""
import argparse, logging, sys, time
from pathlib import Path

# ── Ensure Cinex/ project root is always on sys.path ─────────────────────────
# Works whether you run as `python -m app.ml.train` OR `python app/ml/train.py`
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))
# ─────────────────────────────────────────────────────────────────────────────

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s  %(levelname)-7s  %(message)s",
                    datefmt="%H:%M:%S")
logger = logging.getLogger("cinex.ml.train")

# Absolute path so it works from any working directory
STORE = _PROJECT_ROOT / "app" / "ml" / "store"
STORE.mkdir(parents=True, exist_ok=True)


# ── Steps ─────────────────────────────────────────────

def step_fetch(pages: int = 25) -> int:
    from app.db.database import SessionLocal
    from app.services.movie_service import fetch_and_store
    logger.info(f"── STEP 1/3  Fetch TMDB ({pages} pages) ──")
    t0 = time.time()
    db = SessionLocal()
    try:
        n = fetch_and_store(db, pages=pages)
    finally:
        db.close()
    logger.info(f"   {n} movies stored  ({time.time()-t0:.1f}s)")
    return n


def step_preprocess() -> dict:
    from app.ml.preprocessing import run
    logger.info("── STEP 2/3  TF-IDF preprocessing ──")
    t0 = time.time()
    stats = run()
    logger.info(f"   {stats}  ({time.time()-t0:.1f}s)")
    return stats


def step_collaborative() -> dict:
    logger.info("── STEP 3/3  Collaborative SVD ──")
    t0 = time.time()
    stats = _train_collab()
    logger.info(f"   {stats}  ({time.time()-t0:.1f}s)")
    return stats


def _train_collab() -> dict:
    import pickle, numpy as np
    from sklearn.decomposition import TruncatedSVD
    from app.db.database import SessionLocal
    from app.models.rating import Rating
    from app.models.movie import Movie
    from app.config import settings

    db = SessionLocal()
    try:
        rows = db.query(Rating).all()
        if len(rows) < settings.MIN_RATINGS_FOR_COLLAB:
            return {"status": "skipped", "ratings": len(rows)}

        user_ids  = sorted({r.user_id  for r in rows})
        movie_ids = sorted({r.movie_id for r in rows})
        user_map  = {uid: i for i, uid in enumerate(user_ids)}
        movie_map = {mid: j for j, mid in enumerate(movie_ids)}

        R = np.zeros((len(user_ids), len(movie_ids)), dtype=np.float32)
        for r in rows:
            R[user_map[r["user_id"]], movie_map[r["movie_id"]]] = float(r["rating"])


        R_norm = R.copy()
        user_means = np.zeros(len(user_ids), dtype=np.float32)
        for i in range(len(user_ids)):
            rated = R[i, R[i] != 0]
            if len(rated):
                user_means[i] = rated.mean()
                R_norm[i, R[i] != 0] -= user_means[i]

        k   = min(settings.SVD_FACTORS, min(R_norm.shape) - 1)
        svd = TruncatedSVD(n_components=k, random_state=42)
        U   = svd.fit_transform(R_norm)
        Vt  = svd.components_
        pred = np.dot(U, Vt)
        for i in range(len(user_ids)):
            pred[i] += user_means[i]
        np.clip(pred, 1.0, 5.0, out=pred)

        meta = db.query(Movie).filter(Movie.id.in_(movie_ids)).all()
        collab_meta = [{"id": m.id, "title": m.title,
                        "poster_path": m.poster_path,
                        "vote_average": m.vote_average or 0,
                        "release_date": m.release_date or ""} for m in meta]

        STORE.mkdir(exist_ok=True)
        for name, obj in [("collab_predicted", pred), ("collab_user_map", user_map),
                          ("collab_movie_map", movie_map), ("collab_movie_meta", collab_meta)]:
            with open(STORE / f"{name}.pkl", "wb") as f:
                pickle.dump(obj, f, protocol=pickle.HIGHEST_PROTOCOL)

        return {"status": "trained", "users": len(user_ids),
                "movies": len(movie_ids), "ratings": len(rows), "factors": k}
    finally:
        db.close()


def _reload_caches():
    try:
        from app.ml import predict
        predict.reload_all()
    except Exception as exc:
        logger.warning(f"   Cache reload skipped: {exc}")


def train_all(fetch: bool = True, pages: int = 25) -> dict:
    summary = {}
    t0 = time.time()
    if fetch:
        summary["fetch"] = {"movies_stored": step_fetch(pages)}
    summary["preprocess"]    = step_preprocess()
    summary["collaborative"] = step_collaborative()
    _reload_caches()
    summary["total_seconds"] = round(time.time() - t0, 1)
    logger.info(f"Training complete in {summary['total_seconds']}s")
    return summary


def show_status():
    artefacts = ["tfidf_vectorizer", "tfidf_matrix", "movie_index",
                 "movie_meta", "collab_predicted", "collab_user_map", "collab_movie_map"]
    print(f"\nCINEX ML — Status  (store: {STORE})")
    print("─" * 50)
    for a in artefacts:
        p = STORE / f"{a}.pkl"
        if p.exists():
            print(f"  OK   {a:<28} ({p.stat().st_size//1024} KB)")
        else:
            print(f"  --   {a:<28} missing")

    from app.db.database import SessionLocal
    from app.models.movie import Movie
    from app.models.rating import Rating
    from app.models.user import User
    db = SessionLocal()
    try:
        print(f"\n  users.db → {db.query(User).count()} users, "
              f"{db.query(Movie).count()} movies, {db.query(Rating).count()} ratings\n")
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CINEX ML training pipeline")
    parser.add_argument("--fetch",      action="store_true")
    parser.add_argument("--fetch-only", action="store_true")
    parser.add_argument("--pages",      type=int, default=25)
    parser.add_argument("--status",     action="store_true")
    args = parser.parse_args()

    if args.status:
        show_status(); sys.exit(0)
    if args.fetch_only:
        step_fetch(args.pages); sys.exit(0)
    train_all(fetch=args.fetch, pages=args.pages)