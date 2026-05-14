from sqlalchemy import Column, Integer, String, Boolean, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.database import Base


class User(Base):
    __tablename__ = "users"

    id             = Column(Integer, primary_key=True, index=True)
    username       = Column(String,  nullable=False)
    email          = Column(String,  unique=True, index=True, nullable=False)
    password_hash  = Column(String,  nullable=False)
    email_verified = Column(Boolean, default=False, nullable=False)
    created_at     = Column(DateTime(timezone=True), server_default=func.now())

    watchlist = relationship("Watchlist", back_populates="user", cascade="all, delete")
    ratings   = relationship("Rating",    back_populates="user", cascade="all, delete")
    comments  = relationship("Comment",   back_populates="user", cascade="all, delete")
