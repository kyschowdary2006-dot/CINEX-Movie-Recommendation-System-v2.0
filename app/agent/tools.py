"""
CINEX AI — tool functions callable by the Groq/Llama agent.
Each function returns a JSON-serialisable value.
"""
from app.services.recommender import get_similar


def recommend_similar(movie_id: int, n: int = 5) -> list[dict]:
    """Return hybrid recommendations for a given movie ID."""
    result = get_similar(movie_id=movie_id, n=n)
    return result.get("recommendations", [])


def search_movies(query: str, limit: int = 6) -> list[dict]:
    """Search the movies table by title or keyword (case-insensitive)."""
    from app.db.database import SessionLocal
    from app.models.movie import Movie
    db = SessionLocal()
    try:
        rows = (
            db.query(Movie)
              .filter(Movie.title.ilike(f"%{query}%"))
              .limit(limit)
              .all()
        )
        return [
            {
                "id": m.id,
                "title": m.title,
                "vote_average": m.vote_average,
                "release_date": str(m.release_date) if m.release_date else "",
                "genres": m.genres if hasattr(m, "genres") else "",
            }
            for m in rows
        ]
    finally:
        db.close()


def get_user_ratings(user_id: int) -> list[dict]:
    """Return all movies rated by this user."""
    from app.db.database import SessionLocal
    from app.models.rating import Rating
    from app.models.movie import Movie
    db = SessionLocal()
    try:
        rows = (
            db.query(Rating, Movie.title)
              .join(Movie, Rating.movie_id == Movie.id, isouter=True)
              .filter(Rating.user_id == user_id)
              .all()
        )
        return [
            {"movie_id": r.movie_id, "rating": r.rating, "title": title or "Unknown"}
            for r, title in rows
        ]
    finally:
        db.close()


# Registry used by agent.py dispatcher
TOOL_REGISTRY = {
    "recommend_similar": recommend_similar,
    "search_movies":     search_movies,
    "get_user_ratings":  get_user_ratings,
}
