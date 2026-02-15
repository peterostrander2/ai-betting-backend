"""
ROUTERS - FastAPI Router Modules

This package contains FastAPI routers split from the monolithic live_data_router.py
for better maintainability and separation of concerns.

Usage:
    from routers import community_router, esoteric_router, line_shop_router

    app.include_router(community_router, prefix="/live")
    app.include_router(esoteric_router, prefix="/live")
    app.include_router(line_shop_router, prefix="/live")
"""

from .community import router as community_router
from .esoteric import router as esoteric_router
from .line_shop import router as line_shop_router

__all__ = [
    'community_router',
    'esoteric_router',
    'line_shop_router',
]
