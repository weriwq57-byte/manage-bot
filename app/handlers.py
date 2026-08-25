"""Обработчики: reply-меню менеджера, заявки, ответы, клиентский чат."""
import logging

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import BufferedInputFile, CallbackQuery, Message

from . import roster as roster_svc
from . import storage
from .config import MANAGER_GROUP_ID, MANAGER_TG_ID
from .keyboards import (
    PAGE_SIZE,
    chat_message_kb,
    lead_card_kb,
    leads_list_kb,
    manager_menu_kb,
    manager_reply_kb,
)

log = logging.getLogger("manage_bot.handlers")

router = Router()


class ReplyStates(StatesGroup):
    waiting_reply = State()


def _is_manager(user_id: int) -> bool:
    return user_id == MANAGER_TG_ID


def _lead_text(lead: dict) -> str:
    lines = [
        f"📨 Заявка #{lead['id']} · {lead['created_at']}",
        f"👤 {lead['name']}",
    ]
    if lead["source"] == "chat":
        lines.append(f"🆔 id {lead['phone']} (пишет в бот)")
    else:
        lines.append(f"📞 {lead['phone']}")
    if lead["who"]:
        lines.append(f"👨‍🎓 {lead['who']}")
    if lead["subject"]:
        lines.append(f"📚 {lead['subject']}")
    lines.append(
        f"{'✅ Обработана' if lead['status'] == 'done' else '🆕 Не обработана'}"
    )
    return "\n".join(lines)


def _filter_label(filter_: str) -> str:
    return {
        "new": "🆕 Необработанные",
        "done": "✅ Обработанные",
        "chat": "💬 Чат с клиентами",
    }[filter_]


async def _send_menu(message: Message) -> None:
    """Меню менеджера с inline-кнопками + reply-клавиатура внизу."""
    new_count = storage.count_unanswered()
    chat_count = storage.count_chat_clients()
    await message.answer(
        f"Меню менеджера\n"
        f"📬 Неотвеченных: {new_count}\n"
        f"💬 Чатов: {chat_count}",
        reply_markup=manager_menu_kb(new_count, chat_count),
    )


# ---------------------------------------------------------------------------
# /start, reply-кнопки (📋 Заявки, 💬 Неотвеченные, 👥 Ученики, ❓ Помощь)
# ---------------------------------------------------------------------------
@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    if not _is_manager(message.from_user.id):
        await message.answer(
            "Привет! Это бот курсов LevelUp. Мы скоро ответим — напиши "
            "свой вопрос или оставь контакт."
        )
        return
    await message.answer("Добро пожаловать!", reply_markup=manager_reply_kb())
    await _send_menu(message)


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    if _is_manager(message.from_user.id):
        await _send_menu(message)
    else:
        await cmd_start(message)


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    if not _is_manager(message.from_user.id):
        return
    if await state.get_state() is not None:
        await state.clear()
        await message.answer("Ответ отменён.")
    else:
        await message.answer("Я и так никому не отвечаю 🙂")


@router.message(F.text == "📋 Заявки")
async def btn_leads(message: Message, state: FSMContext) -> None:
    if not _is_manager(message.from_user.id):
        return
    await state.update_data(last_filter="new")
    await _show_leads(message, "new", 0)


@router.message(F.text == "💬 Неотвеченные")
async def btn_unanswered(message: Message, state: FSMContext) -> None:
    if not _is_manager(message.from_user.id):
        return
    leads = storage.list_leads(limit=100, status="new")
    total = len(leads)
    if total == 0:
        await message.answer("Все обработаны! Нет неотвеченных заявок.")
        return
    lines = [f"💬 Неотвеченные — {total}:", ""]
    for lead in leads[:5]:
        lines.append(f"🆕 #{lead['id']} {lead['name']} · {lead['created_at']}")
    await message.answer(
        "\n".join(lines),
        reply_markup=leads_list_kb(leads[:5], "new", 0, total),
    )


@router.message(F.text == "👥 Ученики")
async def btn_roster(message: Message) -> None:
    if not _is_manager(message.from_user.id):
        return
    rows = roster_svc.fetch_roster()
    if not rows:
        await message.answer("Нет данных или БД недоступна.")
        return
    text = roster_svc.roster_text(rows)
    if len(text) > 3900:
        text = text[:3900] + "…"
    await message.answer(text)
    await message.answer_document(
        BufferedInputFile(
            roster_svc.roster_csv(rows), filename="levelup_ученики.csv"
        )
    )


@router.message(F.text == "❓ Помощь")
async def btn_help(message: Message) -> None:
    if not _is_manager(message.from_user.id):
        return
    await message.answer(
        "Команды менеджера:\n\n"
        "📋 Заявки — все заявки\n"
        "💬 Неотвеченные — только новые\n"
        "👥 Ученики — список из БД LevelUp\n"
        "❌ Отмена — выйти из режима ответа\n\n"
        "Ответ клиенту: нажми «✍️ Ответить» на его сообщении "
        "и напиши ответ. Можно отправить текст, фото, стикер, "
        "голосовое — всё дойдёт."
    )


# ---------------------------------------------------------------------------
# Списки заявок (inline-кнопки)
# ---------------------------------------------------------------------------
async def _show_leads(message: Message, filter_: str, page: int) -> None:
    kwargs = {}
    if filter_ == "new":
        kwargs["status"] = "new"
    elif filter_ == "done":
        kwargs["status"] = "done"
    elif filter_ == "chat":
        kwargs["source"] = "chat"
    leads = storage.list_leads(limit=100, **kwargs)
    total = len(leads)
    page_leads = leads[page * PAGE_SIZE:(page + 1) * PAGE_SIZE]

    lines = [f"{_filter_label(filter_)} — всего {total}:", ""]
    for lead in page_leads:
        mark = "✅" if lead["status"] == "done" else "🆕"
        lines.append(
            f"{mark} #{lead['id']} {lead['name']} · {lead['created_at']}"
        )
    await message.answer(
        "\n".join(lines),
        reply_markup=leads_list_kb(page_leads, filter_, page, total),
    )


async def _default_filter(state) -> str:
    data = await state.get_data()
    return data.get("last_filter", "new")


@router.callback_query(F.data == "menu:0")
async def cb_menu(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_manager(callback.from_user.id):
        await callback.answer("Ты не менеджер", show_alert=True)
        return
    await callback.answer()
    await state.clear()
    new_count = storage.count_unanswered()
    chat_count = storage.count_chat_clients()
    await callback.message.edit_text(
        f"Меню менеджера\n"
        f"📬 Неотвеченных: {new_count}\n"
        f"💬 Чатов: {chat_count}",
        reply_markup=manager_menu_kb(new_count, chat_count),
    )


@router.callback_query(F.data.regexp(r"^leads:(new|done|chat):(\d+)$"))
async def cb_leads_list(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_manager(callback.from_user.id):
        await callback.answer("Ты не менеджер", show_alert=True)
        return
    filter_, page = callback.data.split(":")[1], int(callback.data.split(":")[2])
    await state.update_data(last_filter=filter_)
    await callback.answer()
    await _show_leads(callback.message, filter_, page)


@router.callback_query(F.data.regexp(r"^lead:(\d+):0$"))
async def cb_lead_card(callback: CallbackQuery) -> None:
    if not _is_manager(callback.from_user.id):
        await callback.answer("Ты не менеджер", show_alert=True)
        return
    lead_id = int(callback.data.split(":")[1])
    lead = storage.get_lead(lead_id)
    if lead is None:
        await callback.answer("Заявка не найдена", show_alert=True)
        return
    await callback.answer()
    await callback.message.edit_text(
        _lead_text(dict(lead)),
        reply_markup=lead_card_kb(lead_id, lead["status"], lead["source"]),
    )


@router.callback_query(F.data == "lead:back:0")
async def cb_lead_back(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_manager(callback.from_user.id):
        await callback.answer("Ты не менеджер", show_alert=True)
        return
    filter_ = await _default_filter(state)
    await callback.answer()
    await _show_leads(callback.message, filter_, 0)


@router.callback_query(F.data.regexp(r"^lead:(done|reopen):(\d+):0$"))
async def cb_lead_toggle(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_manager(callback.from_user.id):
        await callback.answer("Ты не менеджер", show_alert=True)
        return
    new_status = "done" if callback.data.startswith("lead:done") else "new"
    lead_id = int(callback.data.split(":")[2])
    storage.set_lead_status(lead_id, new_status)
    lead = storage.get_lead(lead_id)
    if lead is None:
        await callback.answer("Заявка не найдена", show_alert=True)
        return
    await callback.answer(
        "✅ Обработана" if new_status == "done" else "↩️ Вернул в работу"
    )
    await callback.message.edit_text(
        _lead_text(dict(lead)),
        reply_markup=lead_card_kb(lead_id, lead["status"], lead["source"]),
    )


# ---------------------------------------------------------------------------
# Ответ клиенту
# ---------------------------------------------------------------------------
async def _enter_reply(callback: CallbackQuery, state: FSMContext, target: int) -> None:
    if MANAGER_GROUP_ID is not None:
        thread = storage.get_thread(target)
        if thread is not None:
            await callback.answer()
            await callback.message.answer(
                f"Переписка в теме «{thread['name']}» в группе — ответьте там."
            )
        else:
            await callback.answer()
            await callback.message.answer(
                "У этого клиента ещё нет темы — попросите его написать боту."
            )
        return
    await state.set_state(ReplyStates.waiting_reply)
    await state.update_data(reply_to=target)
    await callback.answer()
    await callback.message.answer(
        "Жду ответ. Текст, фото, стикер, голосовое — всё дойдёт. "
        "Отмена — /cancel"
    )


@router.callback_query(F.data.regexp(r"^reply:(\d+):chat$"))
async def cb_reply_from_lead(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_manager(callback.from_user.id):
        await callback.answer("Ты не менеджер", show_alert=True)
        return
    lead_id = int(callback.data.split(":")[1])
    lead = storage.get_lead(lead_id)
    if lead is None:
        await callback.answer("Заявка не найдена", show_alert=True)
        return
    await _enter_reply(callback, state, int(lead["phone"]))


@router.callback_query(F.data.regexp(r"^reply:(\d+):0$"))
async def cb_reply_direct(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_manager(callback.from_user.id):
        await callback.answer("Ты не менеджер", show_alert=True)
        return
    target_id = int(callback.data.split(":")[1])
    await _enter_reply(callback, state, target_id)


@router.message(ReplyStates.waiting_reply)
async def manager_reply_any(message: Message, state: FSMContext) -> None:
    if not _is_manager(message.from_user.id):
        await state.clear()
        return
    data = await state.get_data()
    target = data.get("reply_to")
    await state.clear()
    if target is None:
        await message.answer("Диалог сброшен. Нажми «✍️ Ответить» ещё раз.")
        return
    try:
        if message.text:
            await message.bot.send_message(target, message.text)
        else:
            await message.copy_to(target)
        await message.answer(f"✅ Отправлено клиенту.")
    except Exception:
        await message.answer(
            "Не удалось отправить — клиент мог заблокировать бота."
        )


# ---------------------------------------------------------------------------
# Клиент пишет боту
# ---------------------------------------------------------------------------
async def _thread_deliver(message: Message, sender, text: str) -> None:
    thread = storage.get_thread(sender.id)
    if thread is None:
        created = await message.bot.create_forum_topic(
            MANAGER_GROUP_ID, sender.full_name or str(sender.id)
        )
        storage.set_thread(sender.id, created.message_thread_id,
                           sender.full_name or str(sender.id))
        thread = storage.get_thread(sender.id)
    try:
        await message.copy_to(
            MANAGER_GROUP_ID, message_thread_id=thread["thread_id"]
        )
    except Exception:
        await message.bot.send_message(
            MANAGER_GROUP_ID,
            f"{text}\n(копия недоступна)",
            message_thread_id=thread["thread_id"],
        )


@router.message(F.chat.type == "private")
async def any_message_for_manager(message: Message, state: FSMContext) -> None:
    """Клиент пишет боту → заявка (без дублей) + пересылка менеджеру/в группу."""
    if _is_manager(message.from_user.id):
        await _send_menu(message)
        return
    await state.clear()

    sender = message.from_user
    name = sender.full_name or str(sender.id)
    text = message.text or message.caption or "📎 (медиа)"

    lead = storage.get_chat_lead(sender.id)
    is_new = lead is None
    if is_new:
        lead_id = storage.create_lead(name, str(sender.id), "", text, source="chat")
    else:
        lead_id = lead["id"]

    if MANAGER_GROUP_ID is not None:
        await _thread_deliver(message, sender, text)
    else:
        if is_new:
            await message.bot.send_message(
                MANAGER_TG_ID,
                f"💬 Новый клиент: {name} (id {sender.id})",
            )
        try:
            await message.copy_to(
                MANAGER_TG_ID, reply_markup=chat_message_kb(sender.id)
            )
        except Exception:
            await message.bot.send_message(
                MANAGER_TG_ID,
                f"{text}\n(копия недоступна)",
                reply_markup=chat_message_kb(sender.id),
            )


@router.message(F.chat.type.in_({"group", "supergroup"}))
async def group_message(message: Message) -> None:
    if MANAGER_GROUP_ID is None:
        await message.bot.send_message(
            MANAGER_TG_ID,
            "📎 Группа подключена. Добавь в .env:\n"
            f"MANAGER_GROUP_ID={message.chat.id}\nи перезапусти бота.",
        )
        return
    if message.chat.id != MANAGER_GROUP_ID:
        return
    if message.message_thread_id is None:
        return
    rows = storage.list_threads()
    thread = next(
        (t for t in rows if t["thread_id"] == message.message_thread_id), None
    )
    if thread is None:
        return
    if message.from_user.id == MANAGER_TG_ID:
        await message.copy_to(thread["user_id"])
    else:
        await message.bot.send_message(
            MANAGER_TG_ID,
            f"⚠️ {message.from_user.full_name} пытается отвечать "
            "клиенту. Пишите в темы только вы.",
        )
