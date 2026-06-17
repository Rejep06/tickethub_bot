from aiogram.fsm.state import State, StatesGroup


class PurchaseStates(StatesGroup):
    choosing_city = State()
    choosing_event_type = State()
    choosing_sport_type = State()
    choosing_event = State()
    quantity = State()
