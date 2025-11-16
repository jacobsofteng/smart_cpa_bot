"""Recommendation session helpers."""

from __future__ import annotations

from datetime import datetime, timedelta

import shortuuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import RecommendationSession


class RecommendationService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_session(self, *, user_id: int, items: list[dict]) -> RecommendationSession:
        token = shortuuid.uuid()
        session = RecommendationSession(
            user_id=user_id,
            token=token,
            payload={"items": items},
            expires_at=datetime.utcnow() + timedelta(hours=2),
        )
        self.session.add(session)
        await self.session.flush()
        return session

    async def get_session(self, token: str) -> RecommendationSession | None:
        stmt = select(RecommendationSession).where(RecommendationSession.token == token)
        return (await self.session.execute(stmt)).scalar_one_or_none()


__all__ = ["RecommendationService"]
