"""Saleads.pro API client."""

from __future__ import annotations

import logging
from typing import Any, Dict, Iterable

import httpx
from cachetools import TTLCache

from ..config import SaleadsConfig, settings

logger = logging.getLogger(__name__)


class SaleadsAPIError(RuntimeError):
    pass


_default_client: SaleadsAPIClient | None = None


class SaleadsAPIClient:
    """Wrapper around the Saleads webmaster API."""

    def __init__(
        self,
        config: SaleadsConfig | None = None,
        *,
        timeout: float = 15.0,
    ) -> None:
        self._config = config or settings.saleads
        headers = {
            "Authorization": f"Bearer {self._config.token.get_secret_value()}",
            "Accept": "application/json",
        }
        self._client = httpx.AsyncClient(
            base_url=self._config.base_url,
            headers=headers,
            timeout=timeout,
        )
        self._offers_cache: TTLCache[str, list[dict[str, Any]]] = TTLCache(maxsize=1, ttl=300)

    async def close(self) -> None:
        await self._client.aclose()

    async def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        response = await self._client.request(method, path, **kwargs)
        if response.status_code >= 400:
            logger.error("Saleads API error %s %s: %s", method, path, response.text)
            raise SaleadsAPIError(response.text)
        return response.json()

    async def list_offers(self, *, limit: int = 200, force: bool = False, **filters: Any) -> list[dict[str, Any]]:
        """Fetch and cache active offers."""

        cache_key = "offers"
        if not force and cache_key in self._offers_cache:
            return self._offers_cache[cache_key]

        params = {"limit": limit, "offset": 0} | filters
        data = await self._request("GET", "/offer", params=params)
        offers = data.get("data") if isinstance(data, dict) else data
        if not isinstance(offers, list):
            offers = []
        self._offers_cache[cache_key] = offers
        return offers

    async def get_offer(self, offer_uuid: str) -> dict[str, Any]:
        return await self._request("GET", f"/offer/{offer_uuid}")

    async def register_click(
        self,
        *,
        offer_uuid: str,
        stand_uuid: str | None = None,
        landing_uuid: str | None = None,
        subs: Dict[str, str] | None = None,
    ) -> dict[str, Any]:
        payload = {
            "offer_uuid": offer_uuid,
            "stand_uuid": stand_uuid or self._config.default_stand_uuid,
        }
        if landing_uuid:
            payload["landing_uuid"] = landing_uuid
        if subs:
            payload["subs"] = subs
        return await self._request("POST", "/click", json=payload)

    async def list_clicks(self, **filters: Any) -> list[dict[str, Any]]:
        data = await self._request("GET", "/click", params=filters)
        return data.get("data", data)

    async def list_conversions(self, **filters: Any) -> list[dict[str, Any]]:
        data = await self._request("GET", "/conversion", params=filters)
        return data.get("data", data)

    async def get_dictionaries(self, dict_names: Iterable[str]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for name in dict_names:
            result[name] = await self._request("GET", f"/dict/{name}")
        return result


__all__ = ["SaleadsAPIClient", "SaleadsAPIError", "get_saleads_client"]


def get_saleads_client() -> SaleadsAPIClient:
    global _default_client
    if _default_client is None:
        _default_client = SaleadsAPIClient()
    return _default_client
