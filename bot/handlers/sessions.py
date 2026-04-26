"""
/sessions — user-facing booking management.

Lets a user list their upcoming Cal.com sessions on demand and confirm,
cancel, or reschedule each one. Reuses the same callback prefixes as the
2h reminder (bk_confirm / bk_cancel / bk_resched) so the existing
booking_reminder router handles all mutations.
"""

import datetime
import logging

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    WebAppInfo,
)

from bot.config import config
from bot.services.db_service import db

logger = logging.getLogger(__name__)
router = Router()


_MONTHS_RU = ["января", "февраля", "марта", "апреля", "мая", "июня",
              "июля", "августа", "сентября", "октября", "ноября", "декабря"]
_MONTHS_UZ = ["yanvar", "fevral", "mart", "aprel", "may", "iyun",
              "iyul", "avgust", "sentabr", "oktabr", "noyabr", "dekabr"]


def _fmt(iso: str | None, lang: str) -> tuple[str, str]:
    if not iso:
        return ("—", "—")
    try:
        dt = datetime.datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except ValueError:
        return ("—", "—")
    local = dt.astimezone(config.tz)
    months = _MONTHS_RU if lang == "ru" else _MONTHS_UZ
    return (f"{local.day:02d} {months[local.month - 1]}", f"{local.hour:02d}:{local.minute:02d}")


def _row_kb(booking_id: int, lang: str) -> InlineKeyboardMarkup:
    if lang == "ru":
        labels = ("✅ Подтвердить", "🔄 Перенести", "❌ Отменить")
        back = "⬅️ Назад в меню"
    else:
        labels = ("✅ Tasdiqlash", "🔄 Ko'chirish", "❌ Bekor qilish")
        back = "⬅️ Menyuga qaytish"
    rows = [
        [InlineKeyboardButton(text=labels[0], callback_data=f"bk_confirm:{booking_id}")],
        [
            InlineKeyboardButton(text=labels[1], callback_data=f"bk_resched:{booking_id}"),
            InlineKeyboardButton(text=labels[2], callback_data=f"bk_cancel:{booking_id}"),
        ],
        [InlineKeyboardButton(text=back, callback_data="main_menu")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def _fetch_upcoming(telegram_id: int) -> list[dict]:
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    try:
        res = (
            db.client.table("bookings")
            .select("id, scheduled_at, status, confirmed_at, cancel_url, reschedule_url")
            .eq("telegram_id", telegram_id)
            .eq("status", "scheduled")
            .gte("scheduled_at", now_iso)
            .order("scheduled_at")
            .execute()
        )
        return res.data or []
    except Exception as e:
        logger.error(f"sessions list query failed: {e}", exc_info=True)
        return []


async def _send_sessions(target, telegram_id: int, lang: str, edit: bool = False):
    bookings = await _fetch_upcoming(telegram_id)

    if not bookings:
        if lang == "ru":
            text = (
                "📭 У вас пока нет запланированных сессий.\n\n"
                "Хотите забронировать бесплатную 30-минутную стратегическую сессию?"
            )
            btn = "📅 Записаться"
        else:
            text = (
                "📭 Sizda hali rejalashtirilgan sessiyalar yo'q.\n\n"
                "Bepul 30 daqiqalik strategik sessiyani bron qilmoqchimisiz?"
            )
            btn = "📅 Yozilish"
        back = "⬅️ Назад" if lang == "ru" else "⬅️ Orqaga"
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text=btn,
                web_app=WebAppInfo(url=f"{config.TWA_URL}?tab=schedule&lang={lang}"),
            )],
            [InlineKeyboardButton(text=back, callback_data="main_menu")],
        ])
        if edit:
            await target.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
        else:
            await target.answer(text, reply_markup=kb, parse_mode="HTML")
        return

    if lang == "ru":
        header = f"📅 <b>Ваши сессии</b> ({len(bookings)})\n"
    else:
        header = f"📅 <b>Sizning sessiyalaringiz</b> ({len(bookings)})\n"

    if edit:
        await target.message.edit_text(header, parse_mode="HTML")
        send = target.message.answer
    else:
        await target.answer(header, parse_mode="HTML")
        send = target.answer

    for b in bookings:
        date, time = _fmt(b.get("scheduled_at"), lang)
        confirmed = bool(b.get("confirmed_at"))
        if lang == "ru":
            badge = "✓ подтверждено" if confirmed else "⏳ ожидает подтверждения"
            body = (
                f"📅 <b>{date}</b> в <b>{time}</b>\n"
                f"🕐 ~30 минут, бесплатно\n"
                f"<i>{badge}</i>"
            )
        else:
            badge = "✓ tasdiqlandi" if confirmed else "⏳ tasdiqlash kutilmoqda"
            body = (
                f"📅 <b>{date}</b>, soat <b>{time}</b>\n"
                f"🕐 ~30 daqiqa, bepul\n"
                f"<i>{badge}</i>"
            )
        kb = _row_kb(b["id"], lang)
        await send(body, reply_markup=kb, parse_mode="HTML")


@router.message(Command("sessions"))
async def cmd_sessions(message: Message):
    lead = await db.get_lead(message.from_user.id)
    lang = lead.get("preferred_lang", config.DEFAULT_LANG) if lead else config.DEFAULT_LANG
    await db.track_event(message.from_user.id, "sessions_listed", {"source": "command"})
    await _send_sessions(message, message.from_user.id, lang, edit=False)


@router.callback_query(F.data == "my_sessions")
async def cb_my_sessions(callback: CallbackQuery):
    lead = await db.get_lead(callback.from_user.id)
    lang = lead.get("preferred_lang", config.DEFAULT_LANG) if lead else config.DEFAULT_LANG
    await db.track_event(callback.from_user.id, "sessions_listed", {"source": "menu"})
    await _send_sessions(callback, callback.from_user.id, lang, edit=True)
    await callback.answer()
