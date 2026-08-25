"""Настройки manage_bot из переменных окружения/файла .env."""
import os

from dotenv import load_dotenv

load_dotenv()


def _required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Не задано {name} в .env")
    return value


BOT_TOKEN: str = _required("BOT_TOKEN")
MANAGER_TG_ID: int = int(_required("MANAGER_TG_ID"))
WEB_PORT: int = int(os.getenv("WEB_PORT", "8081"))
WEB_API_KEY: str = os.getenv("WEB_API_KEY", "")
# Read-only доступ к БД основного бота LevelUp (Postgres) для /roster.
# Пример: postgresql://weriwq@localhost:5432/levelup_bot_test
LEVELUP_DATABASE_URL: str = os.getenv("LEVELUP_DATABASE_URL", "")
# Супергруппа с темами (форум), куда бот ведёт переписку с клиентами.
# Если не задана — клиентские сообщения уходят в личный чат менеджера.
MANAGER_GROUP_ID: int | None = (
    int(v) if (v := os.getenv("MANAGER_GROUP_ID", "").strip()) else None
)