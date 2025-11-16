"""Click tracking helpers."""

from __future__ import annotations

import shortuuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..models import Click, Offer, OfferLanding
from .saleads import SaleadsAPIClient


class ClickService:
    def __init__(self, session: AsyncSession, api_client: SaleadsAPIClient | None = None) -> None:
        self.session = session
        self.api_client = api_client or SaleadsAPIClient()

    async def create_click(
        self,
        *,
        user_id: int,
        offer: Offer,
        landing: OfferLanding | None = None,
        slot: str | None = None,
    ) -> tuple[Click, str]:
        landing_obj = landing or (offer.landings[0] if offer.landings else None)
        landing_uuid = None
        target_url = None
        if landing_obj:
            landing_uuid = getattr(landing_obj, "external_uuid", None)
            target_url = landing_obj.url
        saleads = await self.api_client.register_click(
            offer_uuid=offer.external_uuid,
            landing_uuid=landing_uuid,
            subs={"user_id": str(user_id)},
        )
        click = Click(
            user_id=user_id,
            offer_id=offer.id,
            landing_id=landing_obj.id if landing_obj else None,
            token=shortuuid.uuid(),
            saleads_click_id=saleads.get("uuid") or saleads.get("id"),
            target_url=saleads.get("redirect_url") or target_url,
            source_slot=slot,
        )
        self.session.add(click)
        await self.session.flush()
        tracking_link = f"{settings.public_base_url.rstrip('/')}/r/{click.token}"
        return click, tracking_link

    async def resolve_click(self, token: str) -> Click | None:
        stmt = select(Click).where(Click.token == token)
        return (await self.session.execute(stmt)).scalar_one_or_none()


__all__ = ["ClickService"]
