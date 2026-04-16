"""
Response tracker — records when a lead is first contacted by the team.

Call record_first_contact(telegram_id) whenever a lead's status changes
away from "new" for the first time (e.g., when team marks them "contacted").

This populates leads.first_contact_at, which powers the response time
badge in the CRM (green/yellow/red based on how fast the team responded).
"""

import logging
from datetime import datetime, timezone

from bot.services.db_service import db

logger = logging.getLogger(__name__)


async def record_first_contact(telegram_id: int) -> None:
    """Set first_contact_at on a lead if it hasn't been set yet.

    Safe to call multiple times — only writes on the first call.
    """
    lead = await db.get_lead(telegram_id)
    if not lead:
        logger.warning(f"record_first_contact: lead {telegram_id} not found")
        return
    if lead.get("first_contact_at"):
        return  # Already recorded
    await db.update_lead(
        telegram_id,
        first_contact_at=datetime.now(config.tz).isoformat(),
    )
    logger.info(f"record_first_contact: recorded for {telegram_id}")
