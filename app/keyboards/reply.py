from aiogram.types import KeyboardButton, ReplyKeyboardMarkup


BUY_TICKET = "Купить билет"
CONTACT_MANAGER = "Связаться с менеджером"
CUSTOM_ORDER = "Заказать событие не из списка"
MY_ORDERS = "Мои заказы"

CREATE_EVENT = "Создать мероприятие"
LIST_EVENTS = "Список мероприятий"
EDIT_EVENT = "Редактировать мероприятие"
DELETE_EVENT = "Удалить мероприятие"


def contact_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Отправить телефон", request_contact=True)],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
        input_field_placeholder="Нажмите кнопку ниже",
    )


def main_menu_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=BUY_TICKET)],
            [KeyboardButton(text=CUSTOM_ORDER)],
            [KeyboardButton(text=MY_ORDERS), KeyboardButton(text=CONTACT_MANAGER)],
        ],
        resize_keyboard=True,
    )


def manager_menu_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=CREATE_EVENT), KeyboardButton(text=LIST_EVENTS)],
            [KeyboardButton(text=EDIT_EVENT), KeyboardButton(text=DELETE_EVENT)],
        ],
        resize_keyboard=True,
    )
