from pydantic import BaseModel, EmailStr, Field
from datetime import datetime
from typing import Optional


class UserCreate(BaseModel):
    username: str      = Field(min_length=3, max_length=50)
    email:    EmailStr
    password: str      = Field(min_length=6)


class UserOut(BaseModel):
    id:         int
    username:   str
    email:      str
    created_at: datetime
    model_config = {"from_attributes": True}


class LoginRequest(BaseModel):
    email:    EmailStr
    password: str


class TokenResponse(BaseModel):
    token: str
    user:  UserOut
