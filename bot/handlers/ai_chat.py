"""
Schedule-fallback catch-all — captures any free-text message and redirects
the user to the strategy-session booking inside the TWA. We still persist
the message to conversations so it appears in the CRM context.
Registered LAST so commands, buttons, and live-chat take priority.
"""

from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo

from bot.config import config
from bot.services.db_service import db
from bot.texts import t

router = Router()


@router.message(F.text)
async def fallback_to_schedule(message: Message):
    """Any unmatched text → redirect to the strategy-session booking."""
    user = message.from_user
    user_text = message.text or ""

    lead = await db.get_lead(user.id)
    if not lead:
        await db.upsert_lead(
            telegram_id=user.id,
            first_name=user.first_name,
            last_name=user.last_name,
            username=user.username,
            language_code=user.language_code,
        )
        lead = await db.get_lead(user.id)
    lang = lead.get("preferred_lang", config.DEFAULT_LANG) if lead else config.DEFAULT_LANG

    # Persist for CRM context (no manager forward)
    await db.save_message(user.id, "user", user_text, source="bot_text")
    await db.track_event(user.id, "schedule_fallback", {"message_length": len(user_text)})

    schedule_label = "Выбрать время" if lang == "ru" else "Vaqtni tanlash"
    await message.answer(
        t("partner_handoff_received", lang),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(
                text=schedule_label,
                web_app=WebAppInfo(url=f"{config.TWA_URL}?tab=schedule&lang={lang}"),
            )
        ]]),
    )
