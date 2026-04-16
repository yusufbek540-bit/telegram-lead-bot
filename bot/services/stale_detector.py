"""
Stale lead detector — daily job at 09:00 Tashkent time.

A lead is stale when last_activity_at is older than the threshold
for its current status (from config.STALE_THRESHOLDS, in days).

For each newly-stale lead:
  1. Writes a 'stale_flagged' event to the events table
  2. Notifies the assigned team member (or all admins if unassigned)

Deduplication: skips leads that already have a 'stale_flagged' event
from the past 24 hours to avoid re-notifying on the same stale state.
"""

import logging
import time
from datetime import datetime, timedelta, timezone

from aiogram import Bot

from bot.config import config
from bot.services.db_service import db

logger = logging.getLogger(__name__)

# Statuses where staleness matters (terminal statuses excluded)
ACTIVE_STATUSES = {"new", "contacted", "qualified", "proposal_sent"}


async def _get_recipient_ids(lead: dict) -> list:
    """Return Telegram IDs to notify: assigned member first, fall back to all admins."""
    if lead.get("assigned_to"):
        member = await db.get_team_member_by_name(lead["assigned_to"])
        if member and member.get("telegram_id"):
            return [int(member["telegram_id"])]
    return list(config.ADMIN_IDS)


async def _already_flagged_today(telegram_id: int) -> bool:
    """True if a stale_flagged event was written for this lead in the past 24h."""
    since = (datetime.now(config.tz) - timedelta(hours=24)).isoformat()
    result = (
        db.client.table("events")
        .select("id")
        .eq("telegram_id", telegram_id)
        .eq("event_type", "stale_flagged")
        .gte("created_at", since)
        .limit(1)
        .execute()
    )
    return bool(result.data)


async def detect_stale_leads(bot: Bot) -> None:
    """Daily job: flag leads that haven't had activity within their status threshold."""
    start = time.monotonic()
    logger.info("detect_stale_leads: starting")
    try:
        now = datetime.now(config.tz)
        # Fetch all active leads that have a last_activity_at value
        result = (
            db.client.table("leads")
            .select("telegram_id, first_name, last_name, status, last_activity_at, lead_score, assigned_to")
            .in_("status", list(ACTIVE_STATUSES))
            .not_.is_("last_activity_at", "null")
            .execute()
        )
        leads = result.data or []
        flagged = 0

        for lead in leads:
            status = lead.get("status", "new")
            threshold_days = config.STALE_THRESHOLDS.get(status)
            if not threshold_days:
                continue

            last_activity = datetime.fromisoformat(lead["last_activity_at"].replace("Z", "+00:00"))
            days_since = (now - last_activity).total_seconds() / 86400

            if days_since <= threshold_days:
                continue  # Not stale yet

            tid = lead["telegram_id"]
            if await _already_flagged_today(tid):
                continue  # Already notified today

            # Flag it
            await db.track_event(tid, "stale_flagged", {
                "days_since_activity": round(days_since, 1),
                "status": status,
                "threshold_days": threshold_days,
            })
            flagged += 1

            name = f"{lead.get('first_name') or ''} {lead.get('last_name') or ''}".strip() or "—"
            score = lead.get("lead_score", 0)
            text = (
                f"⚠️ <b>Застывший лид</b>\n\n"
                f"👤 {name}\n"
                f"📊 Статус: {status}\n"
                f"⭐ Баллы: {score}\n"
                f"📅 Нет активности: {round(days_since, 1)} дн."
            )
            recipient_ids = await _get_recipient_ids(lead)
            for admin_id in recipient_ids:
                try:
                    await bot.send_message(admin_id, text, parse_mode="HTML")
                except Exception as e:
                    logger.warning(f"detect_stale_leads: failed to notify {admin_id} — {e}")

        elapsed = time.monotonic() - start
        logger.info(f"detect_stale_leads: flagged {flagged} leads in {elapsed:.2f}s")

    except Exception as e:
        logger.error(f"detect_stale_leads: failed — {e}", exc_info=True)
