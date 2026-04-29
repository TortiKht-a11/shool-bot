"""FSM states for parent application flow and admin actions."""

from aiogram.fsm.state import State, StatesGroup


class ApplicationFSM(StatesGroup):
    child_full_name = State()
    child_birth_date = State()
    child_gender = State()
    child_address = State()
    child_registration_address = State()
    kindergarten = State()
    parent_full_name = State()
    parent_relation = State()
    parent_phone = State()
    parent_email = State()
    parent_work = State()
    docs_birth_certificate = State()
    docs_parent_passport = State()
    docs_snils = State()
    docs_registration = State()
    confirm = State()


class ContactFSM(StatesGroup):
    parent_message = State()


class AdminCommentFSM(StatesGroup):
    comment_text = State()


class AdminSearchFSM(StatesGroup):
    query = State()


class AdminBroadcastFSM(StatesGroup):
    text = State()
    confirm = State()


class AdminReplyFSM(StatesGroup):
    reply_text = State()


class AdminWriteParentFSM(StatesGroup):
    text = State()
