from datetime import date, datetime, time, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.event import Event

DEFAULT_EVENT_TYPE = "sport"
DEFAULT_SPORT_TYPE = "football"
ALL_FILTER_LABEL = "Все"

EVENT_TYPE_LABELS: dict[str, str] = {
    "sport": "Спорт",
    "concert": "Концерт",
    "theater": "Театр",
    "festival": "Фестиваль",
    "show": "Шоу",
    "exhibition": "Выставка",
    "other": "Другое",
}

SPORT_TYPE_LABELS: dict[str, str] = {
    "football": "Футбол",
    "basketball": "Баскетбол",
    "volleyball": "Волейбол",
    "hockey": "Хоккей",
    "tennis": "Теннис",
    "boxing": "Бокс",
    "mma": "MMA",
    "running": "Бег",
    "other": "Другое",
}

_EVENT_TYPE_ALIASES: dict[str, str] = {
    "sport": "sport",
    "sports": "sport",
    "спорт": "sport",
    "спортивное": "sport",
    "спортивный": "sport",
    "концерт": "concert",
    "concert": "concert",
    "театр": "theater",
    "театральное": "theater",
    "theater": "theater",
    "theatre": "theater",
    "фестиваль": "festival",
    "festival": "festival",
    "шоу": "show",
    "show": "show",
    "выставка": "exhibition",
    "exhibition": "exhibition",
    "другое": "other",
    "прочее": "other",
    "other": "other",
    "-": DEFAULT_EVENT_TYPE,
}

_SPORT_TYPE_ALIASES: dict[str, str] = {
    "football": "football",
    "футбол": "football",
    "soccer": "football",
    "баскетбол": "basketball",
    "basketball": "basketball",
    "волейбол": "volleyball",
    "volleyball": "volleyball",
    "хоккей": "hockey",
    "hockey": "hockey",
    "теннис": "tennis",
    "tennis": "tennis",
    "бокс": "boxing",
    "boxing": "boxing",
    "mma": "mma",
    "мма": "mma",
    "бег": "running",
    "running": "running",
    "другое": "other",
    "прочее": "other",
    "other": "other",
    "-": DEFAULT_SPORT_TYPE,
}


def normalize_city(city: str) -> str:
    return " ".join(city.strip().split())


def _normalize_key(value: str | None) -> str:
    if value is None:
        return ""
    return " ".join(value.strip().lower().replace("ё", "е").split())


def normalize_event_type(event_type: str | None) -> str:
    key = _normalize_key(event_type)
    if not key:
        return DEFAULT_EVENT_TYPE
    return _EVENT_TYPE_ALIASES.get(key, "other")


def normalize_sport_type(sport_type: str | None) -> str:
    key = _normalize_key(sport_type)
    if not key:
        return DEFAULT_SPORT_TYPE
    return _SPORT_TYPE_ALIASES.get(key, "other")


def event_type_label(event_type: str | None) -> str:
    if event_type is None:
        return ALL_FILTER_LABEL
    normalized = normalize_event_type(event_type)
    return EVENT_TYPE_LABELS.get(normalized, normalized)


def sport_type_label(sport_type: str | None) -> str:
    if sport_type is None:
        return ALL_FILTER_LABEL
    normalized = normalize_sport_type(sport_type)
    return SPORT_TYPE_LABELS.get(normalized, normalized)


def city_label(city: str | None) -> str:
    return ALL_FILTER_LABEL if city is None else city


def is_sport_event_type(event_type: str | None) -> bool:
    return normalize_event_type(event_type) == DEFAULT_EVENT_TYPE


def _active_event_filters() -> list:
    return [Event.is_active.is_(True)]


def _event_filter_conditions(
    *,
    city: str | None = None,
    event_type: str | None = None,
    sport_type: str | None = None,
) -> list:
    filters = _active_event_filters()

    if city:
        filters.append(Event.city == normalize_city(city))

    if event_type:
        normalized_event_type = normalize_event_type(event_type)
        filters.append(Event.event_type == normalized_event_type)
    elif sport_type:
        # Тип спорта имеет смысл только для спортивных мероприятий.
        filters.append(Event.event_type == DEFAULT_EVENT_TYPE)

    if sport_type:
        filters.append(Event.sport_type == normalize_sport_type(sport_type))

    return filters


def _not_empty(column) -> list:
    return [column.is_not(None), func.length(func.trim(column)) > 0]


async def list_events(session: AsyncSession, *, include_deleted: bool = False) -> list[Event]:
    filters = [] if include_deleted else _active_event_filters()
    result = await session.execute(
        select(Event)
        .where(*filters)
        .order_by(Event.event_date.asc(), Event.event_time.asc(), Event.id.asc())
    )
    return list(result.scalars().all())


async def list_event_types(session: AsyncSession, *, city: str | None = None) -> list[str]:
    result = await session.execute(
        select(Event.event_type)
        .where(
            *_event_filter_conditions(city=city),
            *_not_empty(Event.event_type),
        )
        .distinct()
        .order_by(Event.event_type.asc())
    )
    event_types = [normalize_event_type(value) for value in result.scalars().all()]
    return sorted(set(event_types), key=lambda value: EVENT_TYPE_LABELS.get(value, value))


async def list_event_cities(session: AsyncSession) -> list[str]:
    return await list_event_cities_by_filters(session)


async def list_event_cities_by_filters(
    session: AsyncSession,
    *,
    event_type: str | None = None,
    sport_type: str | None = None,
) -> list[str]:
    result = await session.execute(
        select(Event.city)
        .where(
            *_event_filter_conditions(event_type=event_type, sport_type=sport_type),
            *_not_empty(Event.city),
        )
        .distinct()
        .order_by(Event.city.asc())
    )
    return list(result.scalars().all())


async def list_event_types_by_city(session: AsyncSession, city: str) -> list[str]:
    return await list_event_types(session, city=city)


async def list_sport_types(
    session: AsyncSession,
    *,
    city: str | None = None,
) -> list[str]:
    result = await session.execute(
        select(Event.sport_type)
        .where(
            *_event_filter_conditions(city=city, event_type=DEFAULT_EVENT_TYPE),
            *_not_empty(Event.sport_type),
        )
        .distinct()
        .order_by(Event.sport_type.asc())
    )
    sport_types = [normalize_sport_type(value) for value in result.scalars().all()]
    return sorted(set(sport_types), key=lambda value: SPORT_TYPE_LABELS.get(value, value))


async def list_sport_types_by_city(session: AsyncSession, city: str) -> list[str]:
    return await list_sport_types(session, city=city)


async def list_events_by_city(session: AsyncSession, city: str) -> list[Event]:
    result = await session.execute(
        select(Event)
        .where(*_event_filter_conditions(city=city))
        .order_by(Event.event_date.asc(), Event.event_time.asc(), Event.id.asc())
    )
    return list(result.scalars().all())


async def list_events_by_filters(
    session: AsyncSession,
    *,
    city: str | None = None,
    event_type: str | None = None,
    sport_type: str | None = None,
) -> list[Event]:
    result = await session.execute(
        select(Event)
        .where(*_event_filter_conditions(city=city, event_type=event_type, sport_type=sport_type))
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
    event_type: str | None = DEFAULT_EVENT_TYPE,
    sport_type: str | None = DEFAULT_SPORT_TYPE,
) -> Event:
    normalized_event_type = normalize_event_type(event_type)
    normalized_sport_type = normalize_sport_type(sport_type) if normalized_event_type == DEFAULT_EVENT_TYPE else None

    event = Event(
        title=title,
        city=normalize_city(city),
        event_type=normalized_event_type,
        sport_type=normalized_sport_type,
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

    if field not in {"title", "city", "event_type", "sport_type", "event_date", "event_time", "location"}:
        raise ValueError(f"Unsupported event field: {field}")

    if field == "city" and isinstance(value, str):
        value = normalize_city(value)
    elif field == "event_type" and isinstance(value, str):
        value = normalize_event_type(value)
        event.sport_type = normalize_sport_type(event.sport_type) if value == DEFAULT_EVENT_TYPE else None
    elif field == "sport_type" and isinstance(value, str):
        value = normalize_sport_type(value)
        if event.event_type != DEFAULT_EVENT_TYPE:
            event.event_type = DEFAULT_EVENT_TYPE

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
