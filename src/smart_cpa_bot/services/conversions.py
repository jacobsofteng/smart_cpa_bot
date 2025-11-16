"""Conversion tracking and ledger sync."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Click, Conversion, ConversionStatus, LedgerEntryType
from .balances import BalanceService


class ConversionService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.balance_service = BalanceService(session)

    async def upsert(self, payload: dict[str, Any]) -> Conversion:
        click_uuid = payload.get("click_id") or payload.get("click_uuid")
        external_id = payload.get("conversion_id") or payload.get("goal_id")
        amount = int(float(payload.get("amount") or payload.get("payout") or 0))
        currency = payload.get("currency", "RUB")
        status_raw = (payload.get("status") or "pending").lower()
        try:
            status = ConversionStatus(status_raw)
        except ValueError:
            status = ConversionStatus.PENDING
        click = await self._find_click(click_uuid)
        if not click:
            raise ValueError("Click not found for conversion")
        conversion = await self._find_conversion(external_id, click.id)
        if not conversion:
            conversion = Conversion(
                user_id=click.user_id,
                offer_id=click.offer_id,
                click_id=click.id,
                external_id=external_id,
                status=status,
                amount_netto=amount,
                currency=currency,
                raw_payload=payload,
            )
            self.session.add(conversion)
            await self.session.flush()
            await self._handle_initial_status(conversion)
            return conversion
        previous_status = conversion.status
        conversion.status = status
        conversion.amount_netto = amount
        conversion.currency = currency
        conversion.raw_payload = payload
        await self._handle_transition(conversion, previous_status, status)
        await self.session.flush()
        return conversion

    async def _handle_initial_status(self, conversion: Conversion) -> None:
        if conversion.status == ConversionStatus.PENDING:
            await self.balance_service.add_entry(
                user_id=conversion.user_id,
                entry_type=LedgerEntryType.ADJUST,
                amount=conversion.amount_netto,
                reference_type="conversion",
                reference_id=str(conversion.id),
                notes="pending_conversion",
            )
        elif conversion.status == ConversionStatus.APPROVED:
            await self.balance_service.add_entry(
                user_id=conversion.user_id,
                entry_type=LedgerEntryType.CREDIT,
                amount=conversion.amount_netto,
                reference_type="conversion",
                reference_id=str(conversion.id),
                notes="conversion_approved",
            )

    async def _handle_transition(
        self,
        conversion: Conversion,
        previous: ConversionStatus,
        current: ConversionStatus,
    ) -> None:
        if previous == ConversionStatus.PENDING:
            await self.balance_service.add_entry(
                user_id=conversion.user_id,
                entry_type=LedgerEntryType.ADJUST,
                amount=-conversion.amount_netto,
                reference_type="conversion",
                reference_id=str(conversion.id),
                notes="pending_released",
            )
        if current == ConversionStatus.APPROVED:
            await self.balance_service.add_entry(
                user_id=conversion.user_id,
                entry_type=LedgerEntryType.CREDIT,
                amount=conversion.amount_netto,
                reference_type="conversion",
                reference_id=str(conversion.id),
                notes="conversion_approved",
            )

    async def _find_click(self, saleads_click_id: str | None) -> Click | None:
        if not saleads_click_id:
            return None
        stmt = select(Click).where(Click.saleads_click_id == saleads_click_id)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def _find_conversion(self, external_id: str | None, click_id: int) -> Conversion | None:
        if not external_id:
            stmt = select(Conversion).where(Conversion.click_id == click_id)
        else:
            stmt = select(Conversion).where(Conversion.external_id == external_id)
        return (await self.session.execute(stmt)).scalar_one_or_none()


__all__ = ["ConversionService"]
