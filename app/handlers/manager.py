from datetime import datetime

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.keyboards.inline import (
    delete_confirm_keyboard,
    event_admin_events_keyboard,
    event_fields_keyboard,
)
from app.keyboards.reply import (
    CREATE_EVENT,
    DELETE_EVENT,
    EDIT_EVENT,
    LIST_EVENTS,
    manager_menu_keyboard,
)
from app.services.events import (
    create_event,
    delete_event,
    get_event,
    list_events,
    update_event_field,
)
from app.services.managers import is_manager
from app.states.event import EventCreateStates, EventEditStates
from app.utils.formatters import format_event_card, format_events_list

router = Router()

DATE_FORMAT = "%Y-%m-%d"
TIME_FORMAT = "%H:%M"


async def _require_manager_message(message: Message, session: AsyncSession) -> bool:
    if message.from_user is None:
        return False

    if await is_manager(session, message.from_user.id):
        return True

    await message.answer("Этот раздел доступен только менеджерам.")
    return False


async def _require_manager_callback(callback: CallbackQuery, session: AsyncSession) -> bool:
    if callback.from_user is None:
        return False

    if await is_manager(session, callback.from_user.id):
        return True

    await callback.answer("Нет доступа.", show_alert=True)
    return False


def _parse_date(raw_value: str):
    return datetime.strptime(raw_value.strip(), DATE_FORMAT).date()


def _parse_time(raw_value: str):
    return datetime.strptime(raw_value.strip(), TIME_FORMAT).time()


@router.message(Command("manager"))
async def manager_menu(message: Message, session: AsyncSession, state: FSMContext) -> None:
    if not await _require_manager_message(message, session):
        return

    await state.clear()
    await message.answer("Меню менеджера.", reply_markup=manager_menu_keyboard())


@router.message(F.text == CREATE_EVENT)
async def create_event_start(message: Message, session: AsyncSession, state: FSMContext) -> None:
    if not await _require_manager_message(message, session):
        return

    await state.set_state(EventCreateStates.title)
    await message.answer("Введите название мероприятия.")


@router.message(EventCreateStates.title)
async def create_event_title(message: Message, state: FSMContext) -> None:
    if not message.text or len(message.text.strip()) < 2:
        await message.answer("Введите название мероприятия.")
        return

    await state.update_data(title=message.text.strip())
    await state.set_state(EventCreateStates.event_date)
    await message.answer("Введите дату мероприятия в формате YYYY-MM-DD. Например: 2026-06-15")


@router.message(EventCreateStates.event_date)
async def create_event_date(message: Message, state: FSMContext) -> None:
    if not message.text:
        await message.answer("Введите дату в формате YYYY-MM-DD.")
        return

    try:
        event_date = _parse_date(message.text)
    except ValueError:
        await message.answer("Неверный формат даты. Пример: 2026-06-15")
        return

    await state.update_data(event_date=event_date)
    await state.set_state(EventCreateStates.event_time)
    await message.answer("Введите время мероприятия в формате HH:MM. Например: 19:30")


@router.message(EventCreateStates.event_time)
async def create_event_time(message: Message, state: FSMContext) -> None:
    if not message.text:
        await message.answer("Введите время в формате HH:MM.")
        return

    try:
        event_time = _parse_time(message.text)
    except ValueError:
        await message.answer("Неверный формат времени. Пример: 19:30")
        return

    await state.update_data(event_time=event_time)
    await state.set_state(EventCreateStates.location)
    await message.answer("Введите место проведения.")


@router.message(EventCreateStates.location)
async def create_event_location(message: Message, session: AsyncSession, state: FSMContext) -> None:
    if not message.text or len(message.text.strip()) < 2:
        await message.answer("Введите место проведения.")
        return

    data = await state.get_data()
    event = await create_event(
        session,
        title=data["title"],
        event_date=data["event_date"],
        event_time=data["event_time"],
        location=message.text.strip(),
    )

    await state.clear()
    await message.answer(
        "Мероприятие создано.\n\n" + format_event_card(event),
        reply_markup=manager_menu_keyboard(),
    )


@router.message(F.text == LIST_EVENTS)
async def events_list(message: Message, session: AsyncSession) -> None:
    if not await _require_manager_message(message, session):
        return

    events = await list_events(session)
    await message.answer(format_events_list(events), reply_markup=manager_menu_keyboard())


@router.message(F.text == EDIT_EVENT)
async def edit_event_start(message: Message, session: AsyncSession, state: FSMContext) -> None:
    if not await _require_manager_message(message, session):
        return

    await state.clear()
    events = await list_events(session)
    if not events:
        await message.answer("Мероприятий пока нет.", reply_markup=manager_menu_keyboard())
        return

    await message.answer("Выберите мероприятие для редактирования:", reply_markup=event_admin_events_keyboard(events, "edit"))


@router.callback_query(F.data.startswith("event_edit:"))
async def edit_event_choose(callback: CallbackQuery, session: AsyncSession) -> None:
    if not await _require_manager_callback(callback, session):
        return

    event_id = int(callback.data.split(":", maxsplit=1)[1])
    event = await get_event(session, event_id)
    if event is None:
        await callback.answer("Мероприятие не найдено.", show_alert=True)
        return

    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            format_event_card(event) + "\n\nЧто изменить?",
            reply_markup=event_fields_keyboard(event.id),
        )
    await callback.answer()


@router.callback_query(F.data.startswith("event_field:"))
async def edit_event_field(callback: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    if not await _require_manager_callback(callback, session):
        return

    _, event_id_raw, field = callback.data.split(":")
    event_id = int(event_id_raw)

    prompts = {
        "title": "Введите новое название.",
        "event_date": "Введите новую дату в формате YYYY-MM-DD.",
        "event_time": "Введите новое время в формате HH:MM.",
        "location": "Введите новое место проведения.",
    }
    if field not in prompts:
        await callback.answer("Неизвестное поле.", show_alert=True)
        return

    await state.update_data(event_id=event_id, field=field)
    await state.set_state(EventEditStates.new_value)

    if isinstance(callback.message, Message):
        await callback.message.edit_text(prompts[field])
    await callback.answer()


@router.message(EventEditStates.new_value)
async def edit_event_new_value(message: Message, session: AsyncSession, state: FSMContext) -> None:
    if not await _require_manager_message(message, session):
        return

    if not message.text or len(message.text.strip()) < 1:
        await message.answer("Введите новое значение.")
        return

    data = await state.get_data()
    event_id = int(data["event_id"])
    field = data["field"]
    raw_value = message.text.strip()

    try:
        if field == "event_date":
            value = _parse_date(raw_value)
        elif field == "event_time":
            value = _parse_time(raw_value)
        else:
            value = raw_value
    except ValueError:
        await message.answer("Неверный формат. Для даты используйте YYYY-MM-DD, для времени — HH:MM.")
        return

    event = await update_event_field(session, event_id=event_id, field=field, value=value)
    if event is None:
        await state.clear()
        await message.answer("Мероприятие не найдено.", reply_markup=manager_menu_keyboard())
        return

    await state.clear()
    await message.answer(
        "Мероприятие обновлено.\n\n" + format_event_card(event),
        reply_markup=manager_menu_keyboard(),
    )


@router.message(F.text == DELETE_EVENT)
async def delete_event_start(message: Message, session: AsyncSession, state: FSMContext) -> None:
    if not await _require_manager_message(message, session):
        return

    await state.clear()
    events = await list_events(session)
    if not events:
        await message.answer("Мероприятий пока нет.", reply_markup=manager_menu_keyboard())
        return

    await message.answer("Выберите мероприятие для удаления:", reply_markup=event_admin_events_keyboard(events, "delete"))


@router.callback_query(F.data.startswith("event_delete:"))
async def delete_event_choose(callback: CallbackQuery, session: AsyncSession) -> None:
    if not await _require_manager_callback(callback, session):
        return

    event_id = int(callback.data.split(":", maxsplit=1)[1])
    event = await get_event(session, event_id)
    if event is None:
        await callback.answer("Мероприятие не найдено.", show_alert=True)
        return

    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            "Удалить мероприятие?\n\n" + format_event_card(event),
            reply_markup=delete_confirm_keyboard(event.id),
        )
    await callback.answer()


@router.callback_query(F.data.startswith("event_delete_confirm:"))
async def delete_event_confirm(callback: CallbackQuery, session: AsyncSession) -> None:
    if not await _require_manager_callback(callback, session):
        return

    event_id = int(callback.data.split(":", maxsplit=1)[1])
    success, message_text = await delete_event(session, event_id)

    if isinstance(callback.message, Message):
        await callback.message.edit_text(message_text)
    await callback.answer("Готово." if success else "Не удалено.", show_alert=not success)


@router.callback_query(F.data == "event_delete_cancel")
async def delete_event_cancel(callback: CallbackQuery, session: AsyncSession) -> None:
    if not await _require_manager_callback(callback, session):
        return

    if isinstance(callback.message, Message):
        await callback.message.edit_text("Удаление отменено.")
    await callback.answer()
