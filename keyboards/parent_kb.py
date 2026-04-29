"""Inline keyboards for parents."""

from __future__ import annotations

from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from utils.texts import FAQ_QUESTIONS, SCHOOL_SITE


def parent_main_menu() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text=" Подать заявление", callback_data="apply_start")
    kb.button(text=" Мои заявки", callback_data="my_applications")
    kb.button(text=" Список документов", callback_data="documents_list")
    kb.button(text=" О школе", callback_data="about_school")
    kb.button(text=" Сайт школы", url=SCHOOL_SITE)
    kb.button(text=" Контакты", callback_data="contacts")
    kb.button(text="❓ FAQ", callback_data="faq")
    kb.button(text=" Связаться с комиссией", callback_data="contact_admin")
    kb.adjust(1)
    return kb.as_markup()


def back_to_menu() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="⬅️ Назад в меню", callback_data="main_menu")
    return kb.as_markup()


def cancel_application() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="❌ Отменить", callback_data="cancel_application")
    return kb.as_markup()

def cancel_fsm() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="❌ Отменить", callback_data="cancel_fsm")
    return kb.as_markup()


def gender_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text=" Мальчик", callback_data="gender_male")
    kb.button(text=" Девочка", callback_data="gender_female")
    kb.adjust(2)
    kb.button(text="❌ Отменить", callback_data="cancel_application")
    kb.adjust(2, 1)
    return kb.as_markup()


def registration_same_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Совпадает с адресом проживания", callback_data="reg_same")
    kb.button(text="❌ Отменить", callback_data="cancel_application")
    kb.adjust(1)
    return kb.as_markup()


def kindergarten_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="❌ Не посещал", callback_data="kindergarten_none")
    kb.button(text="❌ Отменить", callback_data="cancel_application")
    kb.adjust(1)
    return kb.as_markup()


def relation_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text=" Мать", callback_data="relation_mother")
    kb.button(text=" Отец", callback_data="relation_father")
    kb.button(text=" Опекун", callback_data="relation_guardian")
    kb.adjust(3)
    kb.button(text="❌ Отменить", callback_data="cancel_application")
    kb.adjust(3, 1)
    return kb.as_markup()


def skip_email_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="⏭️ Пропустить", callback_data="skip_email")
    kb.button(text="❌ Отменить", callback_data="cancel_application")
    kb.adjust(1)
    return kb.as_markup()


def skip_work_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="⏭️ Пропустить", callback_data="skip_work")
    kb.button(text="❌ Отменить", callback_data="cancel_application")
    kb.adjust(1)
    return kb.as_markup()


def skip_snils_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="⏭️ Пропустить", callback_data="skip_snils")
    kb.button(text="❌ Отменить", callback_data="cancel_application")
    kb.adjust(1)
    return kb.as_markup()


def confirm_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Подтвердить и отправить", callback_data="confirm_application")
    kb.button(text="❌ Отменить", callback_data="cancel_application")
    kb.adjust(1)
    return kb.as_markup()


def faq_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for idx, q in enumerate(FAQ_QUESTIONS, start=1):
        kb.button(text=f"{idx}. {q}", callback_data=f"faq_{idx}")
    kb.button(text="⬅️ Назад в меню", callback_data="main_menu")
    kb.adjust(1)
    return kb.as_markup()


def faq_back_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="⬅️ Назад к FAQ", callback_data="faq")
    return kb.as_markup()
