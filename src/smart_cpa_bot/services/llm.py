"""LLM helper for the primary bot."""

from __future__ import annotations

import asyncio
import logging
from typing import Iterable

import httpx

from ..config import settings

logger = logging.getLogger(__name__)

STOP_KEYWORDS = {
    "политик",
    "насилие",
    "террор",
    "экстремизм",
    "бомб",
    "оруж",
    "фарм",
    "мошеннич",
    "медицин",
    "порн",
}

SYSTEM_PROMPT = """
Ты — вежливый ассистент витрины заданий CPA. Отвечай 1–2 короткими предложениями.
Не придумывай ссылки, суммы, статус баланса и бонусов — укажи, что этим занимается раздел «Баланс».
Если пользователь просит подсказать задания или заработать, мягко предложи «подберу задания с баллами».
Поддерживай короткий smalltalk и задавай не больше одного уточняющего вопроса.
Избегай императивов, не оценивай финансовую надёжность и не обещай результата.
""".strip()


class LLMService:
    def __init__(self, *, endpoint: str | None = None) -> None:
        self._client = httpx.AsyncClient(timeout=settings.llm.timeout)
        self._endpoint = endpoint or settings.llm.endpoint

    async def generate(self, messages: Iterable[dict[str, str]]) -> str:
        if not messages:
            return ""
        payload = {
            "model": settings.llm.model,
            "temperature": settings.llm.temperature,
            "max_tokens": settings.llm.max_tokens,
            "messages": [{"role": "system", "content": SYSTEM_PROMPT}] + list(messages),
        }
        try:
            response = await self._client.post(self._endpoint, json=payload)
            response.raise_for_status()
        except httpx.HTTPError as exc:  # pragma: no cover
            logger.error("LLM request failed: %s", exc)
            return "Немного перегружен. Попробуем ещё раз через минуту?"
        data = response.json()
        if isinstance(data, dict):
            choices = data.get("choices")
            if choices:
                return choices[0]["message"].get("content", "").strip()
            if data.get("message"):
                return data["message"]
        return "Готов помочь с подбором заданий и баллами."

    def violates_policy(self, text: str) -> bool:
        lowered = text.lower()
        return any(keyword in lowered for keyword in STOP_KEYWORDS)

    async def close(self) -> None:
        await self._client.aclose()


__all__ = ["LLMService", "SYSTEM_PROMPT"]
