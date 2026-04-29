"""Inline keyboards for admins."""

from __future__ import annotations

from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from utils.texts import STATUS_EMOJI, STATUS_RU


def admin_panel_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text=" Все заявки", callback_data="admin_all_1")
    kb.button(text=" Новые заявки", callback_data="admin_new_1")
    kb.button(text=" Одобренные", callback_data="admin_approved_1")
    kb.button(text=" Отклонённые", callback_data="admin_rejected_1")
    kb.button(text=" Поиск заявки", callback_data="admin_search")
    kb.button(text=" Статистика", callback_data="admin_stats")
    kb.button(text=" Экспорт в Excel", callback_data="admin_export")
    kb.button(text=" Рассылка", callback_data="admin_broadcast")
    kb.adjust(1)
    return kb.as_markup()


def applications_list_kb(prefix: str, page: int, total_pages: int, rows: list[dict]) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for r in rows:
        status = r.get("status", "pending")
        emoji = STATUS_EMOJI.get(status, "🟡")
        kb.button(
            text=f"#{r['id']} | {r['child_full_name']} | {r['child_birth_date']} | {emoji}",
            callback_data=f"view_app_{r['id']}",
        )

    prev_page = max(1, page - 1)
    next_page = min(total_pages, page + 1)
    kb.button(text="⬅️", callback_data=f"{prefix}_{prev_page}")
    kb.button(text=f"Стр. {page}/{total_pages}", callback_data="noop")
    kb.button(text="➡️", callback_data=f"{prefix}_{next_page}")
    kb.adjust(1)
    kb.adjust(3)
    kb.button(text="⬅️ В админ-панель", callback_data="admin_panel")
    kb.adjust(1)
    return kb.as_markup()


def application_actions_kb(app_id: int, user_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text=" Посмотреть документы", callback_data=f"view_docs_{app_id}")
    kb.button(text="✅ Одобрить", callback_data=f"approve_{app_id}")
    kb.button(text=" Отклонить", callback_data=f"reject_{app_id}")
    kb.button(text=" Запросить документы", callback_data=f"request_docs_{app_id}")
    kb.button(text="✏️ Добавить комментарий", callback_data=f"comment_{app_id}")
    kb.button(text=" Написать родителю", callback_data=f"write_parent_{user_id}")
    kb.button(text="⬅️ Назад к списку", callback_data="admin_all_1")
    kb.adjust(1)
    return kb.as_markup()


def reply_button_kb(user_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text=" Ответить", callback_data=f"reply_{user_id}")
    return kb.as_markup()


def broadcast_confirm_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Да", callback_data="broadcast_yes")
    kb.button(text="❌ Нет", callback_data="broadcast_no")
    kb.adjust(2)
    return kb.as_markup()


def status_line(status: str) -> str:
    return f"{STATUS_EMOJI.get(status, '🟡')} {STATUS_RU.get(status, status)}"
