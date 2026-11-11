import asyncio
import hashlib
import logging
import os

from aiohttp import ClientSession, ClientTimeout, web
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

from config import BOT_TOKEN
from database import init_db
from handlers import commands, messages

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
log = logging.getLogger("bot")

# На хостинге Render эти переменные задаются автоматически.
# Если их нет (Replit, свой компьютер) — бот работает по-старому, через polling.
BASE_URL = os.getenv("RENDER_EXTERNAL_URL", "").rstrip("/")
PORT = int(os.getenv("PORT", "10000"))
SECRET = hashlib.sha256(BOT_TOKEN.encode()).hexdigest()[:40]
WEBHOOK_PATH = f"/webhook/{SECRET}"
PING_EVERY = 600  # секунд; Render усыпляет сервис после 15 минут без входящих запросов


def build_dispatcher() -> Dispatcher:
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(commands.router)
    dp.include_router(messages.router)
    return dp


async def keep_awake():
    """Раз в 10 минут обращаемся к собственному адресу, чтобы сервис не засыпал."""
    async with ClientSession(timeout=ClientTimeout(total=30)) as session:
        while True:
            await asyncio.sleep(PING_EVERY)
            try:
                async with session.get(f"{BASE_URL}/") as resp:
                    log.info("Самопроверка: %s", resp.status)
            except Exception as e:
                log.warning("Самопроверка не удалась: %s", e)


async def health(_request: web.Request) -> web.Response:
    return web.Response(text="ok")


def run_webhook():
    bot = Bot(token=BOT_TOKEN)
    dp = build_dispatcher()
    tasks = []

    async def on_startup():
        await init_db()
        await bot.set_webhook(
            f"{BASE_URL}{WEBHOOK_PATH}",
            secret_token=SECRET,
            allowed_updates=dp.resolve_used_update_types(),
        )
        tasks.append(asyncio.create_task(keep_awake()))
        log.info("Бот запущен! Режим: webhook (%s)", BASE_URL)

    async def on_shutdown():
        # Webhook не удаляем: следующее сообщение от Telegram само разбудит сервис.
        for t in tasks:
            t.cancel()

    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    app = web.Application()
    app.router.add_get("/", health)
    app.router.add_get("/healthz", health)
    SimpleRequestHandler(dispatcher=dp, bot=bot, secret_token=SECRET).register(app, path=WEBHOOK_PATH)
    setup_application(app, dp, bot=bot)
    web.run_app(app, host="0.0.0.0", port=PORT, print=None, access_log=None)


async def run_polling():
    await init_db()
    bot = Bot(token=BOT_TOKEN)
    dp = build_dispatcher()
    log.info("Бот запущен! Режим: polling")
    await dp.start_polling(bot)


if __name__ == "__main__":
    if BASE_URL:
        run_webhook()
    else:
        asyncio.run(run_polling())
