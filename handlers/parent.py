"""Parent flow: application FSM, my applications, school info, FAQ, contact commission."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from config import Config
from db import connect
from db.queries import (
    create_application_draft,
    create_message,
    delete_application,
    finalize_application,
    get_application_by_id,
    get_user_applications,
)
from keyboards.admin_kb import reply_button_kb
from keyboards.parent_kb import (
    back_to_menu,
    cancel_application,
    cancel_fsm,
    confirm_kb,
    faq_back_kb,
    faq_kb,
    gender_kb,
    kindergarten_kb,
    parent_main_menu,
    registration_same_kb,
    relation_kb,
    skip_email_kb,
    skip_snils_kb,
    skip_work_kb,
)
from states import ApplicationFSM, ContactFSM
from utils.texts import (
    ABOUT_SCHOOL,
    CONTACTS,
    CONTACT_PHONE,
    DOCUMENTS_LIST,
    FAQ_ANSWERS,
    PARENT_START,
    STATUS_EMOJI,
    STATUS_RU,
)
from utils.validators import (
    validate_birth_date_ddmmyyyy,
    validate_child_age_for_first_grade,
    validate_email,
    validate_full_name,
    validate_phone,
)

router = Router()
logger = logging.getLogger(__name__)

DOC_MAX_SIZE = 20 * 1024 * 1024


def _step_prefix(step: int) -> str:
    return f"Шаг {step} из 15. "


def _docs_count(data: dict[str, Any]) -> int:
    return sum(1 for k in ("docs_birth_certificate", "docs_parent_passport", "docs_snils", "docs_registration") if data.get(k))


async def _ensure_upload_dir(config: Config, application_id: int) -> Path:
    base = config.uploads_dir / str(application_id)
    base.mkdir(parents=True, exist_ok=True)
    return base


async def _download_media(message: Message, config: Config, application_id: int, file_key: str) -> str | None:
    if message.bot is None:
        return None
    file = None
    ext = "bin"

    if message.document:
        file = message.document
        if file.file_size and file.file_size > DOC_MAX_SIZE:
            await message.answer("Файл слишком большой. Максимум 20 МБ.")
            return None
        if file.file_name and "." in file.file_name:
            ext = file.file_name.rsplit(".", 1)[-1].lower()
    elif message.photo:
        file = message.photo[-1]
        if file.file_size and file.file_size > DOC_MAX_SIZE:
            await message.answer("Файл слишком большой. Максимум 20 МБ.")
            return None
        ext = "jpg"
    else:
        await message.answer("Прикрепите фото или документ (PDF/JPG/PNG).")
        return None

    app_dir = await _ensure_upload_dir(config, application_id)
    dest = app_dir / f"{file_key}.{ext}"
    await message.bot.download(file.file_id, destination=dest)  # type: ignore[arg-type]
    return str(dest)


@router.callback_query(F.data == "apply_start")
async def apply_start(callback: CallbackQuery, state: FSMContext, config: Config) -> None:
    if callback.from_user is None:
        return
    async with connect(str(config.db_path)) as db:
        application_id = await create_application_draft(db, callback.from_user.id)

    await state.set_state(ApplicationFSM.child_full_name)
    await state.update_data(application_id=application_id)
    await callback.message.edit_text(  # type: ignore[union-attr]
        _step_prefix(1) + "Введите ФИО ребёнка полностью (например: Иванов Иван Иванович):",
        reply_markup=cancel_application(),
    )
    await callback.answer()


@router.callback_query(F.data == "cancel_application")
async def cancel_flow(callback: CallbackQuery, state: FSMContext, config: Config) -> None:
    data = await state.get_data()
    app_id = data.get("application_id")
    await state.clear()
    if app_id:
        try:
            async with connect(str(config.db_path)) as db:
                await delete_application(db, int(app_id))
        except Exception:
            logger.exception("Failed to delete draft application %s", app_id)
    await callback.message.edit_text(PARENT_START, reply_markup=parent_main_menu())  # type: ignore[union-attr]
    await callback.answer("Отменено")


@router.message(ApplicationFSM.child_full_name)
async def step_child_full_name(message: Message, state: FSMContext) -> None:
    if not message.text:
        await message.answer("Введите текстом ФИО ребёнка.")
        return
    res = validate_full_name(message.text, min_words=2)
    if not res.ok:
        await message.answer(res.error or "Проверьте ввод.", reply_markup=cancel_application())
        return

    await state.update_data(child_full_name=res.value)
    await state.set_state(ApplicationFSM.child_birth_date)
    await message.answer(_step_prefix(2) + "Введите дату рождения ребёнка в формате ДД.ММ.ГГГГ:", reply_markup=cancel_application())


@router.message(ApplicationFSM.child_birth_date)
async def step_child_birth_date(message: Message, state: FSMContext) -> None:
    if not message.text:
        await message.answer("Введите дату рождения текстом.")
        return
    res = validate_birth_date_ddmmyyyy(message.text)
    if not res.ok:
        await message.answer(res.error or "Неверная дата.", reply_markup=cancel_application())
        return
    res2 = validate_child_age_for_first_grade(res.value or "")
    if not res2.ok:
        await message.answer(res2.error or "Возраст не подходит.", reply_markup=cancel_application())
        return

    await state.update_data(child_birth_date=res2.value)
    await state.set_state(ApplicationFSM.child_gender)
    await message.answer(_step_prefix(3) + "Выберите пол ребёнка:", reply_markup=gender_kb())


@router.callback_query(ApplicationFSM.child_gender, F.data.in_(["gender_male", "gender_female"]))
async def step_child_gender(callback: CallbackQuery, state: FSMContext) -> None:
    gender = "Мальчик" if callback.data == "gender_male" else "Девочка"
    await state.update_data(child_gender=gender)
    await state.set_state(ApplicationFSM.child_address)
    await callback.message.edit_text(_step_prefix(4) + "Введите адрес фактического проживания ребёнка:", reply_markup=cancel_application())  # type: ignore[union-attr]
    await callback.answer()


@router.message(ApplicationFSM.child_address)
async def step_child_address(message: Message, state: FSMContext) -> None:
    if not message.text or len(message.text.strip()) < 5:
        await message.answer("Введите адрес (минимум 5 символов).", reply_markup=cancel_application())
        return
    await state.update_data(child_address=message.text.strip())
    await state.set_state(ApplicationFSM.child_registration_address)
    await message.answer(
        _step_prefix(5) + "Введите адрес регистрации ребёнка или нажмите кнопку:",
        reply_markup=registration_same_kb(),
    )


@router.callback_query(ApplicationFSM.child_registration_address, F.data == "reg_same")
async def step_child_reg_same(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    await state.update_data(child_registration_address=data.get("child_address", ""))
    await state.set_state(ApplicationFSM.kindergarten)
    await callback.message.edit_text(  # type: ignore[union-attr]
        _step_prefix(6) + "Из какого детского сада переходит ребёнок? Введите название или нажмите кнопку:",
        reply_markup=kindergarten_kb(),
    )
    await callback.answer()


@router.message(ApplicationFSM.child_registration_address)
async def step_child_registration_address(message: Message, state: FSMContext) -> None:
    if not message.text or len(message.text.strip()) < 5:
        await message.answer("Введите адрес регистрации (минимум 5 символов).", reply_markup=registration_same_kb())
        return
    await state.update_data(child_registration_address=message.text.strip())
    await state.set_state(ApplicationFSM.kindergarten)
    await message.answer(
        _step_prefix(6) + "Из какого детского сада переходит ребёнок? Введите название или нажмите кнопку:",
        reply_markup=kindergarten_kb(),
    )


@router.callback_query(ApplicationFSM.kindergarten, F.data == "kindergarten_none")
async def step_kindergarten_none(callback: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(kindergarten=None)
    await state.set_state(ApplicationFSM.parent_full_name)
    await callback.message.edit_text(_step_prefix(7) + "Введите ФИО родителя/законного представителя:", reply_markup=cancel_application())  # type: ignore[union-attr]
    await callback.answer()


@router.message(ApplicationFSM.kindergarten)
async def step_kindergarten(message: Message, state: FSMContext) -> None:
    if not message.text:
        await message.answer("Введите название детского сада или нажмите «Не посещал».", reply_markup=kindergarten_kb())
        return
    await state.update_data(kindergarten=message.text.strip())
    await state.set_state(ApplicationFSM.parent_full_name)
    await message.answer(_step_prefix(7) + "Введите ФИО родителя/законного представителя:", reply_markup=cancel_application())


@router.message(ApplicationFSM.parent_full_name)
async def step_parent_full_name(message: Message, state: FSMContext) -> None:
    if not message.text:
        await message.answer("Введите ФИО текстом.", reply_markup=cancel_application())
        return
    res = validate_full_name(message.text, min_words=2)
    if not res.ok:
        await message.answer(res.error or "Проверьте ввод.", reply_markup=cancel_application())
        return
    await state.update_data(parent_full_name=res.value)
    await state.set_state(ApplicationFSM.parent_relation)
    await message.answer(_step_prefix(8) + "Кем вы приходитесь ребёнку?", reply_markup=relation_kb())


@router.callback_query(ApplicationFSM.parent_relation, F.data.in_(["relation_mother", "relation_father", "relation_guardian"]))
async def step_parent_relation(callback: CallbackQuery, state: FSMContext) -> None:
    mapping = {"relation_mother": "Мать", "relation_father": "Отец", "relation_guardian": "Опекун"}
    await state.update_data(parent_relation=mapping.get(callback.data, ""))
    await state.set_state(ApplicationFSM.parent_phone)
    await callback.message.edit_text(  # type: ignore[union-attr]
        _step_prefix(9) + "Введите ваш номер телефона в формате +7XXXXXXXXXX или 8XXXXXXXXXX:",
        reply_markup=cancel_application(),
    )
    await callback.answer()


@router.message(ApplicationFSM.parent_phone)
async def step_parent_phone(message: Message, state: FSMContext) -> None:
    if not message.text:
        await message.answer("Введите телефон текстом.", reply_markup=cancel_application())
        return
    res = validate_phone(message.text)
    if not res.ok:
        await message.answer(res.error or "Проверьте телефон.", reply_markup=cancel_application())
        return
    await state.update_data(parent_phone=res.value)
    await state.set_state(ApplicationFSM.parent_email)
    await message.answer(_step_prefix(10) + "Введите ваш email или пропустите:", reply_markup=skip_email_kb())


@router.callback_query(ApplicationFSM.parent_email, F.data == "skip_email")
async def step_parent_email_skip(callback: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(parent_email=None)
    await state.set_state(ApplicationFSM.parent_work)
    await callback.message.edit_text(_step_prefix(11) + "Укажите место работы (необязательно):", reply_markup=skip_work_kb())  # type: ignore[union-attr]
    await callback.answer()


@router.message(ApplicationFSM.parent_email)
async def step_parent_email(message: Message, state: FSMContext) -> None:
    if not message.text:
        await message.answer("Введите email текстом или нажмите «Пропустить».", reply_markup=skip_email_kb())
        return
    res = validate_email(message.text)
    if not res.ok:
        await message.answer(res.error or "Проверьте email.", reply_markup=skip_email_kb())
        return
    await state.update_data(parent_email=res.value or None)
    await state.set_state(ApplicationFSM.parent_work)
    await message.answer(_step_prefix(11) + "Укажите место работы (необязательно):", reply_markup=skip_work_kb())


@router.callback_query(ApplicationFSM.parent_work, F.data == "skip_work")
async def step_parent_work_skip(callback: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(parent_work=None)
    await state.set_state(ApplicationFSM.docs_birth_certificate)
    await callback.message.edit_text(_step_prefix(12) + "Прикрепите фото свидетельства о рождении ребёнка:", reply_markup=cancel_application())  # type: ignore[union-attr]
    await callback.answer()


@router.message(ApplicationFSM.parent_work)
async def step_parent_work(message: Message, state: FSMContext) -> None:
    if not message.text:
        await message.answer("Введите место работы текстом или нажмите «Пропустить».", reply_markup=skip_work_kb())
        return
    await state.update_data(parent_work=message.text.strip() or None)
    await state.set_state(ApplicationFSM.docs_birth_certificate)
    await message.answer(_step_prefix(12) + "Прикрепите фото свидетельства о рождении ребёнка:", reply_markup=cancel_application())


@router.message(ApplicationFSM.docs_birth_certificate)
async def step_docs_birth(message: Message, state: FSMContext, config: Config) -> None:
    data = await state.get_data()
    app_id = int(data["application_id"])
    path = await _download_media(message, config, app_id, "birth_certificate")
    if not path:
        return
    await state.update_data(docs_birth_certificate=path)
    await state.set_state(ApplicationFSM.docs_parent_passport)
    await message.answer(_step_prefix(13) + "Прикрепите фото главной страницы паспорта родителя:", reply_markup=cancel_application())


@router.message(ApplicationFSM.docs_parent_passport)
async def step_docs_passport(message: Message, state: FSMContext, config: Config) -> None:
    data = await state.get_data()
    app_id = int(data["application_id"])
    path = await _download_media(message, config, app_id, "parent_passport")
    if not path:
        return
    await state.update_data(docs_parent_passport=path)
    await state.set_state(ApplicationFSM.docs_snils)
    await message.answer(_step_prefix(14) + "Прикрепите фото СНИЛС ребёнка (необязательно):", reply_markup=skip_snils_kb())


@router.callback_query(ApplicationFSM.docs_snils, F.data == "skip_snils")
async def step_docs_snils_skip(callback: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(docs_snils=None)
    await state.set_state(ApplicationFSM.docs_registration)
    await callback.message.edit_text(_step_prefix(15) + "Прикрепите документ о регистрации ребёнка:", reply_markup=cancel_application())  # type: ignore[union-attr]
    await callback.answer()


@router.message(ApplicationFSM.docs_snils)
async def step_docs_snils(message: Message, state: FSMContext, config: Config) -> None:
    data = await state.get_data()
    app_id = int(data["application_id"])
    path = await _download_media(message, config, app_id, "snils")
    if not path:
        return
    await state.update_data(docs_snils=path)
    await state.set_state(ApplicationFSM.docs_registration)
    await message.answer(_step_prefix(15) + "Прикрепите документ о регистрации ребёнка:", reply_markup=cancel_application())


@router.message(ApplicationFSM.docs_registration)
async def step_docs_registration(message: Message, state: FSMContext, config: Config) -> None:
    data = await state.get_data()
    app_id = int(data["application_id"])
    path = await _download_media(message, config, app_id, "registration")
    if not path:
        return
    await state.update_data(docs_registration=path)
    await state.set_state(ApplicationFSM.confirm)

    data = await state.get_data()
    text = (
        " Проверьте данные заявки:\n\n"
        " РЕБЁНОК:\n"
        f"ФИО: {data.get('child_full_name')}\n"
        f"Дата рождения: {data.get('child_birth_date')}\n"
        f"Пол: {data.get('child_gender')}\n"
        f"Адрес проживания: {data.get('child_address')}\n"
        f"Адрес регистрации: {data.get('child_registration_address')}\n"
        f"Детский сад: {data.get('kindergarten') or '—'}\n\n"
        " РОДИТЕЛЬ:\n"
        f"ФИО: {data.get('parent_full_name')}\n"
        f"Степень родства: {data.get('parent_relation')}\n"
        f"Телефон: {data.get('parent_phone')}\n"
        f"Email: {data.get('parent_email') or '—'}\n"
        f"Место работы: {data.get('parent_work') or '—'}\n\n"
        f" Документов прикреплено: {_docs_count(data)}\n\n"
        "Класс: 1 класс"
    )
    await message.answer(text, reply_markup=confirm_kb())


@router.callback_query(ApplicationFSM.confirm, F.data == "confirm_application")
async def confirm_application(callback: CallbackQuery, state: FSMContext, config: Config) -> None:
    if callback.from_user is None or callback.message is None:
        return
    data = await state.get_data()
    app_id = int(data["application_id"])

    async with connect(str(config.db_path)) as db:
        await finalize_application(db, app_id, data)

    await state.clear()

    notify_text = (
        f" Новая заявка #{app_id}\n"
        f"Ребёнок: {data.get('child_full_name')}\n"
        f"Родитель: {data.get('parent_full_name')}\n"
        f"Телефон: {data.get('parent_phone')}"
    )
    from aiogram.utils.keyboard import InlineKeyboardBuilder

    kb = InlineKeyboardBuilder()
    kb.button(text=" Открыть заявку", callback_data=f"view_app_{app_id}")
    kb.adjust(1)
    for admin_id in config.admin_ids:
        try:
            await callback.bot.send_message(admin_id, notify_text, reply_markup=kb.as_markup())
        except Exception:
            logger.exception("Failed to notify admin %s", admin_id)

    await callback.message.edit_text(
        f"✅ Заявка #{app_id} принята!\n\n"
        f"С вами свяжется завуч Диана Казбековна по телефону {CONTACT_PHONE} в течение 3-5 рабочих дней.\n\n"
        "Отслеживать статус можно в разделе \" Мои заявки\".",
        reply_markup=parent_main_menu(),
    )
    await callback.answer()


@router.callback_query(F.data == "my_applications")
async def my_applications(callback: CallbackQuery, config: Config) -> None:
    if callback.from_user is None or callback.message is None:
        return
    async with connect(str(config.db_path)) as db:
        rows = await get_user_applications(db, callback.from_user.id)

    if not rows:
        await callback.message.edit_text("У вас пока нет заявок.", reply_markup=back_to_menu())
        await callback.answer()
        return

    from aiogram.utils.keyboard import InlineKeyboardBuilder

    kb = InlineKeyboardBuilder()
    for r in rows:
        emoji = STATUS_EMOJI.get(r["status"], "🟡")
        kb.button(text=f"{emoji} {r['child_full_name']} (#{r['id']})", callback_data=f"my_app_{r['id']}")
    kb.button(text="⬅️ Назад в меню", callback_data="main_menu")
    kb.adjust(1)

    await callback.message.edit_text("Ваши заявки:", reply_markup=kb.as_markup())
    await callback.answer()


@router.callback_query(F.data.startswith("my_app_"))
async def my_application_detail(callback: CallbackQuery, config: Config) -> None:
    if callback.message is None:
        return
    app_id = int(callback.data.split("_", 2)[-1])
    async with connect(str(config.db_path)) as db:
        row = await get_application_by_id(db, app_id)
    if not row:
        await callback.answer("Заявка не найдена")
        return

    status = row["status"]
    text = (
        f" Заявка #{row['id']}\n"
        f"Статус: {STATUS_EMOJI.get(status, '🟡')} {STATUS_RU.get(status, status)}\n\n"
        f"Ребёнок: {row['child_full_name']}\n"
        f"Дата рождения: {row['child_birth_date']}\n"
        f"Родитель: {row['parent_full_name']}\n"
        f"Телефон: {row['parent_phone']}\n\n"
        f"Комментарий комиссии: {row['admin_comment'] or '—'}"
    )
    await callback.message.edit_text(text, reply_markup=back_to_menu())
    await callback.answer()


@router.callback_query(F.data == "documents_list")
async def documents_list(callback: CallbackQuery) -> None:
    await callback.message.edit_text(DOCUMENTS_LIST, reply_markup=back_to_menu())  # type: ignore[union-attr]
    await callback.answer()


@router.callback_query(F.data == "about_school")
async def about_school(callback: CallbackQuery) -> None:
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from utils.texts import SCHOOL_SITE

    kb = InlineKeyboardBuilder()
    kb.button(text=" Перейти на сайт школы", url=SCHOOL_SITE)
    kb.button(text="⬅️ Назад в меню", callback_data="main_menu")
    kb.adjust(1)
    await callback.message.edit_text(ABOUT_SCHOOL, reply_markup=kb.as_markup())  # type: ignore[union-attr]
    await callback.answer()


@router.callback_query(F.data == "contacts")
async def contacts(callback: CallbackQuery) -> None:
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from utils.texts import CONTACT_PHONE_TEL, SCHOOL_SITE

    kb = InlineKeyboardBuilder()
    kb.button(text=" Позвонить", url=CONTACT_PHONE_TEL)
    kb.button(text=" Сайт школы", url=SCHOOL_SITE)
    kb.button(text="⬅️ Назад в меню", callback_data="main_menu")
    kb.adjust(1)
    await callback.message.edit_text(CONTACTS, reply_markup=kb.as_markup())  # type: ignore[union-attr]
    await callback.answer()


@router.callback_query(F.data == "faq")
async def faq(callback: CallbackQuery) -> None:
    await callback.message.edit_text("❓ FAQ\nВыберите вопрос:", reply_markup=faq_kb())  # type: ignore[union-attr]
    await callback.answer()


@router.callback_query(F.data.startswith("faq_"))
async def faq_answer(callback: CallbackQuery) -> None:
    idx = int(callback.data.split("_", 1)[-1])
    answer = FAQ_ANSWERS.get(idx, "Ответ не найден.")
    await callback.message.edit_text(answer, reply_markup=faq_back_kb())  # type: ignore[union-attr]
    await callback.answer()


@router.callback_query(F.data == "contact_admin")
async def contact_admin_start(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(ContactFSM.parent_message)
    await callback.message.edit_text(  # type: ignore[union-attr]
        "Напишите ваш вопрос — мы перешлём его в приёмную комиссию:",
        reply_markup=cancel_fsm(),
    )
    await callback.answer()


@router.message(ContactFSM.parent_message)
async def contact_admin_message(message: Message, state: FSMContext, config: Config) -> None:
    if message.from_user is None or message.text is None:
        await message.answer("Пожалуйста, отправьте текст сообщения.")
        return

    async with connect(str(config.db_path)) as db:
        await create_message(db, message.from_user.id, message.from_user.username, message.text, is_from_admin=0)

    parent_name = message.from_user.full_name
    username = f"@{message.from_user.username}" if message.from_user.username else "—"
    text = (
        f" Сообщение от {parent_name} ({username}, ID: {message.from_user.id}):\n\n"
        f"{message.text}"
    )
    for admin_id in config.admin_ids:
        try:
            await message.bot.send_message(admin_id, text, reply_markup=reply_button_kb(message.from_user.id))  # type: ignore[union-attr]
        except Exception:
            logger.exception("Failed to forward message to admin %s", admin_id)

    await state.clear()
    await message.answer("✅ Ваше сообщение отправлено в приёмную комиссию.", reply_markup=parent_main_menu())
