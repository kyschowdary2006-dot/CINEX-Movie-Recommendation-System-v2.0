from sqlalchemy import (
    Column, Integer, String, DateTime, ForeignKey,
    CheckConstraint, UniqueConstraint, Index, Text
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.database import Base


class Rating(Base):
    __tablename__ = "ratings"
    __table_args__ = (
        UniqueConstraint("user_id", "movie_id"),
        CheckConstraint("rating BETWEEN 1 AND 5", name="chk_rating_range"),
        Index("idx_ratings_movie", "movie_id"),
    )

    id         = Column(Integer, primary_key=True, index=True)
    user_id    = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    movie_id   = Column(Integer, nullable=False)
    rating     = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="ratings")


class Comment(Base):
    __tablename__ = "comments"
    __table_args__ = (Index("idx_comments_movie", "movie_id"),)

    id         = Column(Integer, primary_key=True, index=True)
    user_id    = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    movie_id   = Column(Integer, nullable=False)
    text       = Column(Text,    nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="comments")
