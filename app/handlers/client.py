import logging

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import get_settings
from app.keyboards.inline import (
    event_cities_keyboard,
    event_types_keyboard,
    events_buy_keyboard,
    order_status_keyboard,
    sport_types_keyboard,
)
from app.keyboards.reply import BUY_TICKET, CONTACT_MANAGER, MY_ORDERS, main_menu_keyboard
from app.services.events import (
    DEFAULT_EVENT_TYPE,
    event_type_label,
    get_event,
    list_event_cities,
    list_event_types_by_city,
    list_events_by_filters,
    list_sport_types_by_city,
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


async def _ask_city(message: Message, session: AsyncSession, state: FSMContext) -> None:
    await state.clear()
    cities = await list_event_cities(session)
    if not cities:
        await message.answer("Сейчас нет доступных мероприятий.", reply_markup=main_menu_keyboard())
        return

    await state.set_state(PurchaseStates.choosing_city)
    await state.update_data(cities=cities)
    await message.answer("Выберите город проведения:", reply_markup=event_cities_keyboard(cities))


async def _show_events_for_filter(
    callback: CallbackQuery,
    session: AsyncSession,
    state: FSMContext,
    *,
    city: str,
    event_type: str,
    sport_type: str | None = None,
) -> None:
    events = await list_events_by_filters(
        session,
        city=city,
        event_type=event_type,
        sport_type=sport_type,
    )
    if not events:
        await callback.answer("По выбранным параметрам сейчас нет доступных мероприятий.", show_alert=True)
        return

    await state.update_data(event_type=event_type, sport_type=sport_type)
    await state.set_state(PurchaseStates.choosing_event)

    filter_lines = [
        f"Город: <b>{safe(city)}</b>",
        f"Тип события: <b>{safe(event_type_label(event_type))}</b>",
    ]
    if event_type == DEFAULT_EVENT_TYPE:
        filter_lines.append(f"Тип спорта: <b>{safe(sport_type_label(sport_type))}</b>")
    filter_lines.append("Выберите мероприятие:")

    text = "\n".join(filter_lines)
    if isinstance(callback.message, Message):
        await callback.message.edit_text(text, reply_markup=events_buy_keyboard(events))
    else:
        await callback.answer(text, show_alert=True)
        return
    await callback.answer()


@router.message(F.text == BUY_TICKET)
async def buy_ticket_start(message: Message, session: AsyncSession, state: FSMContext) -> None:
    user = await _get_registered_user(message, session)
    if user is None:
        return

    await _ask_city(message, session, state)


@router.callback_query(F.data.startswith("buy_city:"))
async def buy_ticket_choose_city(callback: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    if callback.from_user is None or callback.data is None:
        return

    user = await get_user_by_telegram_id(session, callback.from_user.id)
    if user is None or not user.phone_number:
        await callback.answer("Сначала отправьте номер телефона через /start.", show_alert=True)
        return

    try:
        city_index = int(callback.data.split(":", maxsplit=1)[1])
    except (ValueError, IndexError):
        await callback.answer("Некорректный город.", show_alert=True)
        return

    data = await state.get_data()
    cities = data.get("cities")
    if not isinstance(cities, list) or city_index < 0 or city_index >= len(cities):
        await callback.answer("Выбор города устарел. Начните заново через меню.", show_alert=True)
        return

    city = str(cities[city_index])
    event_types = await list_event_types_by_city(session, city)
    if not event_types:
        await callback.answer("В этом городе сейчас нет доступных мероприятий.", show_alert=True)
        return

    await state.update_data(city=city, event_types=event_types)
    await state.set_state(PurchaseStates.choosing_event_type)

    text = f"Город: <b>{safe(city)}</b>\nВыберите тип события:"
    if isinstance(callback.message, Message):
        await callback.message.edit_text(text, reply_markup=event_types_keyboard(event_types))
    else:
        await callback.answer(text, show_alert=True)
        return
    await callback.answer()


@router.callback_query(F.data.startswith("buy_event_type:"))
async def buy_ticket_choose_event_type(callback: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    if callback.from_user is None or callback.data is None:
        return

    data = await state.get_data()
    city = data.get("city")
    event_types = data.get("event_types")
    if not isinstance(city, str) or not city:
        await callback.answer("Сначала выберите город.", show_alert=True)
        return

    event_type = callback.data.split(":", maxsplit=1)[1]
    if isinstance(event_types, list) and event_type not in event_types:
        await callback.answer("Этот тип события больше недоступен. Начните заново через меню.", show_alert=True)
        return

    if event_type == DEFAULT_EVENT_TYPE:
        sport_types = await list_sport_types_by_city(session, city)
        if not sport_types:
            await callback.answer("В этом городе сейчас нет доступных спортивных мероприятий.", show_alert=True)
            return

        await state.update_data(event_type=event_type, sport_types=sport_types)
        await state.set_state(PurchaseStates.choosing_sport_type)

        text = (
            f"Город: <b>{safe(city)}</b>\n"
            f"Тип события: <b>{safe(event_type_label(event_type))}</b>\n"
            "Выберите тип спорта:"
        )
        if isinstance(callback.message, Message):
            await callback.message.edit_text(text, reply_markup=sport_types_keyboard(sport_types))
        else:
            await callback.answer(text, show_alert=True)
            return
        await callback.answer()
        return

    await _show_events_for_filter(callback, session, state, city=city, event_type=event_type)


@router.callback_query(F.data.startswith("buy_sport_type:"))
async def buy_ticket_choose_sport_type(callback: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    if callback.from_user is None or callback.data is None:
        return

    data = await state.get_data()
    city = data.get("city")
    event_type = data.get("event_type")
    sport_types = data.get("sport_types")
    if not isinstance(city, str) or not city:
        await callback.answer("Сначала выберите город.", show_alert=True)
        return
    if event_type != DEFAULT_EVENT_TYPE:
        await callback.answer("Сначала выберите спортивный тип события.", show_alert=True)
        return

    sport_type = callback.data.split(":", maxsplit=1)[1]
    if isinstance(sport_types, list) and sport_type not in sport_types:
        await callback.answer("Этот тип спорта больше недоступен. Начните заново через меню.", show_alert=True)
        return

    await _show_events_for_filter(
        callback,
        session,
        state,
        city=city,
        event_type=DEFAULT_EVENT_TYPE,
        sport_type=sport_type,
    )


@router.callback_query(F.data.startswith("buy_event:"))
async def buy_ticket_choose_event(callback: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    if callback.from_user is None or callback.data is None:
        return

    data = await state.get_data()
    selected_city = data.get("city")
    selected_event_type = data.get("event_type")
    selected_sport_type = data.get("sport_type")
    if not isinstance(selected_city, str) or not selected_city:
        await callback.answer("Сначала выберите город.", show_alert=True)
        return
    if not isinstance(selected_event_type, str) or not selected_event_type:
        await callback.answer("Сначала выберите тип события.", show_alert=True)
        return

    event_id = int(callback.data.split(":", maxsplit=1)[1])
    event = await get_event(session, event_id)
    if event is None or not event.is_active:
        await callback.answer("Мероприятие не найдено.", show_alert=True)
        return

    if event.city != selected_city:
        await callback.answer("Мероприятие не относится к выбранному городу.", show_alert=True)
        return
    if event.event_type != selected_event_type:
        await callback.answer("Мероприятие не относится к выбранному типу события.", show_alert=True)
        return
    if selected_event_type == DEFAULT_EVENT_TYPE and event.sport_type != selected_sport_type:
        await callback.answer("Мероприятие не относится к выбранному типу спорта.", show_alert=True)
        return

    user = await get_user_by_telegram_id(session, callback.from_user.id)
    if user is None or not user.phone_number:
        await callback.answer("Сначала отправьте номер телефона через /start.", show_alert=True)
        return

    await state.update_data(event_id=event.id)
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
    event_id = int(data["event_id"])
    selected_city = data.get("city")
    selected_event_type = data.get("event_type")
    selected_sport_type = data.get("sport_type")

    user = await get_user_by_telegram_id(session, message.from_user.id)
    if user is None or not user.phone_number:
        await state.clear()
        await message.answer("Сначала отправьте номер телефона через /start.")
        return

    event = await get_event(session, event_id)
    if event is None or not event.is_active:
        await state.clear()
        await message.answer("Мероприятие больше недоступно.", reply_markup=main_menu_keyboard())
        return

    if isinstance(selected_city, str) and selected_city and event.city != selected_city:
        await state.clear()
        await message.answer(
            "Мероприятие больше не относится к выбранному городу. Начните заказ заново.",
            reply_markup=main_menu_keyboard(),
        )
        return
    if isinstance(selected_event_type, str) and selected_event_type and event.event_type != selected_event_type:
        await state.clear()
        await message.answer(
            "Мероприятие больше не относится к выбранному типу события. Начните заказ заново.",
            reply_markup=main_menu_keyboard(),
        )
        return
    if (
        selected_event_type == DEFAULT_EVENT_TYPE
        and isinstance(selected_sport_type, str)
        and selected_sport_type
        and event.sport_type != selected_sport_type
    ):
        await state.clear()
        await message.answer(
            "Мероприятие больше не относится к выбранному типу спорта. Начните заказ заново.",
            reply_markup=main_menu_keyboard(),
        )
        return

    order = await create_order(
        session,
        user_id=user.id,
        event_id=event.id,
        quantity=quantity,
        # Поле оставлено для обратной совместимости со старой схемой orders.
        # Дополнительный вопрос клиенту больше не задается: город уже выбран в начале сценария.
        customer_location=event.city,
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


@router.message(F.text == CONTACT_MANAGER)
async def contact_manager_start(message: Message, session: AsyncSession, state: FSMContext) -> None:
    user = await _get_registered_user(message, session)
    if user is None:
        return

    await state.set_state(ManagerContactStates.waiting_message)
    await message.answer("Напишите сообщение для менеджера. Следующее сообщение будет отправлено в группу менеджеров.")


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


@router.message(F.text == MY_ORDERS)
async def my_orders(message: Message, session: AsyncSession) -> None:
    user = await _get_registered_user(message, session)
    if user is None:
        return

    orders = await list_user_orders(session, user.id)
    await message.answer(format_user_orders(orders), reply_markup=main_menu_keyboard())
