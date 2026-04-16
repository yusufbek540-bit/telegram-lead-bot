"""
Contact handler — captures phone number when user shares contact.
"""

from aiogram import Router, F
from aiogram.types import Message

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

    # Delete the shared contact message to keep chat clean
    try:
        await message.delete()
    except Exception:
        pass

    # Save phone number
    await db.update_lead_phone(
        telegram_id=user.id,
        phone=contact.phone_number,
    )

    # Track event
    await db.track_event(user.id, "phone_shared", {"phone": contact.phone_number})

    # Recalculate lead score
    await db.recalculate_score(user.id)

    # Get language
    lead = await db.get_lead(user.id)
    lang = lead.get("preferred_lang", config.DEFAULT_LANG) if lead else config.DEFAULT_LANG

    # Remove the share contact ReplyKeyboard, then show inline menu
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
