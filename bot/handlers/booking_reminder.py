"""
Booking reminder handlers — handle the inline buttons attached to the
2-hour pre-session reminder (confirm / cancel / reschedule).

Cancel and reschedule both delegate to Cal.com-hosted URLs we already
have stored in `bookings` (cancel_url / reschedule_url). Cal.com handles
the actual mutation and fires BOOKING_CANCELLED / BOOKING_RESCHEDULED
back to our webhook, which keeps Supabase in sync.
"""

import datetime
import logging

from aiogram import Router, F
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    WebAppInfo,
)

from bot.config import config
from bot.services.db_service import db

logger = logging.getLogger(__name__)
router = Router()


def _fmt_dt(iso: str | None, lang: str) -> tuple[str, str]:
    """Format an ISO timestamp into (date, time) strings in Tashkent TZ."""
    if not iso:
        return ("—", "—")
    try:
        dt = datetime.datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except ValueError:
        return ("—", "—")
    local = dt.astimezone(config.tz)
    months_ru = ["января", "февраля", "марта", "апреля", "мая", "июня",
                 "июля", "августа", "сентября", "октября", "ноября", "декабря"]
    months_uz = ["yanvar", "fevral", "mart", "aprel", "may", "iyun",
                 "iyul", "avgust", "sentabr", "oktabr", "noyabr", "dekabr"]
    months = months_ru if lang == "ru" else months_uz
    date = f"{local.day:02d} {months[local.month - 1]}"
    time = f"{local.hour:02d}:{local.minute:02d}"
    return (date, time)


async def _get_booking(booking_id: int) -> dict | None:
    try:
        res = db.client.table("bookings").select("*").eq("id", booking_id).limit(1).execute()
        return res.data[0] if res.data else None
    except Exception as e:
        logger.error(f"booking lookup failed: {e}")
        return None


@router.callback_query(F.data.startswith("bk_confirm:"))
async def cb_confirm(callback: CallbackQuery):
    booking_id = int(callback.data.split(":", 1)[1])
    booking = await _get_booking(booking_id)
    if not booking:
        await callback.answer("Booking not found", show_alert=True)
        return

    lead = await db.get_lead(callback.from_user.id)
    lang = lead.get("preferred_lang", config.DEFAULT_LANG) if lead else "ru"

    try:
        db.client.table("bookings").update({
            "confirmed_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }).eq("id", booking_id).execute()
    except Exception as e:
        logger.error(f"confirm write failed: {e}")

    await db.track_event(callback.from_user.id, "booking_confirmed", {"booking_id": booking_id})

    date, time = _fmt_dt(booking.get("scheduled_at"), lang)
    if lang == "ru":
        text = f"✓ Подтверждено. Ждём вас <b>{date}</b> в <b>{time}</b>."
        back = "⬅️ Назад в меню"
    else:
        text = f"✓ Tasdiqlandi. Sizni <b>{date}</b> soat <b>{time}</b> da kutamiz."
        back = "⬅️ Menyuga qaytish"

    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=back, callback_data="main_menu")
    ]])
    try:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except Exception:
        await callback.message.answer(text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("bk_cancel:"))
async def cb_cancel(callback: CallbackQuery):
    booking_id = int(callback.data.split(":", 1)[1])
    booking = await _get_booking(booking_id)
    if not booking:
        await callback.answer("Booking not found", show_alert=True)
        return

    lead = await db.get_lead(callback.from_user.id)
    lang = lead.get("preferred_lang", config.DEFAULT_LANG) if lead else "ru"
    cancel_url = booking.get("cancel_url")
    if not cancel_url and booking.get("cal_booking_uid"):
        cancel_url = f"https://app.cal.com/booking/{booking['cal_booking_uid']}?cancel=true"

    await db.track_event(callback.from_user.id, "booking_cancel_clicked", {"booking_id": booking_id})

    if not cancel_url:
        msg = "Cancel link unavailable. Contact support." if lang == "ru" else "Bekor qilish havolasi mavjud emas."
        await callback.answer(msg, show_alert=True)
        return

    if lang == "ru":
        prompt = "Отмена обрабатывается на странице Cal.com — нажмите кнопку ниже."
        btn = "Открыть отмену"
        back = "⬅️ Назад в меню"
    else:
        prompt = "Bekor qilish Cal.com sahifasida amalga oshiriladi — quyidagi tugmani bosing."
        btn = "Bekor qilishni ochish"
        back = "⬅️ Menyuga qaytish"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=btn, url=cancel_url)],
        [InlineKeyboardButton(text=back, callback_data="main_menu")],
    ])
    try:
        await callback.message.edit_text(prompt, reply_markup=kb)
    except Exception:
        await callback.message.answer(prompt, reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data.startswith("bk_resched:"))
async def cb_reschedule(callback: CallbackQuery):
    booking_id = int(callback.data.split(":", 1)[1])
    booking = await _get_booking(booking_id)
    if not booking:
        await callback.answer("Booking not found", show_alert=True)
        return

    lead = await db.get_lead(callback.from_user.id)
    lang = lead.get("preferred_lang", config.DEFAULT_LANG) if lead else "ru"
    reschedule_url = booking.get("reschedule_url")
    if not reschedule_url and booking.get("cal_booking_uid"):
        reschedule_url = f"https://app.cal.com/reschedule/{booking['cal_booking_uid']}"

    await db.track_event(callback.from_user.id, "booking_reschedule_clicked", {"booking_id": booking_id})

    if not reschedule_url:
        msg = "Reschedule link unavailable." if lang == "ru" else "Ko‘chirish havolasi mavjud emas."
        await callback.answer(msg, show_alert=True)
        return

    if lang == "ru":
        prompt = "Откройте страницу переноса и выберите новое время."
        btn = "Перенести встречу"
        back = "⬅️ Назад в меню"
    else:
        prompt = "Ko‘chirish sahifasini oching va yangi vaqt tanlang."
        btn = "Uchrashuvni ko‘chirish"
        back = "⬅️ Menyuga qaytish"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=btn, web_app=WebAppInfo(url=reschedule_url))],
        [InlineKeyboardButton(text=back, callback_data="main_menu")],
    ])
    try:
        await callback.message.edit_text(prompt, reply_markup=kb)
    except Exception:
        await callback.message.answer(prompt, reply_markup=kb)
    await callback.answer()
