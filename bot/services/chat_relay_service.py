"""
Chat Relay Service — forwards messages sent from the CRM to users via Telegram.
"""
import asyncio
import logging
from aiogram import Bot
from bot.services.db_service import db

logger = logging.getLogger(__name__)

async def run_chat_relay(bot: Bot) -> None:
    """
    Background job: check for any assistant messages in conversations 
    that haven't been sent to users yet (is_sent=False).
    """
    logger.debug("Running chat relay check...")
    try:
        pending = await db.get_pending_assistant_messages()
        if not pending:
            return

        logger.info(f"ChatRelay: Found {len(pending)} pending message(s) to relay")
        
        for msg in pending:
            try:
                await bot.send_message(
                    chat_id=msg["telegram_id"],
                    text=msg["message"],
                    parse_mode="HTML"
                )
                await db.mark_message_sent(msg["id"])
                logger.info(f"Relayed message {msg['id']} to user {msg['telegram_id']}")
            except Exception as e:
                logger.error(f"Failed to relay message {msg['id']} to {msg['telegram_id']}: {e}")
                # We don't mark as sent, so it will retry next time. 
                # Consider adding a failure count to avoid infinite loops if user blocked bot.

    except Exception as e:
        logger.error(f"Chat relay loop error: {e}", exc_info=True)
