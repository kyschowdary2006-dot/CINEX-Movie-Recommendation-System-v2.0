from app.db.database import engine, Base
from app.core.logging import logger

# Import all models so Base knows about them before create_all
import app.models.user    # noqa: F401
import app.models.movie   # noqa: F401
import app.models.rating  # noqa: F401


def init_db() -> None:
    """Create all tables in users.db if they don't exist."""
    logger.info("[init_db] Creating tables in users.db …")
    Base.metadata.create_all(bind=engine)
    logger.info("[init_db] Done.")
