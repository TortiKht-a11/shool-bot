"""Common handlers: /start, /cancel, routing helpers."""

from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from config import Config
from db import connect
from db.queries import upsert_user
from keyboards.parent_kb import parent_main_menu
from utils.texts import CANCELLED, PARENT_START

router = Router()
logger = logging.getLogger(__name__)


def is_admin(user_id: int, config: Config) -> bool:
    return user_id in config.admin_ids


@router.message(Command("start"))
async def cmd_start(message: Message, config: Config) -> None:
    if message.from_user is None:
        return
    async with connect(str(config.db_path)) as db:
        await upsert_user(
            db,
            user_id=message.from_user.id,
            username=message.from_user.username,
            full_name=message.from_user.full_name,
        )
    await message.answer(PARENT_START, reply_markup=parent_main_menu())


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(CANCELLED, reply_markup=parent_main_menu())


@router.callback_query(F.data == "main_menu")
async def cb_main_menu(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_text(PARENT_START, reply_markup=parent_main_menu())  # type: ignore[union-attr]
    await callback.answer()

@router.callback_query(F.data == "cancel_fsm")
async def cb_cancel_fsm(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_text(PARENT_START, reply_markup=parent_main_menu())  # type: ignore[union-attr]
    await callback.answer("Отменено")


@router.callback_query(F.data == "noop")
async def cb_noop(callback: CallbackQuery) -> None:
    await callback.answer()
