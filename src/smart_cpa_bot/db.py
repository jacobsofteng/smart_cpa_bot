"""Database utilities."""

from __future__ import annotations

from typing import AsyncIterator, Callable, TypeAlias

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from .config import settings


_engine = create_async_engine(settings.database_url, echo=False, pool_pre_ping=True)
SessionFactory = async_sessionmaker(_engine, expire_on_commit=False)
SessionDependency: TypeAlias = Callable[[], AsyncIterator[AsyncSession]]


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency helper."""

    async with SessionFactory() as session:
        yield session


__all__ = [
    "_engine",
    "SessionFactory",
    "SessionDependency",
    "get_session",
]
