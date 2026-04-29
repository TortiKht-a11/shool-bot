"""SQLite connection and schema initialization."""

from __future__ import annotations

import aiosqlite


APPLICATIONS_SCHEMA = """
CREATE TABLE IF NOT EXISTS applications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    child_full_name TEXT NOT NULL,
    child_birth_date TEXT NOT NULL,
    child_gender TEXT NOT NULL,
    child_address TEXT NOT NULL,
    child_registration_address TEXT NOT NULL,
    kindergarten TEXT,
    parent_full_name TEXT NOT NULL,
    parent_relation TEXT NOT NULL,
    parent_phone TEXT NOT NULL,
    parent_email TEXT,
    parent_work TEXT,
    docs_birth_certificate TEXT,
    docs_parent_passport TEXT,
    docs_snils TEXT,
    docs_registration TEXT,
    status TEXT DEFAULT 'pending',
    admin_comment TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

MESSAGES_SCHEMA = """
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    user_name TEXT,
    text TEXT NOT NULL,
    is_from_admin INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

USERS_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    full_name TEXT,
    first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

TRIGGERS = """
CREATE TRIGGER IF NOT EXISTS trg_applications_updated_at
AFTER UPDATE ON applications
FOR EACH ROW
BEGIN
    UPDATE applications SET updated_at = CURRENT_TIMESTAMP WHERE id = OLD.id;
END;
"""


async def init_db(db_path: str) -> None:
    async with aiosqlite.connect(db_path) as db:
        await db.execute("PRAGMA journal_mode=WAL;")
        await db.execute("PRAGMA foreign_keys=ON;")
        await db.execute(APPLICATIONS_SCHEMA)
        await db.execute(MESSAGES_SCHEMA)
        await db.execute(USERS_SCHEMA)
        await db.execute(TRIGGERS)
        await db.commit()


def connect(db_path: str) -> aiosqlite.Connection:
    return aiosqlite.connect(db_path)
