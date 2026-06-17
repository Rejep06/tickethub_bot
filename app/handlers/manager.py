from datetime import datetime

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, ForceReply, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.keyboards.inline import (
    admin_event_types_keyboard,
    admin_sport_types_keyboard,
    delete_confirm_keyboard,
    event_admin_events_keyboard,
    event_fields_keyboard,
    manager_inline_menu_keyboard,
)
from app.keyboards.reply import (
    CREATE_EVENT,
    DELETE_EVENT,
    EDIT_EVENT,
    LIST_EVENTS,
    manager_menu_keyboard,
)
from app.services.events import (
    DEFAULT_EVENT_TYPE,
    EVENT_TYPE_LABELS,
    SPORT_TYPE_LABELS,
    create_event,
    delete_event,
    event_type_label,
    get_event,
    list_events,
    normalize_event_type,
    normalize_sport_type,
    sport_type_label,
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


def _is_group_chat(message: Message) -> bool:
    return message.chat.type in {"group", "supergroup"}


def _manager_text_reply_markup(message: Message) -> ForceReply | None:
    if not _is_group_chat(message):
        return None

    return ForceReply(selective=True, input_field_placeholder="Ответьте на это сообщение")


def _manager_menu_reply_markup(message: Message):
    if _is_group_chat(message):
        return manager_inline_menu_keyboard()
    return manager_menu_keyboard()


async def _answer_manager_prompt(message: Message, text: str) -> None:
    await message.answer(text, reply_markup=_manager_text_reply_markup(message))


def _event_type_prompt() -> str:
    options = ", ".join(EVENT_TYPE_LABELS.values())
    return (
        "Выберите тип события кнопкой или ответьте текстом.\n"
        f"Доступные варианты: {options}.\n"
        "По умолчанию: Спорт. Для значения по умолчанию можно отправить '-'."
    )


def _sport_type_prompt() -> str:
    options = ", ".join(SPORT_TYPE_LABELS.values())
    return (
        "Выберите тип спорта кнопкой или ответьте текстом.\n"
        f"Доступные варианты: {options}.\n"
        "По умолчанию: Футбол. Для значения по умолчанию можно отправить '-'."
    )


async def _ask_event_type(message: Message) -> None:
    await message.answer(_event_type_prompt(), reply_markup=admin_event_types_keyboard())


async def _ask_sport_type(message: Message) -> None:
    await message.answer(_sport_type_prompt(), reply_markup=admin_sport_types_keyboard())


async def _continue_create_after_event_type(message: Message, state: FSMContext, event_type: str) -> None:
    await state.update_data(event_type=event_type)
    if event_type == DEFAULT_EVENT_TYPE:
        await state.set_state(EventCreateStates.sport_type)
        await _ask_sport_type(message)
        return

    await state.update_data(sport_type=None)
    await state.set_state(EventCreateStates.event_date)
    await _answer_manager_prompt(message, "Введите дату мероприятия в формате YYYY-MM-DD. Например: 2026-06-15")


async def _continue_create_after_sport_type(message: Message, state: FSMContext, sport_type: str) -> None:
    await state.update_data(sport_type=sport_type)
    await state.set_state(EventCreateStates.event_date)
    await _answer_manager_prompt(message, "Введите дату мероприятия в формате YYYY-MM-DD. Например: 2026-06-15")


def _manager_group_menu_text() -> str:
    return (
        "Меню менеджера.\n\n"
        "В группе Telegram бот получает обычный текст только если сообщение написано ответом "
        "на сообщение бота. Используйте кнопки ниже или ответьте на это сообщение одним из вариантов:\n"
        f"— {CREATE_EVENT}\n"
        f"— {LIST_EVENTS}\n"
        f"— {EDIT_EVENT}\n"
        f"— {DELETE_EVENT}"
    )


@router.message(Command("manager"))
async def manager_menu(message: Message, session: AsyncSession, state: FSMContext) -> None:
    if not await _require_manager_message(message, session):
        return

    await state.clear()
    if _is_group_chat(message):
        await message.answer(_manager_group_menu_text(), reply_markup=manager_inline_menu_keyboard())
        return

    await message.answer("Меню менеджера.", reply_markup=manager_menu_keyboard())


@router.callback_query(F.data.startswith("manager_action:"))
async def manager_menu_action(callback: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    if not await _require_manager_callback(callback, session):
        return

    if callback.data is None or not isinstance(callback.message, Message):
        return

    action = callback.data.split(":", maxsplit=1)[1]

    if action == "create":
        await state.clear()
        await state.set_state(EventCreateStates.title)
        await _answer_manager_prompt(callback.message, "Введите название мероприятия.")
        await callback.answer()
        return

    if action == "list":
        await state.clear()
        events = await list_events(session)
        await callback.message.answer(format_events_list(events))
        await callback.answer()
        return

    if action == "edit":
        await state.clear()
        events = await list_events(session)
        if not events:
            await callback.message.answer("Мероприятий пока нет.")
            await callback.answer()
            return
        await callback.message.answer(
            "Выберите мероприятие для редактирования:",
            reply_markup=event_admin_events_keyboard(events, "edit"),
        )
        await callback.answer()
        return

    if action == "delete":
        await state.clear()
        events = await list_events(session)
        if not events:
            await callback.message.answer("Мероприятий пока нет.")
            await callback.answer()
            return
        await callback.message.answer(
            "Выберите мероприятие для удаления:",
            reply_markup=event_admin_events_keyboard(events, "delete"),
        )
        await callback.answer()
        return

    await callback.answer("Неизвестное действие.", show_alert=True)


@router.message(F.text == CREATE_EVENT)
async def create_event_start(message: Message, session: AsyncSession, state: FSMContext) -> None:
    if not await _require_manager_message(message, session):
        return

    await state.clear()
    await state.set_state(EventCreateStates.title)
    await _answer_manager_prompt(message, "Введите название мероприятия.")


@router.message(EventCreateStates.title)
async def create_event_title(message: Message, state: FSMContext) -> None:
    if not message.text or len(message.text.strip()) < 2:
        await _answer_manager_prompt(message, "Введите название мероприятия.")
        return

    await state.update_data(title=message.text.strip())
    await state.set_state(EventCreateStates.city)
    await _answer_manager_prompt(message, "Введите город проведения.")


@router.message(EventCreateStates.city)
async def create_event_city(message: Message, state: FSMContext) -> None:
    if not message.text or len(message.text.strip()) < 2:
        await _answer_manager_prompt(message, "Введите город проведения.")
        return

    await state.update_data(city=message.text.strip())
    await state.set_state(EventCreateStates.event_type)
    await _ask_event_type(message)


@router.callback_query(F.data.startswith("event_create_type:"))
async def create_event_type_callback(callback: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    if not await _require_manager_callback(callback, session):
        return
    if callback.data is None or not isinstance(callback.message, Message):
        return

    current_state = await state.get_state()
    if current_state != EventCreateStates.event_type.state:
        await callback.answer("Этот выбор уже неактуален.", show_alert=True)
        return

    event_type = normalize_event_type(callback.data.split(":", maxsplit=1)[1])
    await _continue_create_after_event_type(callback.message, state, event_type)
    await callback.answer(event_type_label(event_type))


@router.message(EventCreateStates.event_type)
async def create_event_type_message(message: Message, state: FSMContext) -> None:
    if not message.text:
        await _ask_event_type(message)
        return

    event_type = normalize_event_type(message.text)
    await _continue_create_after_event_type(message, state, event_type)


@router.callback_query(F.data.startswith("event_create_sport:"))
async def create_sport_type_callback(callback: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    if not await _require_manager_callback(callback, session):
        return
    if callback.data is None or not isinstance(callback.message, Message):
        return

    current_state = await state.get_state()
    if current_state != EventCreateStates.sport_type.state:
        await callback.answer("Этот выбор уже неактуален.", show_alert=True)
        return

    sport_type = normalize_sport_type(callback.data.split(":", maxsplit=1)[1])
    await _continue_create_after_sport_type(callback.message, state, sport_type)
    await callback.answer(sport_type_label(sport_type))


@router.message(EventCreateStates.sport_type)
async def create_sport_type_message(message: Message, state: FSMContext) -> None:
    if not message.text:
        await _ask_sport_type(message)
        return

    sport_type = normalize_sport_type(message.text)
    await _continue_create_after_sport_type(message, state, sport_type)


@router.message(EventCreateStates.event_date)
async def create_event_date(message: Message, state: FSMContext) -> None:
    if not message.text:
        await _answer_manager_prompt(message, "Введите дату в формате YYYY-MM-DD.")
        return

    try:
        event_date = _parse_date(message.text)
    except ValueError:
        await _answer_manager_prompt(message, "Неверный формат даты. Пример: 2026-06-15")
        return

    await state.update_data(event_date=event_date)
    await state.set_state(EventCreateStates.event_time)
    await _answer_manager_prompt(message, "Введите время мероприятия в формате HH:MM. Например: 19:30")


@router.message(EventCreateStates.event_time)
async def create_event_time(message: Message, state: FSMContext) -> None:
    if not message.text:
        await _answer_manager_prompt(message, "Введите время в формате HH:MM.")
        return

    try:
        event_time = _parse_time(message.text)
    except ValueError:
        await _answer_manager_prompt(message, "Неверный формат времени. Пример: 19:30")
        return

    await state.update_data(event_time=event_time)
    await state.set_state(EventCreateStates.location)
    await _answer_manager_prompt(message, "Введите место проведения.")


@router.message(EventCreateStates.location)
async def create_event_location(message: Message, session: AsyncSession, state: FSMContext) -> None:
    if not message.text or len(message.text.strip()) < 2:
        await _answer_manager_prompt(message, "Введите место проведения.")
        return

    data = await state.get_data()
    event = await create_event(
        session,
        title=data["title"],
        city=data["city"],
        event_type=data.get("event_type", DEFAULT_EVENT_TYPE),
        sport_type=data.get("sport_type"),
        event_date=data["event_date"],
        event_time=data["event_time"],
        location=message.text.strip(),
    )

    await state.clear()
    await message.answer(
        "Мероприятие создано.\n\n" + format_event_card(event),
        reply_markup=_manager_menu_reply_markup(message),
    )


@router.message(F.text == LIST_EVENTS)
async def events_list(message: Message, session: AsyncSession) -> None:
    if not await _require_manager_message(message, session):
        return

    events = await list_events(session)
    await message.answer(format_events_list(events), reply_markup=_manager_menu_reply_markup(message))


@router.message(F.text == EDIT_EVENT)
async def edit_event_start(message: Message, session: AsyncSession, state: FSMContext) -> None:
    if not await _require_manager_message(message, session):
        return

    await state.clear()
    events = await list_events(session)
    if not events:
        await message.answer("Мероприятий пока нет.", reply_markup=_manager_menu_reply_markup(message))
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
        "city": "Введите новый город проведения.",
        "event_type": (
            "Введите новый тип события: спорт, концерт, театр, фестиваль, шоу, выставка или другое. "
            "По умолчанию: спорт. Для значения по умолчанию можно отправить '-'."
        ),
        "sport_type": (
            "Введите новый тип спорта: футбол, баскетбол, волейбол, хоккей, теннис, бокс, MMA, бег или другое. "
            "По умолчанию: футбол. Для значения по умолчанию можно отправить '-'."
        ),
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
        await _answer_manager_prompt(callback.message, prompts[field])
    await callback.answer()


@router.message(EventEditStates.new_value)
async def edit_event_new_value(message: Message, session: AsyncSession, state: FSMContext) -> None:
    if not await _require_manager_message(message, session):
        return

    if not message.text or len(message.text.strip()) < 1:
        await _answer_manager_prompt(message, "Введите новое значение.")
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
        elif field == "event_type":
            value = normalize_event_type(raw_value)
        elif field == "sport_type":
            value = normalize_sport_type(raw_value)
        else:
            value = raw_value
    except ValueError:
        await _answer_manager_prompt(message, "Неверный формат. Для даты используйте YYYY-MM-DD, для времени — HH:MM.")
        return

    event = await update_event_field(session, event_id=event_id, field=field, value=value)
    if event is None:
        await state.clear()
        await message.answer("Мероприятие не найдено.", reply_markup=_manager_menu_reply_markup(message))
        return

    await state.clear()
    await message.answer(
        "Мероприятие обновлено.\n\n" + format_event_card(event),
        reply_markup=_manager_menu_reply_markup(message),
    )


@router.message(F.text == DELETE_EVENT)
async def delete_event_start(message: Message, session: AsyncSession, state: FSMContext) -> None:
    if not await _require_manager_message(message, session):
        return

    await state.clear()
    events = await list_events(session)
    if not events:
        await message.answer("Мероприятий пока нет.", reply_markup=_manager_menu_reply_markup(message))
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
