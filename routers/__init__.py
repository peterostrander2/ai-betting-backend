"""
ROUTERS - FastAPI Router Modules

This package contains FastAPI routers split from the monolithic live_data_router.py
for better maintainability and separation of concerns.

Usage:
    from routers import community_router

    app.include_router(community_router, prefix="/live")
"""

from .community import router as community_router

__all__ = [
    'community_router',
]
