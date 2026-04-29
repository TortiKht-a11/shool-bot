"""Project configuration: loads .env and provides constants."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR / ".env"


def _parse_admin_ids(raw: str) -> set[int]:
    items = [x.strip() for x in raw.split(",") if x.strip()]
    result: set[int] = set()
    for item in items:
        if not item.isdigit():
            raise ValueError(f"ADMIN_IDS contains non-numeric value: {item!r}")
        result.add(int(item))
    return result


@dataclass(frozen=True, slots=True)
class Config:
    bot_token: str
    admin_ids: set[int]
    log_chat_id: int | None
    db_path: Path
    uploads_dir: Path


def load_config() -> Config:
    load_dotenv(ENV_PATH if ENV_PATH.exists() else None)

    bot_token = os.getenv("BOT_TOKEN", "").strip()
    if not bot_token:
        raise RuntimeError("BOT_TOKEN is not set. Create .env from .env.example and fill BOT_TOKEN.")

    raw_admin_ids = os.getenv("ADMIN_IDS", "").strip()
    if not raw_admin_ids:
        raise RuntimeError("ADMIN_IDS is not set. Provide at least one admin id in .env.")
    admin_ids = _parse_admin_ids(raw_admin_ids)

    raw_log_chat_id = os.getenv("LOG_CHAT_ID", "").strip()
    log_chat_id = int(raw_log_chat_id) if raw_log_chat_id else None

    db_path = BASE_DIR / "school.db"
    uploads_dir = BASE_DIR / "uploads"

    return Config(
        bot_token=bot_token,
        admin_ids=admin_ids,
        log_chat_id=log_chat_id,
        db_path=db_path,
        uploads_dir=uploads_dir,
    )
