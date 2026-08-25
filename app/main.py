"""Запуск manage_bot: Telegram-поллинг + HTTP для заявок с сайта.

    python -m app.main
"""
import logging
from contextlib import suppress

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from . import storage
from .config import BOT_TOKEN, WEB_PORT
from .handlers import router
from .web import build_app

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
log = logging.getLogger("manage_bot")


async def main() -> None:
    storage.init_db()
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()
    dp.include_router(router)

    app = build_app(bot)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host="0.0.0.0", port=WEB_PORT)
    await site.start()
    log.info("HTTP endpoint on :%s (POST /apply)", WEB_PORT)

    with suppress(KeyboardInterrupt):
        await dp.start_polling(bot)
    await runner.cleanup()
    await bot.session.close()


if __name__ == "__main__":
    import asyncio
    import sys

    from aiohttp import web

    sys.exit(asyncio.run(main()))