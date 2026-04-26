"""
2-hour pre-session booking reminder.

Runs every 15 minutes via the scheduler. Finds all `bookings` rows with
status='scheduled' whose scheduled_at falls in the (now+1h45m, now+2h15m)
window AND have not yet had a reminder sent (reminder_sent_at IS NULL),
and sends each user a Telegram message with confirm/cancel/reschedule
inline buttons. Marks `reminder_sent_at` immediately after dispatch to
prevent duplicates if the next tick overlaps.
"""

import datetime
import logging

from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from bot.config import config
from bot.services.db_service import db

logger = logging.getLogger(__name__)

REMINDER_LEAD_MIN = 105   # 1h45m
REMINDER_LEAD_MAX = 135   # 2h15m


def _fmt_dt(dt: datetime.datetime, lang: str) -> tuple[str, str]:
    months_ru = ["января", "февраля", "марта", "апреля", "мая", "июня",
                 "июля", "августа", "сентября", "октября", "ноября", "декабря"]
    months_uz = ["yanvar", "fevral", "mart", "aprel", "may", "iyun",
                 "iyul", "avgust", "sentabr", "oktabr", "noyabr", "dekabr"]
    months = months_ru if lang == "ru" else months_uz
    return (f"{dt.day:02d} {months[dt.month - 1]}", f"{dt.hour:02d}:{dt.minute:02d}")


def _build_message(lang: str, date: str, time: str) -> str:
    if lang == "ru":
        return (
            f"⏰ <b>Напоминание о сессии</b>\n\n"
            f"📅 Сегодня в <b>{time}</b> ({date})\n"
            f"🕐 ~30 минут, бесплатно\n\n"
            f"Подтвердите, что будете на встрече, или измените план:"
        )
    return (
        f"⏰ <b>Sessiya haqida eslatma</b>\n\n"
        f"📅 Bugun soat <b>{time}</b> da ({date})\n"
        f"🕐 ~30 daqiqa, bepul\n\n"
        f"Uchrashuvga kelishingizni tasdiqlang yoki rejani o‘zgartiring:"
    )


def _build_kb(booking_id: int, lang: str) -> InlineKeyboardMarkup:
    if lang == "ru":
        labels = ("✅ Подтвердить", "❌ Отменить", "🔄 Перенести")
    else:
        labels = ("✅ Tasdiqlash", "❌ Bekor qilish", "🔄 Ko‘chirish")
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=labels[0], callback_data=f"bk_confirm:{booking_id}")],
        [
            InlineKeyboardButton(text=labels[1], callback_data=f"bk_cancel:{booking_id}"),
            InlineKeyboardButton(text=labels[2], callback_data=f"bk_resched:{booking_id}"),
        ],
    ])


async def send_upcoming_reminders(bot: Bot):
    """Find bookings due in ~2h, send reminders, mark sent."""
    now = datetime.datetime.now(datetime.timezone.utc)
    window_start = (now + datetime.timedelta(minutes=REMINDER_LEAD_MIN)).isoformat()
    window_end = (now + datetime.timedelta(minutes=REMINDER_LEAD_MAX)).isoformat()

    try:
        res = (
            db.client.table("bookings")
            .select("id, telegram_id, scheduled_at")
            .eq("status", "scheduled")
            .is_("reminder_sent_at", "null")
            .gte("scheduled_at", window_start)
            .lte("scheduled_at", window_end)
            .execute()
        )
        rows = res.data or []
    except Exception as e:
        logger.error(f"booking reminder query failed: {e}", exc_info=True)
        return

    if not rows:
        return

    logger.info(f"booking_reminders: dispatching {len(rows)} reminders")

    for row in rows:
        booking_id = row["id"]
        telegram_id = row["telegram_id"]
        scheduled_at = row.get("scheduled_at")
        if not telegram_id or not scheduled_at:
            continue

        try:
            lead = await db.get_lead(telegram_id)
            lang = lead.get("preferred_lang", config.DEFAULT_LANG) if lead else "ru"

            try:
                dt_utc = datetime.datetime.fromisoformat(scheduled_at.replace("Z", "+00:00"))
            except ValueError:
                logger.error(f"booking {booking_id}: invalid scheduled_at {scheduled_at}")
                continue
            local = dt_utc.astimezone(config.tz)
            date, time = _fmt_dt(local, lang)

            text = _build_message(lang, date, time)
            kb = _build_kb(booking_id, lang)
            await bot.send_message(telegram_id, text, reply_markup=kb, parse_mode="HTML")

            db.client.table("bookings").update({
                "reminder_sent_at": now.isoformat(),
            }).eq("id", booking_id).execute()

            await db.track_event(telegram_id, "booking_reminder_sent", {"booking_id": booking_id})
        except Exception as e:
            logger.error(f"booking {booking_id} reminder failed: {e}", exc_info=True)
