"""SQLite-хранилище: заявки с сайта и их статусы обработки.

Заявка (lead): name, phone, who (ученик/родитель), subject, source
(web — с сайта, chat — из переписки в боте), status: new|done,
и id сообщения в чате менеджера, чтобы помечать «✅ обработано».
"""
import sqlite3
from datetime import datetime, timedelta

DB_PATH = "manage_bot.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS leads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    phone TEXT NOT NULL,
    who TEXT NOT NULL DEFAULT '',
    subject TEXT NOT NULL DEFAULT '',
    source TEXT NOT NULL DEFAULT 'web',
    status TEXT NOT NULL DEFAULT 'new',
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS manager_msgs (
    lead_id INTEGER PRIMARY KEY,
    message_id INTEGER NOT NULL,
    chat_id INTEGER NOT NULL,
    FOREIGN KEY (lead_id) REFERENCES leads(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS ix_leads_status ON leads(status);
CREATE TABLE IF NOT EXISTS client_threads (
    user_id INTEGER PRIMARY KEY,
    thread_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with _connect() as conn:
        conn.executescript(_SCHEMA)


def _now() -> str:
    # +3 Минск, без TZ-библиотек: utc+3
    return (datetime.utcnow() + timedelta(hours=3)).strftime("%d.%m.%Y %H:%M")


def create_lead(name: str, phone: str, who: str, subject: str, source: str) -> int:
    with _connect() as conn:
        cur = conn.execute(
            "INSERT INTO leads (name, phone, who, subject, source, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (name, phone, who, subject, source, _now()),
        )
        return int(cur.lastrowid)


def get_lead(lead_id: int) -> sqlite3.Row | None:
    with _connect() as conn:
        return conn.execute("SELECT * FROM leads WHERE id = ?", (lead_id,)).fetchone()


def set_lead_status(lead_id: int, status: str) -> None:
    with _connect() as conn:
        conn.execute(
            "UPDATE leads SET status = ? WHERE id = ?", (status, lead_id)
        )


def set_manager_msg(lead_id: int, message_id: int, chat_id: int) -> None:
    with _connect() as conn:
        conn.execute(
            "INSERT INTO manager_msgs (lead_id, message_id, chat_id)"
            " VALUES (?, ?, ?) ON CONFLICT(lead_id) DO UPDATE SET"
            " message_id = excluded.message_id, chat_id = excluded.chat_id",
            (lead_id, message_id, chat_id),
        )


def get_manager_msg(lead_id: int) -> sqlite3.Row | None:
    with _connect() as conn:
        return conn.execute(
            "SELECT * FROM manager_msgs WHERE lead_id = ?", (lead_id,)
        ).fetchone()


def list_leads(
    limit: int = 30,
    status: str | None = None,
    source: str | None = None,
) -> list[dict]:
    """Заявки (новые первыми); status/source — фильтры."""
    sql = "SELECT id, name, phone, who, subject, source, status, created_at FROM leads"
    conds, params = [], []
    if status is not None:
        conds.append("status = ?")
        params.append(status)
    if source is not None:
        conds.append("source = ?")
        params.append(source)
    if conds:
        sql += " WHERE " + " AND ".join(conds)
    sql += " ORDER BY id DESC LIMIT ?"
    params.append(limit)
    with _connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


def count_leads(status: str | None = None, source: str | None = None) -> int:
    """Число заявок (по статусу/source), для счётчиков в меню."""
    conds, params = [], []
    if status is not None:
        conds.append("status = ?")
        params.append(status)
    if source is not None:
        conds.append("source = ?")
        params.append(source)
    sql = "SELECT COUNT(*) FROM leads"
    if conds:
        sql += " WHERE " + " AND ".join(conds)
    with _connect() as conn:
        return int(conn.execute(sql, tuple(params)).fetchone()[0])


# ---------------------------------------------------------------------------
# Топики форум-группы: один клиент = одна тема (переписка целиком)
# ---------------------------------------------------------------------------
def get_thread(user_id: int) -> sqlite3.Row | None:
    with _connect() as conn:
        return conn.execute(
            "SELECT * FROM client_threads WHERE user_id = ?", (user_id,)
        ).fetchone()


def set_thread(user_id: int, thread_id: int, name: str) -> None:
    with _connect() as conn:
        conn.execute(
            "INSERT INTO client_threads (user_id, thread_id, name, created_at)"
            " VALUES (?, ?, ?, ?) ON CONFLICT(user_id) DO UPDATE SET"
            " thread_id = excluded.thread_id, name = excluded.name",
            (user_id, thread_id, name, _now()),
        )


def list_threads() -> list[dict]:
    """Все топики клиентов (для поиска темы по thread_id)."""
    with _connect() as conn:
        rows = conn.execute(
            "SELECT user_id, thread_id, name FROM client_threads"
        ).fetchall()
    return [dict(r) for r in rows]


def get_chat_lead(user_id: int) -> sqlite3.Row | None:
    """Заявка-диалог клиента (source=chat, phone = tg id)."""
    with _connect() as conn:
        return conn.execute(
            "SELECT * FROM leads WHERE source = 'chat' AND phone = ?"
            " ORDER BY id DESC LIMIT 1",
            (str(user_id),),
        ).fetchone()


def count_chat_clients() -> int:
    """Число клиентов, писавших боту (диалоги в темах)."""
    with _connect() as conn:
        return int(
            conn.execute(
                "SELECT COUNT(DISTINCT phone) FROM leads WHERE source = 'chat'"
            ).fetchone()[0]
        )
