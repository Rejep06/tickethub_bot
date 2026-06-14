import logging

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramAPIError, TelegramBadRequest
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.keyboards.inline import order_status_keyboard
from app.models.order import OrderStatus
from app.services.managers import get_manager_by_telegram_id
from app.services.orders import update_order_status
from app.utils.formatters import format_order_for_manager, status_label

router = Router()
logger = logging.getLogger(__name__)


def _parse_status_callback(callback_data: str) -> tuple[int, OrderStatus]:
    _, order_id_raw, status_raw = callback_data.split(":", maxsplit=2)
    return int(order_id_raw), OrderStatus(status_raw)


@router.callback_query(F.data.startswith("order_status:"))
async def change_order_status(callback: CallbackQuery, session: AsyncSession, bot: Bot) -> None:
    if callback.from_user is None or callback.data is None:
        return

    manager = await get_manager_by_telegram_id(session, callback.from_user.id)
    if manager is None:
        await callback.answer("Нет доступа.", show_alert=True)
        return

    try:
        order_id, new_status = _parse_status_callback(callback.data)
    except (ValueError, IndexError):
        await callback.answer("Некорректная кнопка.", show_alert=True)
        return

    order = await update_order_status(
        session,
        order_id=order_id,
        status=new_status,
        manager_id=manager.id,
    )
    if order is None:
        await callback.answer("Заказ не найден.", show_alert=True)
        return

    if isinstance(callback.message, Message):
        try:
            await callback.message.edit_text(
                format_order_for_manager(order),
                reply_markup=order_status_keyboard(order.id, order.status),
            )
        except TelegramBadRequest:
            # Например: сообщение уже содержит такой же текст.
            pass

    try:
        await bot.send_message(
            chat_id=order.user.telegram_id,
            text=f"Статус заказа #{order.id} изменен: <b>{status_label(order.status)}</b>.",
        )
    except TelegramAPIError:
        logger.exception("Could not notify user about order status change: order_id=%s", order.id)

    await callback.answer("Статус обновлен.")
