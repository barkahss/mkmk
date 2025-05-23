"""
API Routes sub-package for the AI Scraper Framework.

This package aggregates all API router modules. The main router
from `scraper_routes.py` is re-exported here for inclusion
in the main FastAPI application setup (`api/main.py`).
"""

from .scraper_routes import router as scraper_router # Rename to avoid potential clashes if other routers are added

__all__ = [
    "scraper_router",
]
