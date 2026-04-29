"""Admin panel: lists, search, status changes, comments, export, broadcast, replies."""

from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, FSInputFile, Message

from config import Config
from db import connect
from db.queries import (
    create_message,
    get_application_by_id,
    list_all_user_ids,
    list_applications,
    search_applications,
    stats as db_stats,
    update_admin_comment,
    update_application_status,
)
from keyboards.admin_kb import (
    admin_panel_kb,
    application_actions_kb,
    applications_list_kb,
    broadcast_confirm_kb,
    status_line,
)
from keyboards.parent_kb import parent_main_menu
from states import (
    AdminBroadcastFSM,
    AdminCommentFSM,
    AdminReplyFSM,
    AdminSearchFSM,
    AdminWriteParentFSM,
)
from utils.exporter import export_applications_xlsx
from utils.texts import ADMIN_NO_ACCESS, ADMIN_PANEL, CONTACT_PHONE, STATUS_EMOJI, STATUS_RU

router = Router()
logger = logging.getLogger(__name__)

PAGE_SIZE = 10


def _require_admin(user_id: int, config: Config) -> bool:
    return user_id in config.admin_ids


def _status_from_prefix(prefix: str) -> str | None:
    if prefix == "admin_new":
        return "pending"
    if prefix == "admin_approved":
        return "approved"
    if prefix == "admin_rejected":
        return "rejected"
    if prefix == "admin_all":
        return None
    return None


def _as_dicts(rows) -> list[dict]:
    return [dict(r) for r in rows]


@router.message(Command("admin"))
async def cmd_admin(message: Message, config: Config) -> None:
    if message.from_user is None or not _require_admin(message.from_user.id, config):
        await message.answer(ADMIN_NO_ACCESS)
        return
    await message.answer(ADMIN_PANEL, reply_markup=admin_panel_kb())


@router.callback_query(F.data == "admin_panel")
async def cb_admin_panel(callback: CallbackQuery, config: Config) -> None:
    if callback.from_user is None or not _require_admin(callback.from_user.id, config):
        await callback.answer("Нет доступа", show_alert=True)
        return
    await callback.message.edit_text(ADMIN_PANEL, reply_markup=admin_panel_kb())  # type: ignore[union-attr]
    await callback.answer()


@router.callback_query(F.data.regexp(r"^admin_(all|new|approved|rejected)_(\d+)$"))
async def cb_admin_list(callback: CallbackQuery, config: Config) -> None:
    if callback.from_user is None or not _require_admin(callback.from_user.id, config) or callback.message is None:
        return
    prefix, page_s = callback.data.rsplit("_", 1)
    page = max(1, int(page_s))
    status = _status_from_prefix(prefix)

    async with connect(str(config.db_path)) as db:
        rows, total = await list_applications(db, status=status, limit=PAGE_SIZE, offset=(page - 1) * PAGE_SIZE)

    total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    rows_dict = _as_dicts(rows)
    kb = applications_list_kb(prefix=prefix, page=page, total_pages=total_pages, rows=rows_dict)
    title = {
        "admin_all": "Все заявки",
        "admin_new": "Новые заявки",
        "admin_approved": "Одобренные",
        "admin_rejected": "Отклонённые",
    }.get(prefix, "Заявки")

    await callback.message.edit_text(f"{title} (всего: {total})", reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data.startswith("view_app_"))
async def cb_view_application(callback: CallbackQuery, config: Config) -> None:
    if callback.from_user is None or not _require_admin(callback.from_user.id, config) or callback.message is None:
        await callback.answer("Нет доступа", show_alert=True)
        return
    app_id = int(callback.data.split("_", 2)[-1])
    async with connect(str(config.db_path)) as db:
        row = await get_application_by_id(db, app_id)
    if not row:
        await callback.answer("Заявка не найдена", show_alert=True)
        return

    status = row["status"]
    docs = {
        "birth": "✅" if row["docs_birth_certificate"] else "❌",
        "passport": "✅" if row["docs_parent_passport"] else "❌",
        "snils": "✅" if row["docs_snils"] else "❌",
        "reg": "✅" if row["docs_registration"] else "❌",
    }
    text = (
        f" Заявка #{row['id']}\n"
        f"Статус: {STATUS_EMOJI.get(status, '🟡')} {STATUS_RU.get(status, status)}\n"
        f"Создана: {row['created_at']}\n"
        f"Обновлена: {row['updated_at']}\n\n"
        " РЕБЁНОК:\n"
        f"ФИО: {row['child_full_name']}\n"
        f"Дата рождения: {row['child_birth_date']}\n"
        f"Пол: {row['child_gender']}\n"
        f"Адрес проживания: {row['child_address']}\n"
        f"Адрес регистрации: {row['child_registration_address']}\n"
        f"Детский сад: {row['kindergarten'] or '—'}\n\n"
        " РОДИТЕЛЬ:\n"
        f"ФИО: {row['parent_full_name']}\n"
        f"Степень родства: {row['parent_relation']}\n"
        f"Телефон: {row['parent_phone']}\n"
        f"Email: {row['parent_email'] or '—'}\n"
        f"Место работы: {row['parent_work'] or '—'}\n\n"
        f" Комментарий админа: {row['admin_comment'] or '—'}\n\n"
        " Документы:\n"
        f"- Свидетельство о рождении: {docs['birth']}\n"
        f"- Паспорт родителя: {docs['passport']}\n"
        f"- СНИЛС: {docs['snils']}\n"
        f"- Регистрация: {docs['reg']}"
    )
    await callback.message.edit_text(text, reply_markup=application_actions_kb(app_id=row["id"], user_id=row["user_id"]))
    await callback.answer()


@router.callback_query(F.data.startswith("view_docs_"))
async def cb_view_docs(callback: CallbackQuery, config: Config) -> None:
    if callback.from_user is None or not _require_admin(callback.from_user.id, config):
        await callback.answer("Нет доступа", show_alert=True)
        return
    app_id = int(callback.data.split("_", 2)[-1])
    app_dir = config.uploads_dir / str(app_id)
    if not app_dir.exists():
        await callback.answer("Файлы не найдены", show_alert=True)
        return
    files = sorted([p for p in app_dir.iterdir() if p.is_file()])
    if not files:
        await callback.answer("Файлы не найдены", show_alert=True)
        return
    for p in files:
        try:
            await callback.bot.send_document(callback.from_user.id, FSInputFile(p))
        except Exception:
            logger.exception("Failed to send doc %s", p)
    await callback.answer("Документы отправлены")


@router.callback_query(F.data.startswith("approve_"))
async def cb_approve(callback: CallbackQuery, config: Config) -> None:
    if callback.from_user is None or not _require_admin(callback.from_user.id, config):
        await callback.answer("Нет доступа", show_alert=True)
        return
    app_id = int(callback.data.split("_", 1)[-1])
    async with connect(str(config.db_path)) as db:
        await update_application_status(db, app_id, "approved", None)
        row = await get_application_by_id(db, app_id)
    if row:
        try:
            await callback.bot.send_message(
                int(row["user_id"]),
                f" Статус вашей заявки #{app_id} изменён:\n{status_line('approved')}",
            )
        except Exception:
            logger.exception("Failed to notify parent")
    await callback.answer("Одобрено")
    await cb_view_application(callback, config)


@router.callback_query(F.data.startswith("reject_"))
async def cb_reject(callback: CallbackQuery, state: FSMContext, config: Config) -> None:
    if callback.from_user is None or not _require_admin(callback.from_user.id, config):
        await callback.answer("Нет доступа", show_alert=True)
        return
    app_id = int(callback.data.split("_", 1)[-1])
    await state.set_state(AdminCommentFSM.comment_text)
    await state.update_data(target_app_id=app_id, target_status="rejected")
    await callback.message.edit_text("Введите комментарий для отклонения заявки:")  # type: ignore[union-attr]
    await callback.answer()


@router.callback_query(F.data.startswith("request_docs_"))
async def cb_request_docs(callback: CallbackQuery, state: FSMContext, config: Config) -> None:
    if callback.from_user is None or not _require_admin(callback.from_user.id, config):
        await callback.answer("Нет доступа", show_alert=True)
        return
    app_id = int(callback.data.split("_", 2)[-1])
    await state.set_state(AdminCommentFSM.comment_text)
    await state.update_data(target_app_id=app_id, target_status="docs_required")
    await callback.message.edit_text("Введите комментарий (какие документы требуются):")  # type: ignore[union-attr]
    await callback.answer()


@router.callback_query(F.data.startswith("comment_"))
async def cb_add_comment(callback: CallbackQuery, state: FSMContext, config: Config) -> None:
    if callback.from_user is None or not _require_admin(callback.from_user.id, config):
        await callback.answer("Нет доступа", show_alert=True)
        return
    app_id = int(callback.data.split("_", 1)[-1])
    await state.set_state(AdminCommentFSM.comment_text)
    await state.update_data(target_app_id=app_id, target_status=None)
    await callback.message.edit_text("Введите комментарий к заявке:")  # type: ignore[union-attr]
    await callback.answer()


@router.message(AdminCommentFSM.comment_text)
async def admin_comment_text(message: Message, state: FSMContext, config: Config) -> None:
    if message.from_user is None or not _require_admin(message.from_user.id, config) or not message.text:
        return
    data = await state.get_data()
    app_id = int(data["target_app_id"])
    status = data.get("target_status")
    comment = message.text.strip()
    async with connect(str(config.db_path)) as db:
        if status:
            await update_application_status(db, app_id, status, comment)
        else:
            await update_admin_comment(db, app_id, comment)
        row = await get_application_by_id(db, app_id)

    if status and row:
        try:
            await message.bot.send_message(
                int(row["user_id"]),
                (
                    f" Статус вашей заявки #{app_id} изменён:\n"
                    f"{status_line(status)}\n\n"
                    f"{comment}"
                ),
            )
        except Exception:
            logger.exception("Failed to notify parent")

    await state.clear()
    await message.answer("✅ Готово.", reply_markup=admin_panel_kb())


@router.callback_query(F.data == "admin_search")
async def cb_admin_search(callback: CallbackQuery, state: FSMContext, config: Config) -> None:
    if callback.from_user is None or not _require_admin(callback.from_user.id, config):
        await callback.answer("Нет доступа", show_alert=True)
        return
    await state.set_state(AdminSearchFSM.query)
    await callback.message.edit_text("Введите ID заявки, ФИО ребёнка или телефон родителя:")  # type: ignore[union-attr]
    await callback.answer()


@router.message(AdminSearchFSM.query)
async def admin_search_query(message: Message, state: FSMContext, config: Config) -> None:
    if message.from_user is None or not _require_admin(message.from_user.id, config) or not message.text:
        return
    q = message.text.strip()
    async with connect(str(config.db_path)) as db:
        rows = await search_applications(db, q)
    await state.clear()
    if not rows:
        await message.answer("❌ Ничего не найдено.", reply_markup=admin_panel_kb())
        return
    from aiogram.utils.keyboard import InlineKeyboardBuilder

    kb = InlineKeyboardBuilder()
    for r in rows:
        emoji = STATUS_EMOJI.get(r["status"], "🟡")
        kb.button(text=f"#{r['id']} | {r['child_full_name']} | {r['child_birth_date']} | {emoji}", callback_data=f"view_app_{r['id']}")
    kb.button(text="⬅️ В админ-панель", callback_data="admin_panel")
    kb.adjust(1)
    await message.answer("Найдено:", reply_markup=kb.as_markup())


@router.callback_query(F.data == "admin_stats")
async def cb_admin_stats(callback: CallbackQuery, config: Config) -> None:
    if callback.from_user is None or not _require_admin(callback.from_user.id, config):
        await callback.answer("Нет доступа", show_alert=True)
        return
    async with connect(str(config.db_path)) as db:
        s = await db_stats(db)
    text = (
        " Статистика заявок\n\n"
        f"Всего заявок: {s['total']}\n\n"
        "По статусам:\n"
        f" На рассмотрении: {s['pending']}\n"
        f" Одобрено: {s['approved']}\n"
        f" Отклонено: {s['rejected']}\n"
        f" Требуются документы: {s['docs_required']}\n\n"
        " Период:\n"
        f"За сегодня: {s['today']}\n"
        f"За неделю: {s['week']}\n"
        f"За месяц: {s['month']}\n\n"
        " По полу:\n"
        f" Мальчики: {s['male']}\n"
        f" Девочки: {s['female']}\n\n"
        " Школа \"Новый город\""
    )
    from aiogram.utils.keyboard import InlineKeyboardBuilder

    kb = InlineKeyboardBuilder()
    kb.button(text="⬅️ В админ-панель", callback_data="admin_panel")
    await callback.message.edit_text(text, reply_markup=kb.as_markup())  # type: ignore[union-attr]
    await callback.answer()


@router.callback_query(F.data == "admin_export")
async def cb_admin_export(callback: CallbackQuery, config: Config) -> None:
    if callback.from_user is None or not _require_admin(callback.from_user.id, config):
        await callback.answer("Нет доступа", show_alert=True)
        return
    async with connect(str(config.db_path)) as db:
        rows, _ = await list_applications(db, status=None, limit=100000, offset=0)
    xlsx = export_applications_xlsx([dict(r) for r in rows], out_dir=Path.cwd())
    try:
        await callback.bot.send_document(callback.from_user.id, FSInputFile(xlsx))
    finally:
        try:
            xlsx.unlink(missing_ok=True)
        except Exception:
            logger.exception("Failed to delete temp export %s", xlsx)
    await callback.answer("Экспорт готов")


@router.callback_query(F.data == "admin_broadcast")
async def cb_admin_broadcast(callback: CallbackQuery, state: FSMContext, config: Config) -> None:
    if callback.from_user is None or not _require_admin(callback.from_user.id, config):
        await callback.answer("Нет доступа", show_alert=True)
        return
    await state.set_state(AdminBroadcastFSM.text)
    await callback.message.edit_text("Введите текст рассылки. Он будет отправлен всем пользователям, которые когда-либо писали боту.")  # type: ignore[union-attr]
    await callback.answer()


@router.message(AdminBroadcastFSM.text)
async def admin_broadcast_text(message: Message, state: FSMContext, config: Config) -> None:
    if message.from_user is None or not _require_admin(message.from_user.id, config) or not message.text:
        return
    async with connect(str(config.db_path)) as db:
        user_ids = await list_all_user_ids(db)
    await state.update_data(broadcast_text=message.text, broadcast_total=len(user_ids))
    await state.set_state(AdminBroadcastFSM.confirm)
    await message.answer(f"Отправить сообщение {len(user_ids)} пользователям?", reply_markup=broadcast_confirm_kb())


@router.callback_query(AdminBroadcastFSM.confirm, F.data.in_(["broadcast_yes", "broadcast_no"]))
async def admin_broadcast_confirm(callback: CallbackQuery, state: FSMContext, config: Config) -> None:
    if callback.from_user is None or not _require_admin(callback.from_user.id, config) or callback.message is None:
        return
    if callback.data == "broadcast_no":
        await state.clear()
        await callback.message.edit_text("Отменено.", reply_markup=admin_panel_kb())
        await callback.answer()
        return

    data = await state.get_data()
    text = data.get("broadcast_text", "")
    await state.clear()
    async with connect(str(config.db_path)) as db:
        user_ids = await list_all_user_ids(db)

    total = len(user_ids)
    success = 0
    fail = 0
    progress_msg = await callback.message.edit_text(f"Отправлено: 0/{total}")
    for idx, uid in enumerate(user_ids, start=1):
        try:
            await callback.bot.send_message(uid, text)
            success += 1
        except Exception:
            fail += 1
        await asyncio.sleep(0.05)
        if idx % 50 == 0:
            try:
                await progress_msg.edit_text(f"Отправлено: {idx}/{total}")
            except Exception:
                pass
    await progress_msg.edit_text(f"✅ Рассылка завершена. Доставлено: {success}, ошибок: {fail}.", reply_markup=admin_panel_kb())
    await callback.answer()


@router.callback_query(F.data.startswith("reply_"))
async def cb_reply_from_forward(callback: CallbackQuery, state: FSMContext, config: Config) -> None:
    if callback.from_user is None or not _require_admin(callback.from_user.id, config) or callback.message is None:
        return
    user_id = int(callback.data.split("_", 1)[-1])
    await state.set_state(AdminReplyFSM.reply_text)
    await state.update_data(reply_user_id=user_id)
    await callback.message.edit_text(f"Введите ответ пользователю ID {user_id}:")
    await callback.answer()


@router.message(Command("reply"))
async def cmd_reply(message: Message, config: Config) -> None:
    if message.from_user is None or not _require_admin(message.from_user.id, config):
        await message.answer(ADMIN_NO_ACCESS)
        return
    if not message.text:
        return
    parts = message.text.split(maxsplit=2)
    if len(parts) < 3 or not parts[1].isdigit():
        await message.answer("Использование: /reply <user_id> <текст>")
        return
    user_id = int(parts[1])
    text = parts[2].strip()
    await _send_reply_to_parent(message, config, user_id, text)


async def _send_reply_to_parent(message: Message, config: Config, user_id: int, text: str) -> None:
    reply_text = (
        " Ответ от приёмной комиссии школы \"Новый город\":\n\n"
        f"{text}\n\n"
        f" {CONTACT_PHONE} (Диана Казбековна)"
    )
    try:
        await message.bot.send_message(user_id, reply_text)  # type: ignore[union-attr]
    except Exception:
        await message.answer("Не удалось отправить сообщение пользователю.")
        logger.exception("Failed to send reply to %s", user_id)
        return

    async with connect(str(config.db_path)) as db:
        await create_message(db, user_id, None, text, is_from_admin=1)
    await message.answer("✅ Ответ отправлен.")


@router.message(AdminReplyFSM.reply_text)
async def admin_reply_text(message: Message, state: FSMContext, config: Config) -> None:
    if message.from_user is None or not _require_admin(message.from_user.id, config) or not message.text:
        return
    data = await state.get_data()
    user_id = int(data["reply_user_id"])
    text = message.text.strip()
    await state.clear()
    await _send_reply_to_parent(message, config, user_id, text)


@router.callback_query(F.data.startswith("write_parent_"))
async def cb_write_parent(callback: CallbackQuery, state: FSMContext, config: Config) -> None:
    if callback.from_user is None or not _require_admin(callback.from_user.id, config) or callback.message is None:
        return
    user_id = int(callback.data.split("_", 2)[-1])
    await state.set_state(AdminWriteParentFSM.text)
    await state.update_data(write_user_id=user_id)
    await callback.message.edit_text(f"Введите сообщение родителю (ID: {user_id}):")
    await callback.answer()


@router.message(AdminWriteParentFSM.text)
async def admin_write_parent_text(message: Message, state: FSMContext, config: Config) -> None:
    if message.from_user is None or not _require_admin(message.from_user.id, config) or not message.text:
        return
    data = await state.get_data()
    user_id = int(data["write_user_id"])
    text = message.text.strip()
    await state.clear()
    try:
        await message.bot.send_message(user_id, text)  # type: ignore[union-attr]
        await message.answer("✅ Отправлено.", reply_markup=admin_panel_kb())
    except Exception:
        logger.exception("Failed to write parent")
        await message.answer("Не удалось отправить сообщение пользователю.", reply_markup=admin_panel_kb())
