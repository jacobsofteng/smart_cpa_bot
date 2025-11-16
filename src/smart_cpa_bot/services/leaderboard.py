"""Leaderboard generation."""

from __future__ import annotations

from datetime import date

from sqlalchemy import Select, case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..models import BalanceLedger, LeaderboardSnapshot, LedgerEntryType, User


class LeaderboardService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def generate(self, *, limit: int | None = None) -> LeaderboardSnapshot:
        limit = limit or settings.leaderboard_size
        score_expr = func.coalesce(
            func.sum(
                case(
                    (BalanceLedger.type == LedgerEntryType.CREDIT, BalanceLedger.amount),
                    (BalanceLedger.type == LedgerEntryType.DEBIT, -BalanceLedger.amount),
                    (BalanceLedger.type == LedgerEntryType.LOCK, -BalanceLedger.amount),
                    (BalanceLedger.type == LedgerEntryType.UNLOCK, BalanceLedger.amount),
                    else_=0,
                )
            ),
            0,
        ).label("score")
        stmt: Select = (
            select(
                User.id,
                User.display_name,
                score_expr,
            )
            .select_from(User)
            .join(BalanceLedger, BalanceLedger.user_id == User.id, isouter=True)
            .group_by(User.id)
            .order_by(score_expr.desc())
            .limit(limit)
        )
        rows = (await self.session.execute(stmt)).all()
        payload = [
            {
                "user_id": user_id,
                "name": name,
                "score": int(score or 0),
            }
            for user_id, name, score in rows
        ]
        snapshot = LeaderboardSnapshot(date=str(date.today()), payload=payload)
        self.session.add(snapshot)
        await self.session.flush()
        return snapshot

    async def latest(self) -> LeaderboardSnapshot | None:
        stmt = select(LeaderboardSnapshot).order_by(LeaderboardSnapshot.id.desc()).limit(1)
        return (await self.session.execute(stmt)).scalar_one_or_none()


__all__ = ["LeaderboardService"]
