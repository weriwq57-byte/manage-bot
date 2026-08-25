"""HTTP-endpoint для заявок с сайта (POST /apply).

Сайт шлёт form-data или JSON:
    name, phone, who (необязательно), subject (необязательно)
Заголовок X-Api-Key должен совпадать с WEB_API_KEY (.env).
Заявка сохраняется в SQLite и приходит менеджеру в Telegram с кнопкой.
"""
from aiohttp import web

from . import storage
from .config import MANAGER_TG_ID, WEB_API_KEY
from .handlers import _lead_text
from .keyboards import lead_card_kb


async def _send_lead_to_manager(bot, lead_id: int) -> None:
    lead = storage.get_lead(lead_id)
    if lead is None:
        return
    msg = await bot.send_message(
        MANAGER_TG_ID,
        _lead_text(dict(lead)),
        reply_markup=lead_card_kb(lead_id, lead["status"], lead["source"]),
    )
    storage.set_manager_msg(lead_id, msg.message_id, msg.chat.id)


async def _apply(request: web.Request) -> web.Response:
    # Нет ключа в .env — endpoint отключён
    if not WEB_API_KEY:
        return web.json_response({"error": "endpoint disabled"}, status=403)
    if request.headers.get("X-Api-Key", "") != WEB_API_KEY:
        return web.json_response({"error": "forbidden"}, status=403)

    data = await request.post()
    if not data:
        data = await request.json()

    name = (data.get("name") or "").strip()
    phone = (data.get("phone") or "").strip()
    who = (data.get("who") or "").strip()
    subject = (data.get("subject") or "").strip()
    if not name or not phone:
        return web.json_response({"error": "name and phone required"}, status=400)

    # Дедупликация: если уже есть заявка от этого телефона — обновляем, а не создаём
    existing = storage.get_lead_by_phone(phone)
    if existing is not None:
        lead_id = existing["id"]
    else:
        lead_id = storage.create_lead(name, phone, who, subject, source="web")
    try:
        await _send_lead_to_manager(request.app["bot"], lead_id)
    except Exception as exc:  # важно для сайта: ответ даже если ТГ недоступен
        return web.json_response({"error": f"telegram failed: {exc}"}, status=502)
    return web.json_response({"ok": True, "id": lead_id})


async def _health(request: web.Request) -> web.Response:
    return web.json_response({"ok": True})


def build_app(bot) -> web.Application:
    app = web.Application()
    app["bot"] = bot
    app.router.add_post("/apply", _apply)
    app.router.add_get("/health", _health)
    return app