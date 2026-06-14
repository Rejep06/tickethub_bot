from datetime import date, time

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.event import Event
from app.models.order import Order


async def list_events(session: AsyncSession) -> list[Event]:
    result = await session.execute(
        select(Event).order_by(Event.event_date.asc(), Event.event_time.asc(), Event.id.asc())
    )
    return list(result.scalars().all())


async def get_event(session: AsyncSession, event_id: int) -> Event | None:
    return await session.get(Event, event_id)


async def create_event(
    session: AsyncSession,
    *,
    title: str,
    event_date: date,
    event_time: time,
    location: str,
) -> Event:
    event = Event(
        title=title,
        event_date=event_date,
        event_time=event_time,
        location=location,
    )
    session.add(event)
    await session.flush()
    return event


async def update_event_field(
    session: AsyncSession,
    *,
    event_id: int,
    field: str,
    value: str | date | time,
) -> Event | None:
    event = await get_event(session, event_id)
    if event is None:
        return None

    if field not in {"title", "event_date", "event_time", "location"}:
        raise ValueError(f"Unsupported event field: {field}")

    setattr(event, field, value)
    await session.flush()
    return event


async def delete_event(session: AsyncSession, event_id: int) -> tuple[bool, str]:
    event = await get_event(session, event_id)
    if event is None:
        return False, "Мероприятие не найдено."

    orders_count = await session.scalar(
        select(func.count(Order.id)).where(Order.event_id == event_id)
    )
    if orders_count and orders_count > 0:
        return False, "Нельзя удалить мероприятие, у которого уже есть заказы."

    await session.delete(event)
    await session.flush()
    return True, "Мероприятие удалено."
