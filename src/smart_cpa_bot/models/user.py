"""User-centric models."""

from __future__ import annotations

from enum import Enum
from typing import Optional

from sqlalchemy import BigInteger, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin


class UserStatus(str, Enum):
    NEW = "new"
    ONBOARDED = "onboarded"
    BLOCKED = "blocked"


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    username: Mapped[Optional[str]] = mapped_column(String(64))
    first_name: Mapped[Optional[str]] = mapped_column(String(128))
    last_name: Mapped[Optional[str]] = mapped_column(String(128))
    display_name: Mapped[str] = mapped_column(String(128), default="")
    age: Mapped[Optional[int]] = mapped_column(Integer)
    city: Mapped[Optional[str]] = mapped_column(String(128))
    phone: Mapped[Optional[str]] = mapped_column(String(32))
    email: Mapped[Optional[str]] = mapped_column(String(255))
    consents: Mapped[dict | None] = mapped_column(JSON, default=dict)
    status: Mapped[UserStatus] = mapped_column(default=UserStatus.NEW)
    referral_code: Mapped[str] = mapped_column(String(32), unique=True)
    referred_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"))
    notes: Mapped[Optional[str]] = mapped_column(Text)

    referred_by: Mapped["User | None"] = relationship(
        remote_side="User.id", foreign_keys=[referred_by_id]
    )
    referrals: Mapped[list["Referral"]] = relationship(
        back_populates="referrer",
        cascade="all, delete-orphan",
        foreign_keys="Referral.referrer_user_id",
    )


class ReferralStatus(str, Enum):
    ATTRIBUTED = "attributed"
    QUALIFIED = "qualified"
    REWARDED = "rewarded"


class Referral(TimestampMixin, Base):
    __tablename__ = "referrals"

    id: Mapped[int] = mapped_column(primary_key=True)
    referrer_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    referee_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    code: Mapped[str] = mapped_column(String(32), index=True)
    status: Mapped[ReferralStatus] = mapped_column(default=ReferralStatus.ATTRIBUTED)
    reward_fixed: Mapped[int] = mapped_column(Integer, default=0)
    reward_percent_amount: Mapped[int] = mapped_column(Integer, default=0)

    referrer: Mapped[User] = relationship(
        foreign_keys=[referrer_user_id], back_populates="referrals"
    )
    referee: Mapped[User] = relationship(foreign_keys=[referee_user_id])


__all__ = ["User", "UserStatus", "Referral", "ReferralStatus"]
