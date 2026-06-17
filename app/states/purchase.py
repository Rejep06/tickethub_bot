from aiogram.fsm.state import State, StatesGroup


class PurchaseStates(StatesGroup):
    choosing_event_type = State()
    choosing_sport_type = State()
    choosing_event = State()
    custom_event = State()
    quantity = State()
