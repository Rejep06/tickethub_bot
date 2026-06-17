from aiogram.fsm.state import State, StatesGroup


class EventCreateStates(StatesGroup):
    title = State()
    city = State()
    event_type = State()
    sport_type = State()
    event_date = State()
    event_time = State()
    location = State()


class EventEditStates(StatesGroup):
    new_value = State()
