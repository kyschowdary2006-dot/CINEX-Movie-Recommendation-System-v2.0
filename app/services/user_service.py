from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Optional
from app.models.user import User
from app.schemas.user_schema import UserCreate
from app.core.security import hash_password


def create_user(db: Session, payload: UserCreate) -> User:
    user = User(
        username       = payload.username.strip(),
        email          = payload.email.strip().lower(),
        password_hash  = hash_password(payload.password),
        email_verified = True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def get_by_email(db: Session, email: str) -> Optional[User]:
    return db.query(User).filter(
        func.lower(User.email) == email.strip().lower()
    ).first()


def get_by_id(db: Session, user_id: int) -> Optional[User]:
    return db.query(User).filter(User.id == user_id).first()


def email_exists(db: Session, email: str) -> bool:
    return get_by_email(db, email) is not None


def username_exists(db: Session, username: str) -> bool:
    return db.query(User).filter(
        func.lower(User.username) == username.strip().lower()
    ).first() is not None
