from aiogram.fsm.state import State, StatesGroup


class PurchaseStates(StatesGroup):
    choosing_event = State()
    quantity = State()
    customer_location = State()
