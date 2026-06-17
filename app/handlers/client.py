import logging

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import get_settings
from app.keyboards.inline import (
    ALL_FILTER_CALLBACK_VALUE,
    CONTACT_MANAGER_CALLBACK_DATA,
    CUSTOM_EVENT_CALLBACK_DATA,
    event_types_keyboard,
    events_buy_keyboard,
    order_status_keyboard,
    sport_types_keyboard,
)
from app.keyboards.reply import BUY_TICKET, CONTACT_MANAGER, CUSTOM_ORDER, MY_ORDERS, main_menu_keyboard
from app.models.event import Event
from app.services.events import (
    DEFAULT_EVENT_TYPE,
    EVENT_TYPE_LABELS,
    SPORT_TYPE_LABELS,
    event_type_label,
    get_event,
    list_events_by_filters,
    sport_type_label,
)
from app.services.orders import create_order, list_user_orders
from app.services.users import create_or_update_user, get_user_by_telegram_id
from app.states.contact import ManagerContactStates
from app.states.purchase import PurchaseStates
from app.utils.formatters import (
    format_contact_to_manager,
    format_order_for_manager,
    format_user_orders,
    safe,
)

router = Router()
settings = get_settings()
logger = logging.getLogger(__name__)

# Поле orders.customer_location осталось NOT NULL для обратной совместимости.
# Для свободных заявок город больше не спрашивается, поэтому сохраняем пустую строку.
CUSTOM_ORDER_LOCATION = ""


async def _get_registered_user(message: Message, session: AsyncSession):
    if message.from_user is None:
        return None

    user = await get_user_by_telegram_id(session, message.from_user.id)
    if user is None or not user.phone_number:
        await message.answer("Сначала отправьте номер телефона через /start.")
        return None

    return await create_or_update_user(
        session,
        telegram_id=message.from_user.id,
        username=message.from_user.username,
        first_name=message.from_user.first_name,
        last_name=message.from_user.last_name,
    )


async def _ask_event_type(message: Message, session: AsyncSession, state: FSMContext, *, prefix: str = "") -> None:
    await state.clear()
    event_types = list(EVENT_TYPE_LABELS.keys())
    await state.set_state(PurchaseStates.choosing_event_type)
    await state.update_data(event_types=event_types, event_type=None, sport_type=None)

    text = (
        f"{prefix}Выберите тип события.\n"
        "Можно выбрать «Все», если тип не важен."
    )
    await message.answer(text, reply_markup=event_types_keyboard(event_types))


async def _start_contact_manager_flow(message: Message, session: AsyncSession, state: FSMContext) -> None:
    user = await _get_registered_user(message, session)
    if user is None:
        return

    await state.clear()
    await state.set_state(ManagerContactStates.waiting_message)
    await message.answer("Напишите сообщение для менеджера. Следующее сообщение будет отправлено в группу менеджеров.")


async def _start_custom_order_flow(message: Message, session: AsyncSession, state: FSMContext) -> None:
    user = await _get_registered_user(message, session)
    if user is None:
        return

    await state.clear()
    await state.update_data(
        event_id=None,
        requested_event_title=None,
        event_type=None,
        sport_type=None,
    )
    await state.set_state(PurchaseStates.custom_event)
    await message.answer(
        "Напишите название или описание события, которого нет в списке.\n"
        "Можно указать город, дату, команды/артиста и любые важные детали.\n"
        "Например: «Финал Лиги чемпионов в Мадриде»."
    )


def _is_all_callback_value(value: str) -> bool:
    return value == ALL_FILTER_CALLBACK_VALUE


def _event_matches_filters(
    event: Event,
    *,
    event_type: str | None,
    sport_type: str | None,
) -> bool:
    if event_type is not None and event.event_type != event_type:
        return False
    if event_type == DEFAULT_EVENT_TYPE and sport_type is not None and event.sport_type != sport_type:
        return False
    return True


def _filter_lines(*, event_type: str | None, sport_type: str | None) -> list[str]:
    lines = [f"Тип события: <b>{safe(event_type_label(event_type))}</b>"]
    if event_type == DEFAULT_EVENT_TYPE:
        lines.append(f"Тип спорта: <b>{safe(sport_type_label(sport_type))}</b>")
    return lines


async def _show_events_for_filter(
    callback: CallbackQuery,
    session: AsyncSession,
    state: FSMContext,
    *,
    event_type: str | None,
    sport_type: str | None = None,
) -> None:
    normalized_sport_type = sport_type if event_type == DEFAULT_EVENT_TYPE else None
    events = await list_events_by_filters(
        session,
        event_type=event_type,
        sport_type=normalized_sport_type,
    )

    await state.update_data(
        event_type=event_type,
        sport_type=normalized_sport_type,
        event_id=None,
        requested_event_title=None,
    )
    await state.set_state(PurchaseStates.choosing_event)

    lines = _filter_lines(event_type=event_type, sport_type=normalized_sport_type)
    if events:
        lines.append("Выберите мероприятие из списка.")
    else:
        lines.append("По выбранным параметрам нет мероприятий в БД.")
    lines.append("Если нужного события нет в списке, можно оформить заявку вручную или связаться с менеджером.")

    text = "\n".join(lines)
    if isinstance(callback.message, Message):
        await callback.message.edit_text(text, reply_markup=events_buy_keyboard(events))
    else:
        await callback.answer(text, show_alert=True)
        return
    await callback.answer()


async def _ask_custom_event_text(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    event_type = data.get("event_type") if isinstance(data.get("event_type"), str) else None
    sport_type = data.get("sport_type") if isinstance(data.get("sport_type"), str) else None

    await state.set_state(PurchaseStates.custom_event)
    text = "\n".join(
        [
            *_filter_lines(event_type=event_type, sport_type=sport_type),
            "Напишите название или описание нужного события.",
            "Например: «Финал Лиги чемпионов в Мадриде» или «концерт Imagine Dragons».",
        ]
    )

    if isinstance(callback.message, Message):
        await callback.message.edit_text(text)
    else:
        await callback.answer(text, show_alert=True)
        return
    await callback.answer()


async def _save_custom_event_text(message: Message, state: FSMContext) -> None:
    if message.text is None:
        return

    requested_event_title = " ".join(message.text.strip().split())
    if len(requested_event_title) < 2:
        await message.answer("Напишите название или описание события.")
        return
    if len(requested_event_title) > 500:
        await message.answer("Описание события слишком длинное. Ограничение — 500 символов.")
        return

    await state.update_data(event_id=None, requested_event_title=requested_event_title)
    await state.set_state(PurchaseStates.quantity)
    await message.answer(
        f"Вы указали: <b>{safe(requested_event_title)}</b>\n\n"
        "Введите количество билетов числом."
    )


@router.message(F.text == BUY_TICKET)
async def buy_ticket_start(message: Message, session: AsyncSession, state: FSMContext) -> None:
    user = await _get_registered_user(message, session)
    if user is None:
        return

    await _ask_event_type(message, session, state)


@router.message(F.text == CONTACT_MANAGER)
async def contact_manager_start(message: Message, session: AsyncSession, state: FSMContext) -> None:
    await _start_contact_manager_flow(message, session, state)


@router.message(F.text == CUSTOM_ORDER)
async def custom_order_start(message: Message, session: AsyncSession, state: FSMContext) -> None:
    await _start_custom_order_flow(message, session, state)


@router.message(F.text == MY_ORDERS)
async def my_orders(message: Message, session: AsyncSession) -> None:
    user = await _get_registered_user(message, session)
    if user is None:
        return

    orders = await list_user_orders(session, user.id)
    await message.answer(format_user_orders(orders), reply_markup=main_menu_keyboard())


@router.callback_query(F.data.startswith("buy_event_type:"))
async def buy_ticket_choose_event_type(callback: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    if callback.from_user is None or callback.data is None:
        return

    user = await get_user_by_telegram_id(session, callback.from_user.id)
    if user is None or not user.phone_number:
        await callback.answer("Сначала отправьте номер телефона через /start.", show_alert=True)
        return

    raw_event_type = callback.data.split(":", maxsplit=1)[1]
    data = await state.get_data()
    event_types = data.get("event_types")

    if _is_all_callback_value(raw_event_type):
        event_type = None
    else:
        event_type = raw_event_type
        if isinstance(event_types, list) and event_type not in event_types:
            await callback.answer("Этот тип события больше недоступен. Начните заново через меню.", show_alert=True)
            return

    if event_type == DEFAULT_EVENT_TYPE:
        sport_types = list(SPORT_TYPE_LABELS.keys())
        await state.update_data(event_type=event_type, sport_types=sport_types, sport_type=None)
        await state.set_state(PurchaseStates.choosing_sport_type)

        text = (
            f"Тип события: <b>{safe(event_type_label(event_type))}</b>\n"
            "Выберите тип спорта.\n"
            "Можно выбрать «Все», если тип спорта не важен."
        )
        if isinstance(callback.message, Message):
            await callback.message.edit_text(text, reply_markup=sport_types_keyboard(sport_types))
        else:
            await callback.answer(text, show_alert=True)
            return
        await callback.answer()
        return

    await _show_events_for_filter(callback, session, state, event_type=event_type)


@router.callback_query(F.data.startswith("buy_sport_type:"))
async def buy_ticket_choose_sport_type(callback: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    if callback.from_user is None or callback.data is None:
        return

    data = await state.get_data()
    event_type = data.get("event_type")
    sport_types = data.get("sport_types")
    if event_type != DEFAULT_EVENT_TYPE:
        await callback.answer("Сначала выберите спортивный тип события.", show_alert=True)
        return

    raw_sport_type = callback.data.split(":", maxsplit=1)[1]
    if _is_all_callback_value(raw_sport_type):
        sport_type = None
    else:
        sport_type = raw_sport_type
        if isinstance(sport_types, list) and sport_type not in sport_types:
            await callback.answer("Этот тип спорта больше недоступен. Начните заново через меню.", show_alert=True)
            return

    await _show_events_for_filter(
        callback,
        session,
        state,
        event_type=DEFAULT_EVENT_TYPE,
        sport_type=sport_type,
    )


@router.callback_query(F.data == CUSTOM_EVENT_CALLBACK_DATA)
async def buy_ticket_custom_event_callback(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.from_user is None:
        return
    await _ask_custom_event_text(callback, state)


@router.callback_query(F.data == CONTACT_MANAGER_CALLBACK_DATA)
async def buy_ticket_contact_manager_callback(
    callback: CallbackQuery,
    session: AsyncSession,
    state: FSMContext,
) -> None:
    if callback.from_user is None:
        return

    user = await get_user_by_telegram_id(session, callback.from_user.id)
    if user is None or not user.phone_number:
        await callback.answer("Сначала отправьте номер телефона через /start.", show_alert=True)
        return

    await state.clear()
    await state.set_state(ManagerContactStates.waiting_message)
    text = "Напишите сообщение для менеджера. Следующее сообщение будет отправлено в группу менеджеров."
    if isinstance(callback.message, Message):
        await callback.message.edit_text(text)
    else:
        await callback.answer(text, show_alert=True)
        return
    await callback.answer()


@router.callback_query(F.data.startswith("buy_event:"))
async def buy_ticket_choose_event(callback: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    if callback.from_user is None or callback.data is None:
        return

    data = await state.get_data()
    selected_event_type = data.get("event_type") if isinstance(data.get("event_type"), str) else None
    selected_sport_type = data.get("sport_type") if isinstance(data.get("sport_type"), str) else None

    try:
        event_id = int(callback.data.split(":", maxsplit=1)[1])
    except (ValueError, IndexError):
        await callback.answer("Некорректное мероприятие.", show_alert=True)
        return

    event = await get_event(session, event_id)
    if event is None or not event.is_active:
        await callback.answer("Мероприятие не найдено.", show_alert=True)
        return

    if not _event_matches_filters(
        event,
        event_type=selected_event_type,
        sport_type=selected_sport_type,
    ):
        await callback.answer("Мероприятие больше не относится к выбранным фильтрам.", show_alert=True)
        return

    user = await get_user_by_telegram_id(session, callback.from_user.id)
    if user is None or not user.phone_number:
        await callback.answer("Сначала отправьте номер телефона через /start.", show_alert=True)
        return

    await state.update_data(event_id=event.id, requested_event_title=None)
    await state.set_state(PurchaseStates.quantity)

    type_lines = [f"Тип события: {safe(event_type_label(event.event_type))}"]
    if event.event_type == DEFAULT_EVENT_TYPE:
        type_lines.append(f"Тип спорта: {safe(sport_type_label(event.sport_type))}")
    type_text = "\n".join(type_lines)

    text = (
        f"Вы выбрали: <b>{safe(event.title)}</b>\n"
        f"Город: {safe(event.city)}\n"
        f"{type_text}\n"
        f"Дата: {event.event_date:%d.%m.%Y}\n"
        f"Время: {event.event_time:%H:%M}\n"
        f"Место: {safe(event.location)}\n\n"
        "Введите количество билетов числом."
    )

    if isinstance(callback.message, Message):
        await callback.message.edit_text(text)
    else:
        await callback.answer(text, show_alert=True)
    await callback.answer()


@router.message(ManagerContactStates.waiting_message)
async def contact_manager_message(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
    bot: Bot,
) -> None:
    if message.from_user is None:
        return

    user = await get_user_by_telegram_id(session, message.from_user.id)
    if user is None or not user.phone_number:
        await state.clear()
        await message.answer("Сначала отправьте номер телефона через /start.")
        return

    try:
        await bot.send_message(settings.MANAGERS_CHAT_ID, format_contact_to_manager(user))
        await bot.copy_message(
            chat_id=settings.MANAGERS_CHAT_ID,
            from_chat_id=message.chat.id,
            message_id=message.message_id,
        )
    except TelegramAPIError:
        logger.exception("Could not forward customer message to managers chat")
        await message.answer(
            "Не удалось отправить сообщение менеджерам. Проверьте настройки группы.",
            reply_markup=main_menu_keyboard(),
        )
        await state.clear()
        return

    await state.clear()
    await message.answer("Сообщение отправлено менеджерам.", reply_markup=main_menu_keyboard())


@router.message(PurchaseStates.choosing_event)
async def buy_ticket_custom_event_from_text(message: Message, state: FSMContext) -> None:
    await _save_custom_event_text(message, state)


@router.message(PurchaseStates.custom_event)
async def buy_ticket_custom_event_text(message: Message, state: FSMContext) -> None:
    await _save_custom_event_text(message, state)


@router.message(PurchaseStates.quantity)
async def buy_ticket_quantity(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
    bot: Bot,
) -> None:
    if message.from_user is None or message.text is None:
        return

    try:
        quantity = int(message.text.strip())
    except ValueError:
        await message.answer("Количество должно быть числом. Например: 2")
        return

    if quantity <= 0:
        await message.answer("Количество должно быть больше нуля.")
        return

    data = await state.get_data()
    event_id_raw = data.get("event_id")
    requested_event_title = data.get("requested_event_title")
    selected_event_type = data.get("event_type") if isinstance(data.get("event_type"), str) else None
    selected_sport_type = data.get("sport_type") if isinstance(data.get("sport_type"), str) else None

    user = await get_user_by_telegram_id(session, message.from_user.id)
    if user is None or not user.phone_number:
        await state.clear()
        await message.answer("Сначала отправьте номер телефона через /start.")
        return

    event: Event | None = None
    event_id: int | None = int(event_id_raw) if event_id_raw is not None else None

    if event_id is not None:
        event = await get_event(session, event_id)
        if event is None or not event.is_active:
            await state.clear()
            await message.answer("Мероприятие больше недоступно.", reply_markup=main_menu_keyboard())
            return

        if not _event_matches_filters(
            event,
            event_type=selected_event_type,
            sport_type=selected_sport_type,
        ):
            await state.clear()
            await message.answer(
                "Мероприятие больше не относится к выбранным фильтрам. Начните заказ заново.",
                reply_markup=main_menu_keyboard(),
            )
            return
    else:
        if not isinstance(requested_event_title, str) or len(requested_event_title.strip()) < 2:
            await state.clear()
            await message.answer("Не указано мероприятие. Начните заказ заново.", reply_markup=main_menu_keyboard())
            return
        requested_event_title = requested_event_title.strip()

    order = await create_order(
        session,
        user_id=user.id,
        event_id=event.id if event is not None else None,
        quantity=quantity,
        # Поле оставлено для обратной совместимости со старой схемой orders.
        customer_location=event.city if event is not None else CUSTOM_ORDER_LOCATION,
        requested_event_title=None if event is not None else requested_event_title,
        requested_city=None,
        requested_event_type=selected_event_type,
        requested_sport_type=selected_sport_type if selected_event_type == DEFAULT_EVENT_TYPE else None,
    )

    try:
        await bot.send_message(
            chat_id=settings.MANAGERS_CHAT_ID,
            text=format_order_for_manager(order, user=user, event=event),
            reply_markup=order_status_keyboard(order.id, order.status),
        )
    except TelegramAPIError:
        logger.exception("Could not send order %s to managers chat", order.id)
        await message.answer(
            f"Заказ #{order.id} создан, но уведомление менеджерам не отправилось. "
            "Проверьте MANAGERS_CHAT_ID и права бота в группе.",
            reply_markup=main_menu_keyboard(),
        )
        await state.clear()
        return

    await state.clear()
    await message.answer(
        f"Заказ #{order.id} создан. Менеджер скоро обработает его.",
        reply_markup=main_menu_keyboard(),
    )
