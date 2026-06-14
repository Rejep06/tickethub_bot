from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.manager import Manager


async def get_manager_by_telegram_id(session: AsyncSession, telegram_id: int) -> Manager | None:
    result = await session.execute(select(Manager).where(Manager.telegram_id == telegram_id))
    return result.scalar_one_or_none()


async def is_manager(session: AsyncSession, telegram_id: int) -> bool:
    return await get_manager_by_telegram_id(session, telegram_id) is not None


async def seed_managers(session: AsyncSession, telegram_ids: Iterable[int]) -> None:
    for telegram_id in set(telegram_ids):
        manager = await get_manager_by_telegram_id(session, telegram_id)
        if manager is None:
            session.add(Manager(telegram_id=telegram_id))
    await session.flush()
