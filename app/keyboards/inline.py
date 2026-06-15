from collections.abc import Iterable, Sequence

from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.models.event import Event
from app.models.order import OrderStatus


def _status_value(status: OrderStatus | str | None) -> str | None:
    if isinstance(status, OrderStatus):
        return status.value
    return status


def event_cities_keyboard(cities: Sequence[str]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for index, city in enumerate(cities):
        builder.button(text=city[:64], callback_data=f"buy_city:{index}")
    builder.adjust(1)
    return builder.as_markup()


def events_buy_keyboard(events: Iterable[Event]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for event in events:
        button_text = f"{event.title} — {event.event_date:%d.%m.%Y}"
        builder.button(text=button_text[:64], callback_data=f"buy_event:{event.id}")
    builder.adjust(1)
    return builder.as_markup()


def order_status_keyboard(order_id: int, current_status: OrderStatus | str | None = None) -> InlineKeyboardMarkup:
    current_value = _status_value(current_status)
    buttons = [
        (OrderStatus.ACCEPTED, "Принять"),
        (OrderStatus.IN_WORK, "В работе"),
        (OrderStatus.DONE, "Завершено"),
        (OrderStatus.CANCELLED, "Отменено"),
    ]

    builder = InlineKeyboardBuilder()
    for status, text in buttons:
        prefix = "✅ " if status.value == current_value else ""
        builder.button(
            text=f"{prefix}{text}",
            callback_data=f"order_status:{order_id}:{status.value}",
        )
    builder.adjust(2)
    return builder.as_markup()


def event_admin_events_keyboard(events: Iterable[Event], action: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for event in events:
        button_text = f"#{event.id} {event.city} — {event.title} — {event.event_date:%d.%m.%Y}"
        builder.button(text=button_text[:64], callback_data=f"event_{action}:{event.id}")
    builder.adjust(1)
    return builder.as_markup()


def event_fields_keyboard(event_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Название", callback_data=f"event_field:{event_id}:title")
    builder.button(text="Город", callback_data=f"event_field:{event_id}:city")
    builder.button(text="Дата", callback_data=f"event_field:{event_id}:event_date")
    builder.button(text="Время", callback_data=f"event_field:{event_id}:event_time")
    builder.button(text="Место", callback_data=f"event_field:{event_id}:location")
    builder.adjust(2)
    return builder.as_markup()


def delete_confirm_keyboard(event_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Да, удалить", callback_data=f"event_delete_confirm:{event_id}")
    builder.button(text="Отмена", callback_data="event_delete_cancel")
    builder.adjust(1)
    return builder.as_markup()
