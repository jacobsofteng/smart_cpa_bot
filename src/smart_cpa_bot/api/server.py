"""FastAPI application with webhooks and utility endpoints."""

from __future__ import annotations

import json
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..db import _engine, get_session
from ..models import Base, PayoutStatus
from ..services.clicks import ClickService
from ..services.conversions import ConversionService
from ..services.leaderboard import LeaderboardService
from ..services.payouts import PayoutService

app = FastAPI(title="Smart CPA Bot API")


@app.on_event("startup")
async def startup() -> None:
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/leaderboard")
async def leaderboard(session: AsyncSession = Depends(get_session)) -> Any:
    service = LeaderboardService(session)
    snapshot = await service.latest()
    if not snapshot:
        snapshot = await service.generate()
    return snapshot.payload


@app.get("/r/{token}")
async def redirect_click(token: str, session: AsyncSession = Depends(get_session)):
    service = ClickService(session)
    click = await service.resolve_click(token)
    if not click or not click.target_url:
        raise HTTPException(status_code=404, detail="Click not found")
    return RedirectResponse(click.target_url)


async def _extract_payload(request: Request) -> dict[str, Any]:
    if request.headers.get("content-type", "").startswith("application/json"):
        try:
            return await request.json()
        except json.JSONDecodeError:
            return {}
    form = await request.form()
    return {key: value for key, value in form.items()}


@app.post("/webhooks/saleads/postback")
async def saleads_postback(
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    secret = request.headers.get("x-webhook-secret")
    if secret != settings.webhook_secret:
        raise HTTPException(status_code=403, detail="Invalid secret")
    payload = await _extract_payload(request)
    service = ConversionService(session)
    try:
        conversion = await service.upsert(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"status": "ok", "conversion_id": conversion.id}


@app.post("/admin/payouts/{request_id}/status")
async def update_payout_status(
    request_id: int,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    secret = request.headers.get("x-webhook-secret")
    if secret != settings.webhook_secret:
        raise HTTPException(status_code=403, detail="Invalid secret")
    payload = await _extract_payload(request)
    try:
        status = PayoutStatus(payload.get("status"))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Unknown status") from exc
    service = PayoutService(session)
    updated = await service.mark_status(request_id, status)
    return {"status": updated.status, "id": updated.id}


__all__ = ["app"]
