from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class MovieOut(BaseModel):
    id:           int
    title:        str
    overview:     Optional[str] = None
    genres:       Optional[str] = None
    poster_path:  Optional[str] = None
    vote_average: Optional[float] = None
    release_date: Optional[str]  = None
    model_config = {"from_attributes": True}


class WatchlistAdd(BaseModel):
    movie_id:    int
    title:       str
    poster_path: Optional[str] = None


class WatchlistItem(BaseModel):
    movie_id:    int
    title:       str
    poster_path: Optional[str]
    added_at:    datetime
    model_config = {"from_attributes": True}
