"""
AI Chat handler — catches all free-text messages and responds via Claude.
This is registered LAST so buttons and commands take priority.
"""

from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

from bot.config import config
from bot.services.db_service import db
from bot.services.ai_service import ai_service
from bot.keyboards.main_menu import back_to_menu_keyboard
from bot.texts import t

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
        biz = lead.get("business_type")
        if biz:
            biz_str = lead.get("business_type_other") if biz == "other" else biz
            parts.append(f"Business: {biz_str or 'other'}")
        svc = lead.get("service_interest")
        if svc:
            parts.append(f"Interested in: {', '.join(svc)}")
        mkt = lead.get("current_marketing")
        if mkt:
            parts.append(f"Current marketing: {mkt}")
        budget = lead.get("budget_range")
        if budget:
            parts.append(f"Budget range: {budget}")
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

    # Append AI disclaimer + escalation CTA to every AI reply.
    if lang == "ru":
        disclaimer = (
            "\n\n<i>🤖 Это сообщение от AI-бота. Нужен живой менеджер? "
            "Нажмите кнопку ниже, чтобы открыть live-чат.</i>"
        )
        live_btn_text = "💬 Связаться с менеджером"
    else:
        disclaimer = (
            "\n\n<i>🤖 Bu xabar AI-bot tomonidan yuborildi. Jonli menejer kerakmi? "
            "Live-chatni ochish uchun quyidagi tugmani bosing.</i>"
        )
        live_btn_text = "💬 Menejer bilan bog'lanish"

    has_phone = bool(lead and lead.get("phone"))
    back_kb = back_to_menu_keyboard(lang, show_callback=not has_phone)
    rows = [
        [InlineKeyboardButton(text=live_btn_text, callback_data="live_chat_request")],
        *back_kb.inline_keyboard,
    ]
    await message.answer(
        response + disclaimer,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
        parse_mode="HTML",
    )
