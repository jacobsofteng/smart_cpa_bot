"""Payout workflow services."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..models import LedgerEntryType, PayoutMethod, PayoutRequest, PayoutStatus
from .balances import BalanceService


class PayoutValidationError(ValueError):
    """Raised when payout arguments are invalid."""


PAYOUT_LIMITS = {
    PayoutMethod.OZON: [700, 1000, 1500, 2000, 3000, 3500, 4000, 5000, 8000, 10000],
    PayoutMethod.WB: [1000, 2000, 3000, 5000, 8000, 10000],
    PayoutMethod.GOLD_APPLE: None,
    PayoutMethod.DIRECT: None,
}


@dataclass
class PayoutResult:
    request: PayoutRequest
    locked_amount: int


class PayoutService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.balance_service = BalanceService(session)

    async def create_request(
        self,
        *,
        user_id: int,
        method: PayoutMethod,
        amount: int,
        phone: str,
        email: str,
    ) -> PayoutResult:
        if amount < settings.payout_minimum:
            raise PayoutValidationError("Минимальный вывод — 700 баллов")
        allowed = PAYOUT_LIMITS.get(method)
        if allowed and amount not in allowed:
            raise PayoutValidationError("Для выбранного метода доступны фиксированные номиналы")
        snapshot = await self.balance_service.snapshot(user_id)
        if amount > snapshot.available:
            raise PayoutValidationError("Недостаточно баллов на балансе")
        lock_entry = await self.balance_service.add_entry(
            user_id=user_id,
            entry_type=LedgerEntryType.LOCK,
            amount=amount,
            reference_type="payout",
        )
        request = PayoutRequest(
            user_id=user_id,
            method=method,
            amount=amount,
            denomination=amount,
            phone=phone,
            email=email,
            status=PayoutStatus.PENDING,
        )
        self.session.add(request)
        await self.session.flush()
        lock_entry.reference_id = str(request.id)
        await self.session.flush()
        return PayoutResult(request=request, locked_amount=amount)

    async def mark_status(self, request_id: int, status: PayoutStatus) -> PayoutRequest:
        request = await self.session.get(PayoutRequest, request_id)
        if not request:
            raise PayoutValidationError("Заявка не найдена")
        request.status = status
        if status == PayoutStatus.ISSUED:
            await self.balance_service.add_entry(
                user_id=request.user_id,
                entry_type=LedgerEntryType.UNLOCK,
                amount=request.amount,
                reference_type="payout",
                reference_id=str(request.id),
                notes="unlock_after_issue",
            )
            await self.balance_service.add_entry(
                user_id=request.user_id,
                entry_type=LedgerEntryType.DEBIT,
                amount=request.amount,
                reference_type="payout",
                reference_id=str(request.id),
                notes="payout_debit",
            )
        elif status == PayoutStatus.FAILED:
            await self.balance_service.add_entry(
                user_id=request.user_id,
                entry_type=LedgerEntryType.UNLOCK,
                amount=request.amount,
                reference_type="payout",
                reference_id=str(request.id),
                notes="payout_failed_unlock",
            )
        await self.session.flush()
        return request


__all__ = [
    "PayoutService",
    "PayoutResult",
    "PayoutValidationError",
]
