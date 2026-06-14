from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


async def get_user_by_telegram_id(session: AsyncSession, telegram_id: int) -> User | None:
    result = await session.execute(select(User).where(User.telegram_id == telegram_id))
    return result.scalar_one_or_none()


async def create_or_update_user(
    session: AsyncSession,
    *,
    telegram_id: int,
    username: str | None,
    phone_number: str,
) -> User:
    user = await get_user_by_telegram_id(session, telegram_id)

    if user is None:
        user = User(
            telegram_id=telegram_id,
            username=username,
            phone_number=phone_number,
        )
        session.add(user)
    else:
        user.username = username
        user.phone_number = phone_number

    await session.flush()
    return user
