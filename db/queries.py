"""CRUD queries for the bot."""

from __future__ import annotations

from datetime import datetime

import aiosqlite


async def upsert_user(db: aiosqlite.Connection, user_id: int, username: str | None, full_name: str | None) -> None:
    await db.execute(
        """
        INSERT INTO users (user_id, username, full_name)
        VALUES (?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            username=excluded.username,
            full_name=excluded.full_name
        """,
        (user_id, username, full_name),
    )
    await db.commit()


async def create_application_draft(db: aiosqlite.Connection, user_id: int) -> int:
    cur = await db.execute(
        """
        INSERT INTO applications (
            user_id,
            child_full_name,
            child_birth_date,
            child_gender,
            child_address,
            child_registration_address,
            kindergarten,
            parent_full_name,
            parent_relation,
            parent_phone,
            parent_email,
            parent_work,
            docs_birth_certificate,
            docs_parent_passport,
            docs_snils,
            docs_registration,
            status,
            admin_comment
        ) VALUES (
            ?, '', '', '', '', '', NULL, '', '', '', NULL, NULL, NULL, NULL, NULL, NULL, 'draft', NULL
        )
        """,
        (user_id,),
    )
    await db.commit()
    return int(cur.lastrowid)


async def finalize_application(
    db: aiosqlite.Connection,
    application_id: int,
    data: dict,
) -> None:
    await db.execute(
        """
        UPDATE applications SET
            child_full_name=?,
            child_birth_date=?,
            child_gender=?,
            child_address=?,
            child_registration_address=?,
            kindergarten=?,
            parent_full_name=?,
            parent_relation=?,
            parent_phone=?,
            parent_email=?,
            parent_work=?,
            docs_birth_certificate=?,
            docs_parent_passport=?,
            docs_snils=?,
            docs_registration=?,
            status='pending'
        WHERE id=?
        """,
        (
            data["child_full_name"],
            data["child_birth_date"],
            data["child_gender"],
            data["child_address"],
            data["child_registration_address"],
            data.get("kindergarten"),
            data["parent_full_name"],
            data["parent_relation"],
            data["parent_phone"],
            data.get("parent_email"),
            data.get("parent_work"),
            data.get("docs_birth_certificate"),
            data.get("docs_parent_passport"),
            data.get("docs_snils"),
            data.get("docs_registration"),
            application_id,
        ),
    )
    await db.commit()


async def delete_application(db: aiosqlite.Connection, application_id: int) -> None:
    await db.execute("DELETE FROM applications WHERE id=?", (application_id,))
    await db.commit()


async def get_user_applications(db: aiosqlite.Connection, user_id: int) -> list[aiosqlite.Row]:
    db.row_factory = aiosqlite.Row
    cur = await db.execute(
        """
        SELECT * FROM applications
        WHERE user_id=? AND status != 'draft'
        ORDER BY created_at DESC
        """,
        (user_id,),
    )
    return list(await cur.fetchall())


async def get_application_by_id(db: aiosqlite.Connection, application_id: int) -> aiosqlite.Row | None:
    db.row_factory = aiosqlite.Row
    cur = await db.execute("SELECT * FROM applications WHERE id=?", (application_id,))
    return await cur.fetchone()


async def update_application_status(db: aiosqlite.Connection, application_id: int, status: str, admin_comment: str | None) -> None:
    await db.execute(
        "UPDATE applications SET status=?, admin_comment=? WHERE id=?",
        (status, admin_comment, application_id),
    )
    await db.commit()


async def update_admin_comment(db: aiosqlite.Connection, application_id: int, admin_comment: str) -> None:
    await db.execute("UPDATE applications SET admin_comment=? WHERE id=?", (admin_comment, application_id))
    await db.commit()


async def list_applications(
    db: aiosqlite.Connection,
    status: str | None,
    limit: int,
    offset: int,
) -> tuple[list[aiosqlite.Row], int]:
    db.row_factory = aiosqlite.Row

    where_sql = ""
    params: list = []
    if status is not None:
        where_sql = "WHERE status=?"
        params.append(status)
    else:
        where_sql = "WHERE status != 'draft'"

    cur_total = await db.execute(f"SELECT COUNT(*) AS cnt FROM applications {where_sql}", params)
    total = int((await cur_total.fetchone())[0])

    cur = await db.execute(
        f"""
        SELECT * FROM applications
        {where_sql}
        ORDER BY created_at DESC
        LIMIT ? OFFSET ?
        """,
        (*params, limit, offset),
    )
    return list(await cur.fetchall()), total


async def search_applications(db: aiosqlite.Connection, query: str, limit: int = 50) -> list[aiosqlite.Row]:
    db.row_factory = aiosqlite.Row
    q = query.strip()
    if not q:
        return []
    like = f"%{q}%"

    if q.isdigit():
        cur = await db.execute(
            """
            SELECT * FROM applications
            WHERE status != 'draft' AND (
                id=? OR child_full_name LIKE ? OR parent_phone LIKE ? OR parent_full_name LIKE ?
            )
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (int(q), like, like, like, limit),
        )
    else:
        cur = await db.execute(
            """
            SELECT * FROM applications
            WHERE status != 'draft' AND (
                child_full_name LIKE ? OR parent_phone LIKE ? OR parent_full_name LIKE ?
            )
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (like, like, like, limit),
        )
    return list(await cur.fetchall())


async def stats(db: aiosqlite.Connection) -> dict[str, int]:
    db.row_factory = aiosqlite.Row
    cur = await db.execute(
        """
        SELECT
            COUNT(*) AS total,
            SUM(CASE WHEN status='pending' THEN 1 ELSE 0 END) AS pending,
            SUM(CASE WHEN status='approved' THEN 1 ELSE 0 END) AS approved,
            SUM(CASE WHEN status='rejected' THEN 1 ELSE 0 END) AS rejected,
            SUM(CASE WHEN status='docs_required' THEN 1 ELSE 0 END) AS docs_required,
            SUM(CASE WHEN date(created_at, 'localtime') = date('now', 'localtime') THEN 1 ELSE 0 END) AS today,
            SUM(CASE WHEN created_at >= datetime('now', 'localtime', '-7 day') THEN 1 ELSE 0 END) AS week,
            SUM(CASE WHEN created_at >= datetime('now', 'localtime', '-30 day') THEN 1 ELSE 0 END) AS month,
            SUM(CASE WHEN child_gender='Мальчик' THEN 1 ELSE 0 END) AS male,
            SUM(CASE WHEN child_gender='Девочка' THEN 1 ELSE 0 END) AS female
        FROM applications
        WHERE status != 'draft'
        """
    )
    r = await cur.fetchone()
    if r is None:
        return {k: 0 for k in ["total", "pending", "approved", "rejected", "docs_required", "today", "week", "month", "male", "female"]}
    return {k: int(r[k] or 0) for k in r.keys()}


async def create_message(db: aiosqlite.Connection, user_id: int, user_name: str | None, text: str, is_from_admin: int) -> None:
    await db.execute(
        "INSERT INTO messages (user_id, user_name, text, is_from_admin) VALUES (?, ?, ?, ?)",
        (user_id, user_name, text, is_from_admin),
    )
    await db.commit()


async def list_all_user_ids(db: aiosqlite.Connection) -> list[int]:
    cur = await db.execute("SELECT user_id FROM users")
    return [int(r[0]) for r in await cur.fetchall()]
