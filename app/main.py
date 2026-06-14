import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from app.config.settings import get_settings
from app.database.middleware import DbSessionMiddleware
from app.database.session import async_session_maker, create_db, dispose_db
from app.handlers import client_router, common_router, manager_router, orders_router
from app.services.managers import seed_managers


async def on_startup() -> None:
    settings = get_settings()

    if settings.RUN_DB_CREATE_ALL:
        await create_db()

    async with async_session_maker() as session:
        await seed_managers(session, settings.manager_ids)
        await session.commit()


async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    settings = get_settings()

    bot = Bot(
        token=settings.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())

    dp.update.outer_middleware(DbSessionMiddleware(async_session_maker))

    dp.include_router(common_router)
    dp.include_router(orders_router)
    dp.include_router(client_router)
    dp.include_router(manager_router)

    await on_startup()

    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await bot.session.close()
        await dispose_db()


if __name__ == "__main__":
    asyncio.run(main())
