"""Клавиатуры: reply-меню менеджера, inline-списки заявок, карточка заявки."""
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

PAGE_SIZE = 5


# ---------------------------------------------------------------------------
# Reply-клавиатура (постоянная внизу экрана)
# ---------------------------------------------------------------------------
def manager_reply_kb() -> ReplyKeyboardMarkup:
    """Постоянные кнопки внизу для менеджера."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="📋 Заявки"),
                KeyboardButton(text="💬 Неотвеченные"),
            ],
            [
                KeyboardButton(text="👥 Ученики"),
                KeyboardButton(text="❓ Помощь"),
            ],
        ],
        resize_keyboard=True,
    )


# ---------------------------------------------------------------------------
# Inline-клавиатуры
# ---------------------------------------------------------------------------
def chat_message_kb(chat_user_id: int) -> InlineKeyboardMarkup:
    """Кнопка «✍️ Ответить» на пересланном сообщении клиента."""
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            text="✍️ Ответить",
            callback_data=f"reply:{chat_user_id}:0",
        )
    ]])


def manager_menu_kb(new_count: int = 0, chat_count: int = 0) -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=f"🆕 Необработанные ({new_count})",
            callback_data="leads:new:0",
        )],
        [InlineKeyboardButton(
            text="✅ Обработанные",
            callback_data="leads:done:0",
        )],
        [InlineKeyboardButton(
            text=f"💬 Чат с клиентами ({chat_count})",
            callback_data="leads:chat:0",
        )],
    ])
    return kb


def leads_list_kb(
    leads: list[dict],
    filter_: str,
    page: int,
    total: int,
) -> InlineKeyboardMarkup:
    """Кнопки по одной на заявку; пагинация внизу."""
    rows = []
    for lead in leads:
        status_mark = "✅" if lead["status"] == "done" else "🆕"
        name = (lead["name"] or "—")[:20]
        rows.append([InlineKeyboardButton(
            text=f"{status_mark} #{lead['id']} {name}",
            callback_data=f"lead:{lead['id']}:0",
        )])
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(
            text="← Назад",
            callback_data=f"leads:{filter_}:{page - 1}",
        ))
    if (page + 1) * PAGE_SIZE < total:
        nav.append(InlineKeyboardButton(
            text="Ещё →",
            callback_data=f"leads:{filter_}:{page + 1}",
        ))
    if nav:
        rows.append(nav)
    rows.append([InlineKeyboardButton(
        text="🏠 В меню",
        callback_data="menu:0",
    )])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def lead_card_kb(lead_id: int, status: str, source: str) -> InlineKeyboardMarkup:
    """Карточка заявки: обработка + (для чата) ответ клиенту."""
    rows = []
    if source == "chat":
        rows.append([InlineKeyboardButton(
            text="✍️ Ответить",
            callback_data=f"reply:{lead_id}:chat",
        )])
    if status == "done":
        rows.append([InlineKeyboardButton(
            text="↩️ Вернуть в работу",
            callback_data=f"lead:reopen:{lead_id}:0",
        )])
    else:
        rows.append([InlineKeyboardButton(
            text="✅ Обработана",
            callback_data=f"lead:done:{lead_id}:0",
        )])
    rows.append([InlineKeyboardButton(
        text="← Назад к списку",
        callback_data="lead:back:0",
    )])
    return InlineKeyboardMarkup(inline_keyboard=rows)
