"""
Partner-handoff catch-all — captures any free-text message from a user
and routes it to the assigned manager (or all admins as fallback).

Replaces the previous user-facing AI chat. AI is no longer exposed to users.
The /ask admin command (admin.py) still uses CRM analytics AI separately.
Registered LAST so commands, buttons, and live-chat take priority.
"""

from aiogram import Router, F
from aiogram.types import Message

from bot.config import config
from bot.services.db_service import db
from bot.texts import t

router = Router()


@router.message(F.text)
async def handle_text_message(message: Message):
    """Any unmatched text → leave a message for a partner."""
    from bot.handlers.live_chat import _notify_managers

    user = message.from_user
    user_text = message.text

    lead = await db.get_lead(user.id)
    lang = lead.get("preferred_lang", config.DEFAULT_LANG) if lead else config.DEFAULT_LANG

    # Live chat already active → forward straight through.
    if lead and lead.get("live_chat"):
        await _notify_managers(message.bot, lead, message_text=user_text)
        await message.answer(t("live_chat_forwarded", lang))
        return

    # Ensure lead row exists.
    if not lead:
        await db.upsert_lead(
            telegram_id=user.id,
            first_name=user.first_name,
            last_name=user.last_name,
            username=user.username,
            language_code=user.language_code,
        )
        lead = await db.get_lead(user.id)

    # Open a partner-handoff session: mark live_chat=True so the next manager
    # reply lands back to this user, persist the message, notify managers.
    await db.update_lead(user.id, live_chat=True)
    await db.track_event(user.id, "partner_handoff", {"message_length": len(user_text)})
    await db.save_message(user.id, "user", user_text)
    await _notify_managers(message.bot, lead, message_text=user_text)

    await message.answer(t("partner_handoff_received", lang), parse_mode="HTML")
