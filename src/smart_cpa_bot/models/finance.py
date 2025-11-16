"""Balance and payout models."""

from __future__ import annotations

from enum import Enum
from typing import Optional

from sqlalchemy import ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin


class LedgerEntryType(str, Enum):
    CREDIT = "credit"
    DEBIT = "debit"
    LOCK = "lock"
    UNLOCK = "unlock"
    ADJUST = "adjust"


class BalanceLedger(TimestampMixin, Base):
    __tablename__ = "balances_ledger"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    type: Mapped[LedgerEntryType]
    amount: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(8), default="RUB")
    reference_type: Mapped[Optional[str]] = mapped_column(String(64))
    reference_id: Mapped[Optional[str]] = mapped_column(String(64))
    notes: Mapped[Optional[str]] = mapped_column(Text)


class PayoutMethod(str, Enum):
    DIRECT = "direct"
    OZON = "ozon"
    WB = "wb"
    GOLD_APPLE = "golden_apple"


class PayoutStatus(str, Enum):
    PENDING = "pending"
    APPROVED_INTERNAL = "approved_internal"
    ISSUED = "issued"
    FAILED = "failed"


class PayoutRequest(TimestampMixin, Base):
    __tablename__ = "payout_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    method: Mapped[PayoutMethod]
    amount: Mapped[int] = mapped_column(Integer)
    denomination: Mapped[int | None] = mapped_column(Integer)
    phone: Mapped[Optional[str]] = mapped_column(String(32))
    email: Mapped[Optional[str]] = mapped_column(String(255))
    status: Mapped[PayoutStatus] = mapped_column(default=PayoutStatus.PENDING)
    payload: Mapped[dict | None] = mapped_column(JSON)


__all__ = [
    "BalanceLedger",
    "LedgerEntryType",
    "PayoutMethod",
    "PayoutRequest",
    "PayoutStatus",
]
