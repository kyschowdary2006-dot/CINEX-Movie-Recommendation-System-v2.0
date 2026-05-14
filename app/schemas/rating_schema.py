from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional


class RatingCreate(BaseModel):
    movie_id: int
    rating:   int = Field(ge=1, le=5)


class RatingStats(BaseModel):
    avg:       float
    total:     int
    my_rating: Optional[int] = None


class CommentCreate(BaseModel):
    movie_id: int
    text:     str = Field(min_length=1, max_length=500)


class CommentOut(BaseModel):
    id:         int
    text:       str
    username:   str
    user_id:    int
    created_at: datetime
    model_config = {"from_attributes": True}
