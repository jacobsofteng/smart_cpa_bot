"""Offer synchronisation and scoring logic."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Offer, OfferLanding, OfferStatus, User
from .saleads import SaleadsAPIClient, get_saleads_client


@dataclass(slots=True)
class OfferPresentation:
    id: int
    external_uuid: str
    title: str
    payout: int
    description: str
    landing_url: str | None


class OfferService:
    def __init__(self, session: AsyncSession, api_client: SaleadsAPIClient | None = None) -> None:
        self.session = session
        self.api_client = api_client or get_saleads_client()

    async def sync_from_saleads(self, *, force: bool = False) -> None:
        offers = await self.api_client.list_offers(force=force)
        for payload in offers:
            await self._upsert_offer(payload)

    async def _upsert_offer(self, payload: dict) -> Offer:
        external_uuid = payload.get("uuid") or payload.get("offer_uuid")
        if not external_uuid:
            raise ValueError("Saleads offer payload does not contain uuid")
        stmt = select(Offer).where(Offer.external_uuid == external_uuid)
        existing = (await self.session.execute(stmt)).scalar_one_or_none()
        if existing:
            offer = existing
        else:
            offer = Offer(external_uuid=external_uuid, title=payload.get("name", ""))
            self.session.add(offer)

        offer.title = payload.get("name") or offer.title
        offer.category = payload.get("category") or payload.get("verticalName")
        limits = payload.get("limits") or {}
        offer.min_age = limits.get("ageMin") or limits.get("age", {}).get("min") or 18
        offer.max_age = limits.get("ageMax") or limits.get("age", {}).get("max")
        offer.geo_text = payload.get("geoText")
        offer.city_whitelist = payload.get("cities")
        goals = payload.get("goals") or []
        if isinstance(goals, dict):  # when API returns mapping keyed by goal id
            top_goal = next(iter(goals.values()), {})
        else:
            top_goal = goals[0] if goals else {}
        offer.payout_brutto = int(top_goal.get("price") or top_goal.get("payout", 0))
        offer.expected_score = int(payload.get("stats", {}).get("avgPrice", offer.payout_brutto))
        offer.features = payload.get("features")
        offer.schedule = payload.get("schedule")
        offer.metadata_json = payload

        await self.session.flush()
        await self._sync_landings(offer, payload.get("landings") or [])
        return offer

    async def _sync_landings(self, offer: Offer, landings_payload: Iterable[dict]) -> None:
        await self.session.execute(
            delete(OfferLanding).where(OfferLanding.offer_id == offer.id)
        )
        for landing in landings_payload:
            model = OfferLanding(
                offer_id=offer.id,
                external_uuid=landing.get("uuid") or landing.get("landing_uuid"),
                url=landing.get("url") or landing.get("link") or "",
                title=landing.get("name") or landing.get("title"),
                geo=landing.get("geo"),
            )
            self.session.add(model)
        await self.session.flush()

    async def get_personalized_offers(self, user: User, *, limit: int = 3) -> list[OfferPresentation]:
        stmt = select(Offer).where(Offer.status == OfferStatus.ACTIVE)
        offers = list((await self.session.execute(stmt)).scalars())
        if not offers:
            await self.sync_from_saleads(force=True)
            offers = list((await self.session.execute(stmt)).scalars())
        scored = [
            (self._score_offer(offer, user), offer)
            for offer in offers
            if self._is_offer_allowed(offer, user)
        ]
        scored.sort(key=lambda item: item[0], reverse=True)
        result: list[OfferPresentation] = []
        for _, offer in scored[:limit]:
            landing_url = offer.landings[0].url if offer.landings else None
            result.append(
                OfferPresentation(
                    id=offer.id,
                    external_uuid=offer.external_uuid,
                    title=offer.title,
                    payout=offer.payout_brutto,
                    description=(offer.metadata_json or {}).get("offerDescription", ""),
                    landing_url=landing_url,
                )
            )
        return result

    def _is_offer_allowed(self, offer: Offer, user: User) -> bool:
        if offer.min_age and user.age and user.age < offer.min_age:
            return False
        if offer.max_age and user.age and user.age > offer.max_age:
            return False
        if offer.city_whitelist and user.city:
            normalized = {city.lower() for city in offer.city_whitelist}
            if user.city.lower() not in normalized:
                return False
        return True

    def _score_offer(self, offer: Offer, user: User) -> int:
        base = offer.expected_score or offer.payout_brutto
        bonus = 0
        if user.city and offer.geo_text and user.city.lower() in offer.geo_text.lower():
            bonus += 25
        if offer.metadata_json and offer.metadata_json.get("goals"):
            bonus += len(offer.metadata_json["goals"]) * 5
        return base + bonus


__all__ = ["OfferService", "OfferPresentation"]
