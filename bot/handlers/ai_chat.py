"""
AI Chat handler — catches all free-text messages and responds via Claude.
This is registered LAST so buttons and commands take priority.
"""

from aiogram import Router, F
from aiogram.types import Message

from bot.config import config
from bot.services.db_service import db
from bot.services.ai_service import ai_service
from bot.keyboards.main_menu import back_to_menu_keyboard

router = Router()


@router.message(F.text)
async def handle_text_message(message: Message):
    """Handle any text message that wasn't caught by other handlers."""
    from bot.texts import t
    from bot.handlers.live_chat import _notify_managers
    user = message.from_user
    user_text = message.text

    # Get lead info for language preference
    lead = await db.get_lead(user.id)
    lang = lead.get("preferred_lang", config.DEFAULT_LANG) if lead else config.DEFAULT_LANG

    # If live chat is active, forward to manager instead of AI
    if lead and lead.get("live_chat"):
        await _notify_managers(message.bot, lead, message_text=user_text)
        await message.answer(t("live_chat_forwarded", lang))
        return

    # If lead doesn't exist yet (shouldn't happen, but safety check)
    if not lead:
        await db.upsert_lead(
            telegram_id=user.id,
            first_name=user.first_name,
            last_name=user.last_name,
            username=user.username,
            language_code=user.language_code,
        )

    # Track AI chat event
    await db.track_event(user.id, "ai_chat", {"message_length": len(user_text)})

    # Save user message to conversation history
    await db.save_message(user.id, "user", user_text)

    # Get conversation history for context
    history = await db.get_conversation(user.id, limit=config.HISTORY_LIMIT)

    # Show typing indicator
    await message.bot.send_chat_action(message.chat.id, "typing")

    # Build user context string for the AI
    parts = []
    if lead:
        name = f"{lead.get('first_name') or ''} {lead.get('last_name') or ''}".strip()
        if name:
            parts.append(f"Name: {name}")
        if lead.get("username"):
            parts.append(f"Telegram: @{lead['username']}")
        if lead.get("phone"):
            parts.append(f"Phone: {lead['phone']} (already shared)")
        if lead.get("preferred_lang"):
            parts.append(f"Language: {lead['preferred_lang']}")
    user_info = ", ".join(parts) if parts else ""

    # Get AI response
    response = await ai_service.get_response(
        conversation_history=history[:-1],  # Exclude the message we just saved
        user_message=user_text,
        lang=lang,
        user_info=user_info,
    )

    # Save assistant response
    await db.save_message(user.id, "assistant", response)

    # Recalculate lead score periodically
    user_msgs = [m for m in history if m["role"] == "user"]
    if len(user_msgs) % 5 == 0:  # Every 5 messages
        await db.recalculate_score(user.id)

    # Send response with back-to-menu button
    await message.answer(
        response,
        reply_markup=back_to_menu_keyboard(lang),
        parse_mode="HTML",
    )
