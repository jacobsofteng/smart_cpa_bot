"""Entrypoint for the offer board bot."""

from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage

from ..config import settings
from ..telegram.middlewares import DatabaseSessionMiddleware
from ..telegram.routers import offers_router


async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    bot = Bot(
        token=settings.offers_bot.token.get_secret_value(),
        default=DefaultBotProperties(parse_mode="HTML"),
    )
    dp = Dispatcher(storage=MemoryStorage())
    dp.update.outer_middleware(DatabaseSessionMiddleware())
    dp.include_router(offers_router)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
