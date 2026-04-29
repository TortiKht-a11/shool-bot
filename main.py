from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.dispatcher.middlewares.base import BaseMiddleware
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Update

from config import load_config
from db import init_db
from handlers import admin_router, common_router, parent_router
from utils.texts import ERROR_FRIENDLY


class ErrorMiddleware(BaseMiddleware):
    """Catches unhandled exceptions and logs them."""

    def __init__(self, logger: logging.Logger) -> None:
        self._logger = logger

    async def __call__(self, handler, event, data):
        try:
            return await handler(event, data)
        except Exception:
            self._logger.exception("Unhandled exception: event=%r", event)
            bot: Bot | None = data.get("bot")
            if bot is not None:
                try:
                    if hasattr(event, "message") and event.message:
                        await event.message.answer(ERROR_FRIENDLY)
                    elif hasattr(event, "callback_query") and event.callback_query:
                        await event.callback_query.message.answer(ERROR_FRIENDLY)  # type: ignore[union-attr]
                except Exception:
                    self._logger.exception("Failed to send friendly error message")
            return None


def setup_logging() -> None:
    log_fmt = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    root = logging.getLogger()
    root.setLevel(logging.INFO)

    stream = logging.StreamHandler(sys.stdout)
    stream.setFormatter(logging.Formatter(log_fmt))
    stream.setLevel(logging.INFO)

    file_handler = logging.FileHandler("bot.log", encoding="utf-8")
    file_handler.setFormatter(logging.Formatter(log_fmt))
    file_handler.setLevel(logging.INFO)

    root.handlers.clear()
    root.addHandler(stream)
    root.addHandler(file_handler)


async def main() -> None:
    setup_logging()
    logger = logging.getLogger("main")

    config = load_config()
    config.uploads_dir.mkdir(parents=True, exist_ok=True)
    await init_db(str(config.db_path))

    bot = Bot(
        token=config.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    dp = Dispatcher(storage=MemoryStorage())
    dp.update.middleware(ErrorMiddleware(logging.getLogger("errors")))

    dp["config"] = config
    dp.include_router(common_router)
    dp.include_router(parent_router)
    dp.include_router(admin_router)

    logger.info("Bot started")
    await dp.start_polling(bot, allowed_updates=Update.model_fields.keys())


if __name__ == "__main__":
    asyncio.run(main())
