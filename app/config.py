from pydantic_settings import BaseSettings
from pathlib import Path
from functools import lru_cache


class Settings(BaseSettings):
    APP_NAME: str = "CINEX"
    APP_VERSION: str = "2.0"
    DEBUG: bool = True

    # Database
    DATABASE_URL: str = "sqlite:///./users.db"

    # JWT
    SECRET_KEY: str = "cinex-super-secret-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_DAYS: int = 7

    # TMDB
    TMDB_API_KEY: str = "9e3656f495ccd03d580d88c34715d4a0"
    TMDB_BASE_URL: str = "https://api.themoviedb.org/3"

    # EmailJS
    EMAILJS_PUBLIC_KEY: str = "nND4Wew7AcSBmNkXn"
    EMAILJS_SERVICE_ID: str = "service_vz2h2p6"
    EMAILJS_TEMPLATE_ID: str = "template_6xnh3sa"

    # ML
    ML_STORE_DIR: str = "app/ml/store"
    TMDB_FETCH_PAGES: int = 25
    MIN_RATINGS_FOR_COLLAB: int = 5
    SVD_FACTORS: int = 50

    # AI Agent — free key from console.groq.com
    GROQ_API_KEY: str = "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"

    @property
    def ml_store_path(self) -> Path:
        p = Path(self.ML_STORE_DIR)
        p.mkdir(parents=True, exist_ok=True)
        return p

    model_config = {"env_file": ".env", "extra": "ignore"}


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
