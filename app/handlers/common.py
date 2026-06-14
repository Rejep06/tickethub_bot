from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.keyboards.reply import contact_keyboard, main_menu_keyboard
from app.services.users import create_or_update_user

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(
        "Здравствуйте. Чтобы начать работу, отправьте номер телефона кнопкой ниже.",
        reply_markup=contact_keyboard(),
    )


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Текущий сценарий отменен.", reply_markup=main_menu_keyboard())


@router.message(F.contact)
async def handle_contact(message: Message, session: AsyncSession, state: FSMContext) -> None:
    if message.from_user is None or message.contact is None:
        return

    contact_user_id = message.contact.user_id
    if contact_user_id is not None and contact_user_id != message.from_user.id:
        await message.answer("Отправьте свой номер телефона через кнопку Telegram.")
        return

    await create_or_update_user(
        session,
        telegram_id=message.from_user.id,
        username=message.from_user.username,
        phone_number=message.contact.phone_number,
    )

    await state.clear()
    await message.answer(
        "Регистрация завершена. Выберите действие в меню.",
        reply_markup=main_menu_keyboard(),
    )
