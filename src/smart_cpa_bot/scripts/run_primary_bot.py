"""Entrypoint for the onboarding bot."""

from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage

from ..config import settings
from ..services.llm import LLMService
from ..telegram.middlewares import DatabaseSessionMiddleware
from ..telegram.routers import primary_router


async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    bot = Bot(
        token=settings.primary_bot.token.get_secret_value(),
        default=DefaultBotProperties(parse_mode="HTML"),
    )
    dp = Dispatcher(storage=MemoryStorage())
    dp.update.outer_middleware(DatabaseSessionMiddleware())
    dp.include_router(primary_router)
    llm_service = LLMService()
    try:
        await dp.start_polling(bot, llm_service=llm_service)
    finally:
        await llm_service.close()


if __name__ == "__main__":
    asyncio.run(main())
