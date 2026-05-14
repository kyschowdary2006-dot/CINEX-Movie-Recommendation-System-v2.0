"""
Central dependency injection module.
Import get_db and auth helpers from here in route files.
"""
from app.db.database import get_db          # noqa: F401 — re-exported
from app.core.security import (             # noqa: F401 — re-exported
    get_current_user,
    get_optional_user,
)
