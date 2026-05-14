from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Optional
from app.models.rating import Rating, Comment
from app.schemas.rating_schema import RatingCreate, CommentCreate


# ── Ratings ───────────────────────────────────────────

def get_rating_stats(db: Session, movie_id: int, user_id: Optional[int] = None) -> dict:
    row = db.query(
        func.round(func.avg(Rating.rating), 1).label("avg"),
        func.count(Rating.id).label("total"),
    ).filter(Rating.movie_id == movie_id).first()

    my_rating = None
    if user_id:
        r = db.query(Rating).filter_by(user_id=user_id, movie_id=movie_id).first()
        my_rating = r.rating if r else None

    avg = float(row.avg or 0) if row else 0.0
    total = row.total if row else 0
    return {"avg": avg, "total": total, "my_rating": my_rating}


def upsert_rating(db: Session, user_id: int, data: RatingCreate) -> dict:
    existing = db.query(Rating).filter_by(user_id=user_id, movie_id=data.movie_id).first()
    if existing:
        setattr(existing, 'rating', data.rating)
    else:
        db.add(Rating(user_id=user_id, movie_id=data.movie_id, rating=data.rating))
    db.commit()
    return get_rating_stats(db, data.movie_id, user_id)


# ── Comments ──────────────────────────────────────────

def get_comments(db: Session, movie_id: int) -> list[dict]:
    from app.models.user import User
    rows = (
        db.query(Comment, User.username)
          .join(User)
          .filter(Comment.movie_id == movie_id)
          .order_by(Comment.created_at.desc())
          .limit(50)
          .all()
    )
    return [
        {
            "id":         c.id,
            "text":       c.text,
            "username":   username,
            "user_id":    c.user_id,
            "created_at": c.created_at,
        }
        for c, username in rows
    ]


def add_comment(db: Session, user_id: int, data: CommentCreate) -> Comment:
    comment = Comment(user_id=user_id, movie_id=data.movie_id, text=data.text)
    db.add(comment)
    db.commit()
    db.refresh(comment)
    return comment


def delete_comment(db: Session, comment_id: int, user_id: int) -> bool:
    deleted = db.query(Comment).filter_by(id=comment_id, user_id=user_id).delete()
    db.commit()
    return deleted > 0
