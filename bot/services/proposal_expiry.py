"""
Proposal expiry job — runs every 6 hours.

Actions:
  1. Proposals expiring within 3 days → send one-time warning to admins.
  2. Proposals past valid_until with status='sent' → mark status='expired'.
"""

import logging
import time
from datetime import datetime, timezone, timedelta

from aiogram import Bot

from bot.config import config
from bot.services.db_service import db

logger = logging.getLogger(__name__)


async def check_proposal_expiry(bot: Bot):
    start = time.monotonic()
    logger.info("check_proposal_expiry: starting")
    try:
        now = datetime.now(config.tz)
        three_days = (now + timedelta(days=3)).date().isoformat()
        today = now.date().isoformat()

        # 1. Find proposals expiring within 3 days (not yet warned, status='sent')
        soon = db.client.table("proposals") \
            .select("id, telegram_id, title, amount, currency, valid_until, created_by") \
            .eq("status", "sent") \
            .lte("valid_until", three_days) \
            .gte("valid_until", today) \
            .execute()

        for p in (soon.data or []):
            # Check if we already sent a warning event for this proposal
            existing = db.client.table("events") \
                .select("id") \
                .eq("telegram_id", p["telegram_id"]) \
                .eq("event_type", f"proposal_expiry_warning_{p['id']}") \
                .execute()
            if existing.data:
                continue  # Already warned

            # Fetch lead name
            lead_res = db.client.table("leads") \
                .select("first_name, last_name, username") \
                .eq("telegram_id", p["telegram_id"]) \
                .limit(1).execute()
            lead = lead_res.data[0] if lead_res.data else {}
            lead_name = (
                f"{lead.get('first_name', '')} {lead.get('last_name', '')}".strip()
                or lead.get("username") or "Unknown"
            )

            amount_fmt = f"{p['amount']:,.0f} {p['currency']}"
            msg = (
                f"⏰ <b>Предложение истекает через 3 дня!</b>\n\n"
                f"Лид: <b>{lead_name}</b>\n"
                f"Тема: {p['title']}\n"
                f"Сумма: {amount_fmt}\n"
                f"Действует до: {p['valid_until']}\n"
                f"Создал: {p.get('created_by', '—')}"
            )
            for admin_id in config.ADMIN_IDS:
                try:
                    await bot.send_message(admin_id, msg, parse_mode="HTML")
                except Exception:
                    pass

            # Record warning so we don't send again
            db.client.table("events").insert({
                "telegram_id": p["telegram_id"],
                "event_type": f"proposal_expiry_warning_{p['id']}",
                "event_data": {"proposal_id": p["id"]},
            }).execute()

        # 2. Mark overdue proposals as expired
        expired = db.client.table("proposals") \
            .update({"status": "expired", "updated_at": datetime.now(config.tz).isoformat()}) \
            .eq("status", "sent") \
            .lt("valid_until", today) \
            .execute()

        expired_count = len(expired.data or [])
        if expired_count:
            logger.info(f"check_proposal_expiry: marked {expired_count} proposals expired")

        elapsed = time.monotonic() - start
        logger.info(f"check_proposal_expiry: done in {elapsed:.2f}s")
    except Exception as e:
        logger.error(f"check_proposal_expiry: failed — {e}", exc_info=True)
