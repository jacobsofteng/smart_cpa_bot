"""Telegram routers."""

from .primary import router as primary_router
from .offers import router as offers_router

__all__ = ["primary_router", "offers_router"]
