from collections.abc import Iterable
from datetime import datetime
from html import escape

from app.models.event import Event
from app.models.order import Order, OrderStatus
from app.models.user import User


def safe(value: object | None) -> str:
    if value is None or value == "":
        return "—"
    return escape(str(value))


def status_label(status: OrderStatus | str | None) -> str:
    value = status.value if isinstance(status, OrderStatus) else status
    labels = {
        OrderStatus.NEW.value: "Новый",
        OrderStatus.ACCEPTED.value: "Принят",
        OrderStatus.IN_WORK.value: "В работе",
        OrderStatus.DONE.value: "Завершен",
        OrderStatus.CANCELLED.value: "Отменен",
    }
    return labels.get(value or "", safe(value))


def format_date_time(value: datetime | None) -> str:
    if value is None:
        return "—"
    return value.strftime("%d.%m.%Y %H:%M")


def format_username(username: str | None) -> str:
    if not username:
        return "—"
    return f"@{escape(username)}"


def format_full_name(user: User) -> str:
    parts = [part for part in (user.first_name, user.last_name) if part]
    if not parts:
        return "—"
    return safe(" ".join(parts))


def format_event_card(event: Event) -> str:
    return (
        f"<b>Мероприятие #{event.id}</b>\n"
        f"Название: {safe(event.title)}\n"
        f"Город: {safe(event.city)}\n"
        f"Дата: {event.event_date:%d.%m.%Y}\n"
        f"Время: {event.event_time:%H:%M}\n"
        f"Место: {safe(event.location)}"
    )


def format_events_list(events: Iterable[Event]) -> str:
    event_list = list(events)
    if not event_list:
        return "Мероприятий пока нет."

    lines = ["<b>Список мероприятий</b>"]
    for event in event_list:
        lines.append("")
        lines.append(format_event_card(event))
    return "\n".join(lines)


def format_order_for_manager(order: Order, user: User | None = None, event: Event | None = None) -> str:
    user = user or order.user
    event = event or order.event

    return (
        f"<b>Заказ #{order.id}</b>\n\n"
        f"<b>Мероприятие</b>: {safe(event.title)}\n"
        f"<b>Город мероприятия</b>: {safe(event.city)}\n"
        f"<b>Дата мероприятия</b>: {event.event_date:%d.%m.%Y}\n"
        f"<b>Время мероприятия</b>: {event.event_time:%H:%M}\n"
        f"<b>Место мероприятия</b>: {safe(event.location)}\n"
        f"<b>Количество билетов</b>: {order.quantity}\n"
        f"<b>Город/место клиента</b>: {safe(order.customer_location)}\n\n"
        f"<b>Имя</b>: {format_full_name(user)}\n"
        f"<b>Username</b>: {format_username(user.username)}\n"
        f"<b>Телефон</b>: {safe(user.phone_number)}\n"
        f"<b>Telegram ID</b>: <code>{user.telegram_id}</code>\n"
        f"<b>Статус</b>: {status_label(order.status)}"
    )


def format_contact_to_manager(user: User) -> str:
    return (
        "<b>Сообщение клиента менеджерам</b>\n\n"
        f"<b>Имя</b>: {format_full_name(user)}\n"
        f"<b>Username</b>: {format_username(user.username)}\n"
        f"<b>Телефон</b>: {safe(user.phone_number)}\n"
        f"<b>Telegram ID</b>: <code>{user.telegram_id}</code>"
    )


def format_user_orders(orders: Iterable[Order]) -> str:
    order_list = list(orders)
    if not order_list:
        return "У вас пока нет заказов."

    lines = ["<b>Мои заказы</b>"]
    for order in order_list:
        event = order.event
        lines.extend(
            [
                "",
                f"<b>Заказ #{order.id}</b>",
                f"Мероприятие: {safe(event.title)}",
                f"Город мероприятия: {safe(event.city)}",
                f"Количество: {order.quantity}",
                f"Статус: {status_label(order.status)}",
                f"Дата заказа: {format_date_time(order.created_at)}",
            ]
        )
    return "\n".join(lines)
