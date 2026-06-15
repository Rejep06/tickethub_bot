from datetime import date, datetime, time, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.event import Event


def normalize_city(city: str) -> str:
    return " ".join(city.strip().split())


async def list_events(session: AsyncSession, *, include_deleted: bool = False) -> list[Event]:
    filters = [] if include_deleted else [Event.is_active.is_(True)]
    result = await session.execute(
        select(Event)
        .where(*filters)
        .order_by(Event.event_date.asc(), Event.event_time.asc(), Event.id.asc())
    )
    return list(result.scalars().all())


async def list_event_cities(session: AsyncSession) -> list[str]:
    result = await session.execute(
        select(Event.city)
        .where(
            Event.is_active.is_(True),
            Event.city.is_not(None),
            func.length(func.trim(Event.city)) > 0,
        )
        .distinct()
        .order_by(Event.city.asc())
    )
    return list(result.scalars().all())


async def list_events_by_city(session: AsyncSession, city: str) -> list[Event]:
    normalized_city = normalize_city(city)
    result = await session.execute(
        select(Event)
        .where(Event.is_active.is_(True), Event.city == normalized_city)
        .order_by(Event.event_date.asc(), Event.event_time.asc(), Event.id.asc())
    )
    return list(result.scalars().all())


async def get_event(session: AsyncSession, event_id: int) -> Event | None:
    return await session.get(Event, event_id)


async def create_event(
    session: AsyncSession,
    *,
    title: str,
    city: str,
    event_date: date,
    event_time: time,
    location: str,
) -> Event:
    event = Event(
        title=title,
        city=normalize_city(city),
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

    if field not in {"title", "city", "event_date", "event_time", "location"}:
        raise ValueError(f"Unsupported event field: {field}")

    if field == "city" and isinstance(value, str):
        value = normalize_city(value)

    setattr(event, field, value)
    await session.flush()
    return event


async def delete_event(session: AsyncSession, event_id: int) -> tuple[bool, str]:
    event = await get_event(session, event_id)
    if event is None:
        return False, "Мероприятие не найдено."

    if not event.is_active:
        return True, "Мероприятие уже удалено."

    event.is_active = False
    event.deleted_at = datetime.now(timezone.utc)
    await session.flush()
    return True, "Мероприятие удалено."
