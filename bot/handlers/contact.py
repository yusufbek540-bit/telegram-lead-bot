"""
Contact handler — captures phone number when user shares contact.
"""

from aiogram import Router, F
from aiogram.types import Message

import logging
logger = logging.getLogger(__name__)

from bot.config import config
from bot.texts import t
from bot.services.db_service import db
from bot.keyboards.main_menu import main_menu_keyboard, remove_keyboard

router = Router()


@router.message(F.contact)
async def handle_contact(message: Message):
    """Handle when user shares their phone number."""
    contact = message.contact
    user = message.from_user

    # Save phone number
    await db.update_lead_phone(
        telegram_id=user.id,
        phone=contact.phone_number,
    )

    # Duplicate detection: check if another lead already has this phone
    try:
        dup_res = db.client.table("leads").select("telegram_id").eq(
            "phone", contact.phone_number
        ).neq("telegram_id", user.id).execute()
        if dup_res.data:
            primary_tg_id = dup_res.data[0]["telegram_id"]
            # Mark current lead as duplicate of the primary
            db.client.table("leads").update({
                "duplicate_of": primary_tg_id
            }).eq("telegram_id", user.id).execute()
            logger.info(f"Duplicate detected: {user.id} is a duplicate of {primary_tg_id}")
    except Exception as dup_err:
        logger.warning(f"Duplicate check failed: {dup_err}")

    # Track event
    await db.track_event(user.id, "phone_shared", {"phone": contact.phone_number})

    # Recalculate lead score
    await db.recalculate_score(user.id)

    # Get language
    lead = await db.get_lead(user.id)
    lang = lead.get("preferred_lang", config.DEFAULT_LANG) if lead else config.DEFAULT_LANG
    await message.answer(
        t("contact_received", lang),
        reply_markup=remove_keyboard(),
    )
    await message.answer(
        t("welcome", lang, agency_name=config.AGENCY_NAME),
        reply_markup=main_menu_keyboard(lang),
        parse_mode="HTML",
    )

    # Notify admins about phone shared
    name = f"{user.first_name or ''} {user.last_name or ''}".strip() or "—"
    score = lead.get("lead_score", 0) if lead else 0
    source = lead.get("source", "—") if lead else "—"
    text = t(
        "admin_phone_shared",
        "ru",
        name=name,
        username=user.username or "—",
        phone=contact.phone_number,
        source=source,
        score=score,
    )
    for admin_id in config.ADMIN_IDS:
        try:
            await message.bot.send_message(admin_id, text, parse_mode="HTML")
        except Exception:
            pass
