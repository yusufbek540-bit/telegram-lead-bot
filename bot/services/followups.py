"""
Follow-up reminders — notifies team members about scheduled lead follow-ups.

Runs every hour. Checks followup_reminders for entries where:
  - scheduled_for <= now
  - completed = False

Sends a Telegram message to the assigned team member, or all admins if
the lead is unassigned. Marks the reminder as completed after sending.

This is for TEAM reminders set manually in the CRM, not the automated
user-facing follow-up messages in scheduler_service.py.
"""

import logging
import time
from datetime import datetime, timezone

from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo

from bot.config import config
from bot.services.db_service import db

logger = logging.getLogger(__name__)

CRM_URL = "https://crm-mqsd.vercel.app"


async def _get_recipient_ids(lead: dict) -> list:
    """Return Telegram IDs to notify: assigned member first, fall back to all admins."""
    if lead.get("assigned_to"):
        member = await db.get_team_member_by_name(lead["assigned_to"])
        if member and member.get("telegram_id"):
            return [int(member["telegram_id"])]
    return list(config.ADMIN_IDS)


async def check_followup_reminders(bot: Bot) -> None:
    """Hourly job: send notifications for due follow-up reminders."""
    start = time.monotonic()
    logger.info("check_followup_reminders: starting")
    try:
        now_iso = datetime.now(timezone.utc).isoformat()

        # Fetch overdue, incomplete reminders
        result = (
            db.client.table("followup_reminders")
            .select("id, telegram_id, note, scheduled_for")
            .lte("scheduled_for", now_iso)
            .eq("completed", False)
            .execute()
        )
        reminders = result.data or []

        if not reminders:
            logger.info("check_followup_reminders: no due reminders")
            return

        for reminder in reminders:
            tid = reminder["telegram_id"]
            lead = await db.get_lead(tid)
            if not lead:
                continue

            name = f"{lead.get('first_name') or ''} {lead.get('last_name') or ''}".strip() or "—"
            score = lead.get("lead_score", 0)
            note = reminder.get("note") or "—"

            text = (
                f"⏰ <b>Напоминание о лиде</b>\n\n"
                f"👤 {name}\n"
                f"⭐ Баллы: {score}\n"
                f"📝 Заметка: {note}"
            )
            keyboard = InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(
                    text="📊 Открыть CRM",
                    web_app=WebAppInfo(url=CRM_URL),
                )
            ]])

            recipient_ids = await _get_recipient_ids(lead)
            for admin_id in recipient_ids:
                try:
                    await bot.send_message(admin_id, text, parse_mode="HTML", reply_markup=keyboard)
                except Exception as e:
                    logger.warning(f"check_followup_reminders: failed to notify {admin_id} — {e}")

            # Mark reminder as completed
            db.client.table("followup_reminders").update(
                {"completed": True}
            ).eq("id", reminder["id"]).execute()

        elapsed = time.monotonic() - start
        logger.info(f"check_followup_reminders: processed {len(reminders)} reminders in {elapsed:.2f}s")

    except Exception as e:
        logger.error(f"check_followup_reminders: failed — {e}", exc_info=True)
