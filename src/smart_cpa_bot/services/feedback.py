"""Feedback persistence."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Feedback


class FeedbackService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def submit(
        self,
        *,
        user_id: int,
        offer_id: int,
        rating: int,
        comment: str | None,
        ready_to_repeat: bool,
    ) -> Feedback:
        feedback = Feedback(
            user_id=user_id,
            offer_id=offer_id,
            rating=rating,
            comment=comment,
            ready_to_repeat=ready_to_repeat,
        )
        self.session.add(feedback)
        await self.session.flush()
        return feedback


__all__ = ["FeedbackService"]
