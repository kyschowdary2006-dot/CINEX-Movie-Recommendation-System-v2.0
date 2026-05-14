import os
from click import echo
from fastapi import FastAPI, Depends
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.core.logging import logger
from app.db.init_db import init_db
from app.api.router import api_router

# ── App creation ──────────────────────────────────────
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Movie recommendation system — FastAPI + SQLite + ML",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── CORS ─────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Auto-training scheduler ──────────────────────────
import threading
import time
from pathlib import Path
from datetime import datetime

# ── Guards ────────────────────────────────────────────
_training_lock    = threading.Lock()   # one training run at a time
_scheduler_started = False             # only one scheduler thread ever
_WEEKLY           = 7 * 24 * 3600     # seconds between TMDB refreshes
_MIN_RETRAIN_AGE  = 300               # don't retrain if models < 5 min old


def _ml_store_ready() -> bool:
    """True when all required content-based artefacts exist."""
    store    = settings.ml_store_path
    required = ["tfidf_matrix.pkl", "movie_index.pkl",
                "movie_meta.pkl",   "tfidf_vectorizer.pkl"]
    return all((store / f).exists() for f in required)


def _store_age_seconds() -> float:
    """Age of tfidf_matrix.pkl in seconds (inf when missing)."""
    p = settings.ml_store_path / "tfidf_matrix.pkl"
    if not p.exists():
        return float("inf")
    return datetime.now().timestamp() - p.stat().st_mtime


def _run_training(fetch: bool, label: str) -> None:
    """Thread target — acquires lock, runs training, releases lock."""
    if not _training_lock.acquire(blocking=False):
        logger.info(f"[auto-train] {label}: another run in progress — skipped")
        return
    try:
        logger.info(f"[auto-train] ── {label} started (fetch={fetch}) ──")
        from app.ml.train import train_all
        summary = train_all(fetch=fetch, pages=settings.TMDB_FETCH_PAGES)
        logger.info(f"[auto-train] ── {label} finished: {summary} ──")
    except Exception as exc:
        logger.error(f"[auto-train] {label} error: {exc}", exc_info=True)
    finally:
        _training_lock.release()


def _weekly_scheduler() -> None:
    """
    Daemon thread — sleeps until 7 days after last TMDB fetch,
    then re-fetches and retrains once.  Uses time.sleep() to avoid
    the threading.Event().wait(0) infinite-loop bug.
    """
    while True:
        age  = _store_age_seconds()
        wait = max(60, _WEEKLY - age)        # at least 60 s before first check
        logger.info(f"[auto-train] Next weekly refresh in {wait/3600:.1f}h")
        time.sleep(wait)                     # actual blocking sleep — no busy loop
        _run_training(fetch=True, label="weekly-refresh")


# ── Startup ───────────────────────────────────────────
@app.on_event("startup")
async def startup():
    global _scheduler_started

    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    init_db()
    logger.info("Database ready  →  users.db")
    logger.info("Docs available at  http://localhost:8000/docs")

    # Guard: uvicorn --reload spawns multiple processes - only train once.
    # We use an environment variable written by the first trainer process.
    import os
    if os.environ.get("CINEX_TRAINER_PID"):
        # Another process already owns training
        logger.info("[auto-train] Trainer already running in another process — skipped")
        return
    os.environ["CINEX_TRAINER_PID"] = str(os.getpid())

    age = _store_age_seconds()

    # Check how many movies are already in the DB (used for resume logic)
    db = next(get_db())
    try:
        from app.models.movie import Movie
        movie_count = db.query(Movie).count()
    except Exception:
        movie_count = 0
    finally:
        db.close()

    if _ml_store_ready() and age < _MIN_RETRAIN_AGE:
        # Models were freshly written (hot reload) — skip entirely
        logger.info(f"[auto-train] Models fresh ({age:.0f}s old) — skipping")

    elif _ml_store_ready():
        # Models exist — quick collab-only retrain for new ratings
        logger.info(f"[auto-train] Models exist ({age/3600:.1f}h old) — collab retrain only")
        threading.Thread(
            target=_run_training,
            kwargs={"fetch": False, "label": "startup-retrain"},
            daemon=True,
        ).start()

    elif movie_count >= 100:
        # Movies are in DB but models were deleted/never written — retrain without fetch
        logger.info(f"[auto-train] {movie_count} movies in DB but no models — retraining …")
        threading.Thread(
            target=_run_training,
            kwargs={"fetch": False, "label": "resume-train"},
            daemon=True,
        ).start()

    else:
        # First run or interrupted before DB was populated — full fetch + train
        logger.info(f"[auto-train] {movie_count} movies in DB — starting full fetch + train …")
        threading.Thread(
            target=_run_training,
            kwargs={"fetch": True, "label": "first-run"},
            daemon=True,
        ).start()

    # Start the weekly scheduler exactly once per process
    if not _scheduler_started:
        _scheduler_started = True
        threading.Thread(
            target=_weekly_scheduler,
            daemon=True,
            name="cinex-weekly-scheduler",
        ).start()
        logger.info("[auto-train] Weekly refresh scheduler started")


# ── API routes ────────────────────────────────────────
app.include_router(api_router)

# ── Backwards-compatible auth alias (/api/auth/…) ────
from app.api.routes.users import router as _users_router
from fastapi import APIRouter as _AR
_auth_alias = _AR()

from app.dependencies import get_db
from app.schemas.user_schema import UserCreate, LoginRequest, TokenResponse, UserOut
from app.services import user_service
from app.core.security import create_access_token, verify_password, get_current_user
from fastapi import HTTPException
from sqlalchemy.orm import Session

@app.post("/api/auth/register", response_model=TokenResponse, status_code=201, tags=["Auth"])
def auth_register(payload: UserCreate, db: Session = Depends(get_db)):
    if user_service.email_exists(db, payload.email):
        raise HTTPException(409, "Email already registered")
    if user_service.username_exists(db, payload.username):
        raise HTTPException(409, "Username already taken")
    user  = user_service.create_user(db, payload)
    token = create_access_token({"id": user.id, "username": user.username, "email": user.email})
    return {"token": token, "user": user}

@app.post("/api/auth/login", response_model=TokenResponse, tags=["Auth"])
def auth_login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = user_service.get_by_email(db, payload.email)
    if not user:
        raise HTTPException(401, "No account found with that email. Please register first.")
    if not verify_password(payload.password, user.password):
        raise HTTPException(401, "Incorrect password.")
    token = create_access_token({"id": user.id, "username": user.username, "email": user.email})
    return {"token": token, "user": user}

@app.get("/api/auth/me", response_model=UserOut, tags=["Auth"])
def auth_me(payload: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    user = user_service.get_by_id(db, payload["id"])
    if not user:
        raise HTTPException(404, "User not found")
    return user

# ── Backwards-compatible recommendation aliases ───────
from app.services.recommender import get_similar, get_for_user
from typing import Optional
from app.core.security import get_optional_user
from fastapi.security import HTTPAuthorizationCredentials

@app.get("/api/recommendations/{movie_id}", tags=["Recommendations"])
def compat_recommend(movie_id: int, n: int = 12,
                     payload: Optional[dict] = Depends(get_optional_user)):
    return get_similar(movie_id, user_id=payload["id"] if payload else None, n=n)

@app.get("/api/recommendations/user/me", tags=["Recommendations"])
def compat_user_recs(n: int = 12, payload: dict = Depends(get_current_user)):
    return get_for_user(payload["id"], n=n)

# ── Backwards-compatible watchlist / ratings aliases ──
from app.schemas.movie_schema import WatchlistAdd, WatchlistItem
from app.schemas.rating_schema import RatingCreate, RatingStats, CommentCreate, CommentOut
from app.services import movie_service, rating_service

@app.get("/api/watchlist", response_model=list[WatchlistItem], tags=["Watchlist"])
def compat_get_wl(payload=Depends(get_current_user), db=Depends(get_db)):
    return movie_service.get_watchlist(db, payload["id"])

@app.post("/api/watchlist", status_code=201, tags=["Watchlist"])
def compat_add_wl(item: WatchlistAdd, payload=Depends(get_current_user), db=Depends(get_db)):
    movie_service.add_to_watchlist(db, payload["id"], item)
    return {"success": True}

@app.delete("/api/watchlist/{movie_id}", tags=["Watchlist"])
def compat_rm_wl(movie_id: int, payload=Depends(get_current_user), db=Depends(get_db)):
    movie_service.remove_from_watchlist(db, payload["id"], movie_id)
    return {"success": True}

@app.get("/api/ratings/{movie_id}", response_model=RatingStats, tags=["Ratings"])
def compat_get_rating(movie_id: int, db=Depends(get_db),
                      payload: Optional[dict]=Depends(get_optional_user)):
    return rating_service.get_rating_stats(db, movie_id, payload["id"] if payload else None)

@app.post("/api/ratings", response_model=RatingStats, tags=["Ratings"])
def compat_rate(data: RatingCreate, payload=Depends(get_current_user), db=Depends(get_db)):
    from app.api.routes.ratings import _trigger_collab_retrain
    result = rating_service.upsert_rating(db, payload["id"], data)
    _trigger_collab_retrain()
    return result

@app.get("/api/comments/{movie_id}", response_model=list[CommentOut], tags=["Comments"])
def compat_get_comments(movie_id: int, db=Depends(get_db)):
    return rating_service.get_comments(db, movie_id)

@app.post("/api/comments", response_model=CommentOut, status_code=201, tags=["Comments"])
def compat_post_comment(data: CommentCreate, payload=Depends(get_current_user), db=Depends(get_db)):
    c = rating_service.add_comment(db, payload["id"], data)
    return {"id": c.id, "text": c.text, "username": payload["username"],
            "user_id": payload["id"], "created_at": c.created_at}

@app.delete("/api/comments/{comment_id}", status_code=204, tags=["Comments"])
def compat_del_comment(comment_id: int, payload=Depends(get_current_user), db=Depends(get_db)):
    if not rating_service.delete_comment(db, comment_id, payload["id"]):
        raise HTTPException(404, "Comment not found or not yours")

@app.post("/api/ml/train", tags=["ML"])
def compat_ml_train(background_tasks, fetch: bool = False, pages: int = 25,
                    payload=Depends(get_current_user)):
    from fastapi import BackgroundTasks
    from app.ml.train import train_all
    background_tasks.add_task(train_all, fetch=fetch, pages=pages)
    return {"status": "started"}

@app.get("/api/ml/training-status", tags=["ML"])
def ml_training_status():
    """Real-time training state — polled by the frontend banner."""
    locked  = not _training_lock.acquire(blocking=False)
    if not locked:
        _training_lock.release()
    ready   = _ml_store_ready()
    age_h   = round(_store_age_seconds() / 3600, 1) if ready else None
    return {
        "training":      locked,
        "models_ready":  ready,
        "model_age_hours": age_h,
        "next_refresh_hours": round(max(0, _WEEKLY - _store_age_seconds()) / 3600, 1),
    }


@app.get("/api/ml/status", tags=["ML"])
def compat_ml_status(db=Depends(get_db)):
    from app.services.recommender import is_content_ready, is_collab_ready
    from app.config import settings
    from app.models.movie import Movie
    from app.models.rating import Rating
    from app.models.user import User
    store = settings.ml_store_path
    arts  = ["tfidf_vectorizer","tfidf_matrix","movie_index","movie_meta",
             "collab_predicted","collab_user_map","collab_movie_map"]
    return {
        "artefacts":       {a: (store/f"{a}.pkl").exists() for a in arts},
        "content_ready":   is_content_ready(),
        "collab_ready":    is_collab_ready(),
        "db_users":        db.query(User).count(),
        "db_movies":       db.query(Movie).count(),
        "db_ratings":      db.query(Rating).count(),
    }

# ── Static frontend ───────────────────────────────────
import mimetypes
from pathlib import Path

PUBLIC = Path(os.path.dirname(__file__)).parent / "public"

# Explicit routes for each static asset (must come BEFORE the SPA catch-all
# so FastAPI doesn't swallow style.css / script.js with the wildcard handler).
if PUBLIC.is_dir():
    @app.get("/style.css", include_in_schema=False)
    def serve_css():
        return FileResponse(PUBLIC / "style.css", media_type="text/css")

    @app.get("/script.js", include_in_schema=False)
    def serve_js():
        return FileResponse(PUBLIC / "script.js", media_type="application/javascript")

    # Serve any other file inside public/ (fonts, images, favicons, etc.)
    # before falling back to the SPA.
    @app.get("/{filename:path}", include_in_schema=False)
    def spa(filename: str):
        # Resolve the requested path inside public/
        requested = (PUBLIC / filename).resolve()
        # Security: must stay inside PUBLIC
        try:
            requested.relative_to(PUBLIC.resolve())
        except ValueError:
            pass
        else:
            if requested.is_file():
                media_type, _ = mimetypes.guess_type(str(requested))
                return FileResponse(str(requested), media_type=media_type or "application/octet-stream")

        # Everything else → SPA index.html
        index = PUBLIC / "index.html"
        if index.exists():
            return FileResponse(str(index), media_type="text/html")
        return {"detail": "Frontend not found. Place index.html in public/"}

# ── Agent Chat endpoint ───────────────────────────────
from fastapi import Body

@app.post("/api/agent/chat", tags=["Agent"])
def agent_chat(
    message: str = Body(..., embed=True),
    payload: dict = Depends(get_current_user),
):
    """Send a message to the CINEX AI agent."""
    from app.agent.agent import chat
    reply = chat(user_id=payload["id"], message=message)
    return {"reply": reply, "user": payload["username"]}

@app.delete("/api/agent/memory", tags=["Agent"])
def clear_agent_memory(payload: dict = Depends(get_current_user)):
    """Clear conversation history for this user."""
    from app.agent.memory import clear
    clear(payload["id"])
    return {"success": True}

