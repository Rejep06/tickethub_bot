from collections.abc import Iterable, Sequence

from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.models.event import Event
from app.models.order import OrderStatus
from app.services.events import (
    ALL_FILTER_LABEL,
    EVENT_TYPE_LABELS,
    SPORT_TYPE_LABELS,
    event_type_label,
    sport_type_label,
)

ALL_FILTER_CALLBACK_VALUE = "__all__"
CUSTOM_EVENT_CALLBACK_DATA = "buy_event_custom"
CONTACT_MANAGER_CALLBACK_DATA = "buy_contact_manager"


def _status_value(status: OrderStatus | str | None) -> str | None:
    if isinstance(status, OrderStatus):
        return status.value
    return status


def event_types_keyboard(event_types: Sequence[str], *, include_all: bool = True) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if include_all:
        builder.button(text=ALL_FILTER_LABEL, callback_data=f"buy_event_type:{ALL_FILTER_CALLBACK_VALUE}")
    for event_type in event_types:
        builder.button(text=event_type_label(event_type), callback_data=f"buy_event_type:{event_type}")
    builder.adjust(1)
    return builder.as_markup()


def sport_types_keyboard(sport_types: Sequence[str], *, include_all: bool = True) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if include_all:
        builder.button(text=ALL_FILTER_LABEL, callback_data=f"buy_sport_type:{ALL_FILTER_CALLBACK_VALUE}")
    for sport_type in sport_types:
        builder.button(text=sport_type_label(sport_type), callback_data=f"buy_sport_type:{sport_type}")
    builder.adjust(1)
    return builder.as_markup()


def admin_event_types_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for event_type, label in EVENT_TYPE_LABELS.items():
        builder.button(text=label, callback_data=f"event_create_type:{event_type}")
    builder.adjust(2)
    return builder.as_markup()


def admin_sport_types_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for sport_type, label in SPORT_TYPE_LABELS.items():
        builder.button(text=label, callback_data=f"event_create_sport:{sport_type}")
    builder.adjust(2)
    return builder.as_markup()


def events_buy_keyboard(
    events: Iterable[Event],
    *,
    include_custom: bool = True,
    include_contact_manager: bool = True,
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for event in events:
        button_text = f"{event.title} — {event.city} — {event.event_date:%d.%m.%Y}"
        builder.button(text=button_text[:64], callback_data=f"buy_event:{event.id}")
    if include_custom:
        builder.button(text="Заказать событие не из списка", callback_data=CUSTOM_EVENT_CALLBACK_DATA)
    if include_contact_manager:
        builder.button(text="Связаться с менеджером", callback_data=CONTACT_MANAGER_CALLBACK_DATA)
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


def manager_inline_menu_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Создать мероприятие", callback_data="manager_action:create")
    builder.button(text="Список мероприятий", callback_data="manager_action:list")
    builder.button(text="Редактировать мероприятие", callback_data="manager_action:edit")
    builder.button(text="Удалить мероприятие", callback_data="manager_action:delete")
    builder.adjust(1)
    return builder.as_markup()


def event_admin_events_keyboard(events: Iterable[Event], action: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for event in events:
        type_text = event_type_label(event.event_type)
        if event.event_type == "sport" and event.sport_type:
            type_text = f"{type_text}/{sport_type_label(event.sport_type)}"
        button_text = f"#{event.id} {event.city} — {type_text} — {event.title} — {event.event_date:%d.%m.%Y}"
        builder.button(text=button_text[:64], callback_data=f"event_{action}:{event.id}")
    builder.adjust(1)
    return builder.as_markup()


def event_fields_keyboard(event_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Название", callback_data=f"event_field:{event_id}:title")
    builder.button(text="Город", callback_data=f"event_field:{event_id}:city")
    builder.button(text="Тип события", callback_data=f"event_field:{event_id}:event_type")
    builder.button(text="Тип спорта", callback_data=f"event_field:{event_id}:sport_type")
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
