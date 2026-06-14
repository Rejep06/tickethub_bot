from aiogram.fsm.state import State, StatesGroup


class ManagerContactStates(StatesGroup):
    waiting_message = State()
