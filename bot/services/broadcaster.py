"""
Broadcaster service — sends campaign messages to filtered recipients.

Features:
- Filters leads from target_filters JSONB
- Rate-limits at 25 messages/sec (Telegram bot API limit)
- Handles TelegramForbiddenError (user blocked bot)
- Handles 429 rate limit with retry_after
- Writes campaign_deliveries rows
- Updates campaign.sent_count / failed_count / status
"""

import asyncio
import logging
from datetime import datetime, timezone, timedelta

from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter

from bot.services.db_service import db

logger = logging.getLogger(__name__)

# Telegram allows ~30 msg/sec per bot; we stay safe at 25
RATE_LIMIT_DELAY = 0.04  # seconds between messages (25/sec)


async def get_campaign_recipients(target_filters: dict) -> list[dict]:
    """
    Query leads matching the campaign's target_filters.

    Supported filter keys:
      - status: str (e.g. 'new', 'qualified')
      - source: str
      - language: str ('uz' or 'ru')
      - inactive_days: int (leads with no update in N days)
      - tag: str (leads who have this lead_tag)
    """
    query = db.client.table("leads").select(
        "telegram_id, preferred_lang, first_name, updated_at, phone, duplicate_of"
    )

    if status := target_filters.get("status"):
        query = query.eq("status", status)
    if source := target_filters.get("source"):
        query = query.eq("source", source)
    if language := target_filters.get("language"):
        query = query.eq("preferred_lang", language)

    result = query.execute()
    leads = result.data or []

    # Client-side filter: inactive_days
    if inactive_days := target_filters.get("inactive_days"):
        cutoff = datetime.now(timezone.utc) - timedelta(days=int(inactive_days))
        leads = [
            l for l in leads
            if l.get("updated_at") and datetime.fromisoformat(
                l["updated_at"].replace("Z", "+00:00")
            ) < cutoff
        ]

    # Client-side filter: tag (check lead_tags table)
    if tag := target_filters.get("tag"):
        tagged_res = db.client.table("lead_tags").select("telegram_id").eq("tag", tag).execute()
        tagged_ids = {r["telegram_id"] for r in (tagged_res.data or [])}
        leads = [l for l in leads if l.get("telegram_id") in tagged_ids]

    # Exclude duplicates (secondary leads)
    leads = [l for l in leads if not l.get("duplicate_of")]

    return leads


async def send_campaign(campaign_id: int, bot: Bot) -> None:
    """Fire a campaign: fetch recipients, send messages, record deliveries."""
    # Load campaign
    camp_res = db.client.table("campaigns").select("*").eq("id", campaign_id).execute()
    if not camp_res.data:
        logger.error(f"Campaign {campaign_id} not found")
        return

    campaign = camp_res.data[0]
    if campaign["status"] not in ("scheduled", "draft"):
        logger.warning(f"Campaign {campaign_id} already in status={campaign['status']}, skipping")
        return

    # Mark as sending
    db.client.table("campaigns").update({
        "status": "sending",
        "updated_at": datetime.now(timezone.utc).isoformat()
    }).eq("id", campaign_id).execute()

    target_filters = campaign.get("target_filters") or {}
    msg_uz = campaign.get("message_uz", "")
    msg_ru = campaign.get("message_ru", "")

    recipients = await get_campaign_recipients(target_filters)
    logger.info(f"Campaign {campaign_id}: sending to {len(recipients)} recipients")

    sent = 0
    failed = 0

    for lead in recipients:
        tg_id = lead["telegram_id"]
        lang = lead.get("preferred_lang", "ru")
        message_text = msg_uz if lang == "uz" else msg_ru

        if not message_text.strip():
            continue

        delivery = {
            "campaign_id": campaign_id,
            "telegram_id": tg_id,
        }

        try:
            await bot.send_message(tg_id, message_text, parse_mode="HTML")
            delivery["sent_at"] = datetime.now(timezone.utc).isoformat()
            delivery["delivered"] = True
            sent += 1
        except TelegramForbiddenError:
            # User blocked the bot
            delivery["delivered"] = False
            delivery["failed_reason"] = "blocked_bot"
            failed += 1
            logger.info(f"Campaign {campaign_id}: lead {tg_id} blocked bot, skipping")
        except TelegramRetryAfter as e:
            # Hit rate limit — pause then retry once
            logger.warning(f"Campaign {campaign_id}: rate limited, sleeping {e.retry_after}s")
            await asyncio.sleep(e.retry_after)
            try:
                await bot.send_message(tg_id, message_text, parse_mode="HTML")
                delivery["sent_at"] = datetime.now(timezone.utc).isoformat()
                delivery["delivered"] = True
                sent += 1
            except Exception as retry_err:
                delivery["delivered"] = False
                delivery["failed_reason"] = str(retry_err)[:200]
                failed += 1
        except Exception as e:
            delivery["delivered"] = False
            delivery["failed_reason"] = str(e)[:200]
            failed += 1
            logger.error(f"Campaign {campaign_id}: failed to send to {tg_id}: {e}")

        # Write delivery record
        try:
            db.client.table("campaign_deliveries").insert(delivery).execute()
        except Exception as db_err:
            logger.error(f"Failed to write delivery record: {db_err}")

        # Rate-limit delay
        await asyncio.sleep(RATE_LIMIT_DELAY)

    # Mark campaign done
    final_status = "sent" if failed == 0 else "sent"  # always mark sent even with some failures
    db.client.table("campaigns").update({
        "status": final_status,
        "sent_count": sent,
        "failed_count": failed,
        "updated_at": datetime.now(timezone.utc).isoformat()
    }).eq("id", campaign_id).execute()

    logger.info(f"Campaign {campaign_id} complete: sent={sent}, failed={failed}")


async def check_scheduled_campaigns(bot: Bot) -> None:
    """Scheduled job: fire any campaigns whose scheduled_for has passed."""
    logger.info("check_scheduled_campaigns: scanning for due campaigns")
    try:
        # Get all scheduled campaigns - compare server-side via Supabase
        now = datetime.now(timezone.utc).isoformat()
        res = db.client.table("campaigns").select("id, scheduled_for").eq("status", "scheduled").execute()

        due = []
        for row in (res.data or []):
            sf = row.get("scheduled_for")
            if not sf:
                due.append(row)
                continue
            # Parse scheduled_for and compare
            try:
                scheduled_dt = datetime.fromisoformat(sf.replace("Z", "+00:00"))
                if scheduled_dt <= datetime.now(timezone.utc):
                    due.append(row)
            except Exception:
                due.append(row)  # If parsing fails, fire it anyway

        logger.info(f"check_scheduled_campaigns: found {len(due)} due campaign(s) out of {len(res.data or [])} scheduled")

        for row in due:
            logger.info(f"Triggering scheduled campaign {row['id']}")
            try:
                await send_campaign(row["id"], bot)
            except Exception as e:
                logger.error(f"Campaign {row['id']} failed: {e}")
                db.client.table("campaigns").update({"status": "failed"}).eq("id", row["id"]).execute()
    except Exception as e:
        logger.error(f"check_scheduled_campaigns error: {e}", exc_info=True)


async def count_recipients(target_filters: dict) -> int:
    """Preview: return number of leads matching the given filters."""
    recipients = await get_campaign_recipients(target_filters)
    return len(recipients)
