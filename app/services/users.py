from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
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
    phone_number: str | None = None,
    first_name: str | None = None,
    last_name: str | None = None,
) -> User:
    insert_stmt = insert(User).values(
        telegram_id=telegram_id,
        username=username,
        phone_number=phone_number,
        first_name=first_name,
        last_name=last_name,
    )
    upsert_stmt = (
        insert_stmt.on_conflict_do_update(
            index_elements=[User.telegram_id],
            set_={
                "username": insert_stmt.excluded.username,
                "phone_number": func.coalesce(insert_stmt.excluded.phone_number, User.phone_number),
                "first_name": insert_stmt.excluded.first_name,
                "last_name": insert_stmt.excluded.last_name,
                "updated_at": func.now(),
            },
        )
        .returning(User)
    )

    result = await session.execute(
        select(User).from_statement(upsert_stmt).execution_options(populate_existing=True)
    )
    return result.scalar_one()
