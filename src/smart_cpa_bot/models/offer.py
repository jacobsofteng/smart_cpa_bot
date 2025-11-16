"""Offer and tracking models."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin


class OfferStatus(str, Enum):
    ACTIVE = "active"
    PAUSED = "paused"


class Offer(TimestampMixin, Base):
    __tablename__ = "offers"

    id: Mapped[int] = mapped_column(primary_key=True)
    external_uuid: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(255))
    category: Mapped[Optional[str]] = mapped_column(String(128))
    min_age: Mapped[int] = mapped_column(Integer, default=18)
    max_age: Mapped[Optional[int]] = mapped_column(Integer)
    geo_text: Mapped[Optional[str]] = mapped_column(String(255))
    city_whitelist: Mapped[list[str] | None] = mapped_column(JSON)
    payout_brutto: Mapped[int] = mapped_column(Integer, default=0)
    expected_score: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[OfferStatus] = mapped_column(default=OfferStatus.ACTIVE)
    partner_id: Mapped[Optional[str]] = mapped_column(String(64))
    features: Mapped[dict | None] = mapped_column(JSON, default=dict)
    schedule: Mapped[dict | None] = mapped_column(JSON)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, default=dict)

    landings: Mapped[list["OfferLanding"]] = relationship(
        back_populates="offer", cascade="all, delete-orphan"
    )
    clicks: Mapped[list["Click"]] = relationship(back_populates="offer")


class OfferLanding(TimestampMixin, Base):
    __tablename__ = "offer_landings"

    id: Mapped[int] = mapped_column(primary_key=True)
    offer_id: Mapped[int] = mapped_column(ForeignKey("offers.id", ondelete="CASCADE"))
    external_uuid: Mapped[str | None] = mapped_column(String(64), index=True)
    url: Mapped[str] = mapped_column(Text)
    title: Mapped[Optional[str]] = mapped_column(String(255))
    geo: Mapped[Optional[str]] = mapped_column(String(64))

    offer: Mapped[Offer] = relationship(back_populates="landings")


class ClickStatus(str, Enum):
    SENT = "sent"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"


class Click(TimestampMixin, Base):
    __tablename__ = "clicks"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    offer_id: Mapped[int] = mapped_column(ForeignKey("offers.id"), index=True)
    landing_id: Mapped[Optional[int]] = mapped_column(ForeignKey("offer_landings.id"))
    token: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    saleads_click_id: Mapped[Optional[str]] = mapped_column(String(128), index=True)
    target_url: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[ClickStatus] = mapped_column(default=ClickStatus.SENT)
    source_slot: Mapped[str | None] = mapped_column(String(32))

    offer: Mapped[Offer] = relationship(back_populates="clicks")


class ConversionStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    HOLD = "hold"


class Conversion(TimestampMixin, Base):
    __tablename__ = "conversions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    offer_id: Mapped[int] = mapped_column(ForeignKey("offers.id"))
    click_id: Mapped[int] = mapped_column(ForeignKey("clicks.id"))
    external_id: Mapped[Optional[str]] = mapped_column(String(128), index=True)
    status: Mapped[ConversionStatus] = mapped_column(default=ConversionStatus.PENDING)
    amount_netto: Mapped[int] = mapped_column(Integer, default=0)
    currency: Mapped[str] = mapped_column(String(8), default="RUB")
    raw_payload: Mapped[dict | None] = mapped_column(JSON)
    eta_date: Mapped[Optional[datetime]] = mapped_column()


class RecommendationSession(TimestampMixin, Base):
    __tablename__ = "recommendation_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    token: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    payload: Mapped[dict] = mapped_column(JSON)
    expires_at: Mapped[Optional[datetime]] = mapped_column()


__all__ = [
    "Offer",
    "OfferLanding",
    "Click",
    "Conversion",
    "RecommendationSession",
    "OfferStatus",
    "ClickStatus",
    "ConversionStatus",
]
