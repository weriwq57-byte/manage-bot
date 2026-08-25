"""Реестр учеников из основной БД LevelUp (Postgres, read-only).

Команда /roster менеджера показывает «кто, на каком предмете, до какого
числа» и отдаёт CSV-файл. Соединение — отдельный URL из .env
(LEVELUP_DATABASE_URL), чтобы не конфликтовать с SQLite manage_bot.
"""
import csv
import io

import psycopg2

from .config import LEVELUP_DATABASE_URL

_QUERY = """
SELECT
    u.tg_full_name AS name,
    u.is_active AS user_active,
    s.access_until,
    sub.name AS subject
FROM students s
JOIN users u ON u.id = s.user_id
LEFT JOIN student_subjects ss
    ON ss.student_id = s.id AND ss.is_active = true
LEFT JOIN subjects sub ON sub.id = ss.subject_id AND sub.is_active = true
WHERE s.access_until IS NOT NULL
ORDER BY s.access_until ASC, u.tg_full_name ASC
"""


def fetch_roster() -> list[dict]:
    """Строки: {name, active, access_until, subject}. Пусто, если БД нет."""
    if not LEVELUP_DATABASE_URL:
        return []
    try:
        with psycopg2.connect(LEVELUP_DATABASE_URL, connect_timeout=5) as conn:
            with conn.cursor() as cur:
                cur.execute(_QUERY)
                cols = [d[0] for d in cur.description]
                rows = [dict(zip(cols, row)) for row in cur.fetchall()]
    except Exception:
        return []
    return rows


def roster_csv(rows: list[dict]) -> bytes:
    """CSV: Ученик;Предмет;До какого числа;Статус (; — для Excel/Нумерики)."""
    out = io.StringIO()
    writer = csv.writer(out, delimiter=";")
    writer.writerow(["Ученик", "Предмет", "До какого числа", "Статус"])
    for r in rows:
        writer.writerow([
            r["name"] or "—",
            r["subject"] or "—",
            r["access_until"],
            "активен" if r["user_active"] else "деактивирован",
        ])
    return out.getvalue().encode("utf-8-sig")


def roster_text(rows: list[dict]) -> str:
    """Человекочитаемый список для чата (не длиннее 4000 знаков)."""
    lines = ["📋 Ученики (до какого числа):", ""]
    for r in rows:
        marker = "✅" if r["user_active"] else "⛔"
        lines.append(
            f"{marker} {r['name'] or '—'} · {r['subject'] or '—'} · "
            f"до {r['access_until']}"
        )
    return "\n".join(lines)