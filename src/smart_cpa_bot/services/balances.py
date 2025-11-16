"""Balance ledger helpers."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import Select, case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import BalanceLedger, LedgerEntryType


@dataclass(slots=True)
class BalanceSnapshot:
    available: int
    pending: int
    locked: int


class BalanceService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def snapshot(self, user_id: int) -> BalanceSnapshot:
        available_stmt: Select = select(
            func.coalesce(
                func.sum(
                    case(
                        (BalanceLedger.type == LedgerEntryType.CREDIT, BalanceLedger.amount),
                        (BalanceLedger.type == LedgerEntryType.DEBIT, -BalanceLedger.amount),
                        (BalanceLedger.type == LedgerEntryType.UNLOCK, BalanceLedger.amount),
                        (BalanceLedger.type == LedgerEntryType.LOCK, -BalanceLedger.amount),
                        else_=0,
                    )
                ),
                0,
            )
        ).where(BalanceLedger.user_id == user_id)
        available = (await self.session.execute(available_stmt)).scalar_one()

        locked_stmt: Select = select(
            func.coalesce(
                func.sum(
                    case(
                        (BalanceLedger.type == LedgerEntryType.LOCK, BalanceLedger.amount),
                        (BalanceLedger.type == LedgerEntryType.UNLOCK, -BalanceLedger.amount),
                        else_=0,
                    )
                ),
                0,
            )
        ).where(BalanceLedger.user_id == user_id)
        locked = (await self.session.execute(locked_stmt)).scalar_one()

        pending_stmt: Select = select(
            func.coalesce(
                func.sum(
                    case(
                        (BalanceLedger.type == LedgerEntryType.ADJUST, BalanceLedger.amount),
                        else_=0,
                    )
                ),
                0,
            )
        ).where(BalanceLedger.user_id == user_id)
        pending = (await self.session.execute(pending_stmt)).scalar_one()
        return BalanceSnapshot(
            available=int(available or 0),
            pending=int(pending or 0),
            locked=int(locked or 0),
        )

    async def add_entry(
        self,
        *,
        user_id: int,
        entry_type: LedgerEntryType,
        amount: int,
        reference_type: str | None = None,
        reference_id: str | None = None,
        notes: str | None = None,
    ) -> BalanceLedger:
        entry = BalanceLedger(
            user_id=user_id,
            type=entry_type,
            amount=amount,
            reference_type=reference_type,
            reference_id=reference_id,
            notes=notes,
        )
        self.session.add(entry)
        await self.session.flush()
        return entry


__all__ = ["BalanceService", "BalanceSnapshot"]
