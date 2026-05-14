from sqlalchemy import (
    Column, Integer, String, Float, DateTime, Text,
    ForeignKey, UniqueConstraint, Index
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.database import Base


class Movie(Base):
    __tablename__ = "movies"

    id            = Column(Integer, primary_key=True)
    title         = Column(String,  nullable=False)
    overview      = Column(Text,    nullable=True)
    genres        = Column(Text,    nullable=True)
    cast          = Column(Text,    nullable=True)
    keywords      = Column(Text,    nullable=True)
    poster_path   = Column(String,  nullable=True)
    backdrop_path = Column(String,  nullable=True)
    vote_average  = Column(Float,   nullable=True)
    popularity    = Column(Float,   nullable=True)
    release_date  = Column(String,  nullable=True)
    fetched_at    = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class Watchlist(Base):
    __tablename__ = "watchlist"
    __table_args__ = (
        UniqueConstraint("user_id", "movie_id"),
        Index("idx_watchlist_user", "user_id"),
    )

    id          = Column(Integer, primary_key=True, index=True)
    user_id     = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    movie_id    = Column(Integer, nullable=False)
    title       = Column(String,  nullable=False)
    poster_path = Column(String,  nullable=True)
    added_at    = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="watchlist")
