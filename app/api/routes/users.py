from typing import cast

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.dependencies import get_db, get_current_user
from app.schemas.user_schema import UserCreate, UserOut, LoginRequest, TokenResponse
from app.services import user_service
from app.core.security import create_access_token, verify_password

router = APIRouter(prefix="/api/users", tags=["Users"])


@router.post("/register", response_model=TokenResponse, status_code=201)
def register(payload: UserCreate, db: Session = Depends(get_db)):
    """Register a new user. Saves bcrypt-hashed password to users.db."""
    if user_service.email_exists(db, payload.email):
        raise HTTPException(status_code=409, detail="Email already registered")
    if user_service.username_exists(db, payload.username):
        raise HTTPException(status_code=409, detail="Username already taken")
    try:
        user  = user_service.create_user(db, payload)
        token = create_access_token({"id": user.id, "username": user.username, "email": user.email})
        return {"token": token, "user": user}
    except IntegrityError:
        raise HTTPException(status_code=409, detail="Email already registered")


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    """Login and receive a JWT token."""
    user = user_service.get_by_email(db, payload.email)
    if not user:
        # Distinct message so the frontend can tell apart "no account" vs "wrong password"
        raise HTTPException(status_code=401, detail="No account found with that email. Please register first.")
    if not verify_password(payload.password, cast(str, user.password_hash)):
        raise HTTPException(status_code=401, detail="Incorrect password.")
    token = create_access_token({"id": user.id, "username": user.username, "email": user.email})
    return {"token": token, "user": user}


@router.get("/check-email")
def check_email(email: str, db: Session = Depends(get_db)):
    """Check whether an email is already registered (used by the signup form)."""
    return {"exists": user_service.email_exists(db, email)}


@router.get("/me", response_model=UserOut)
def me(payload: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """Return the currently authenticated user."""
    user = user_service.get_by_id(db, payload["id"])
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user