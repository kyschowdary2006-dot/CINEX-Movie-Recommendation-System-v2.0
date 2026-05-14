from fastapi import APIRouter
from app.api.routes import users, movies, ratings, recommend

api_router = APIRouter()

api_router.include_router(users.router)
api_router.include_router(movies.router)
api_router.include_router(ratings.router)
api_router.include_router(recommend.router)
