"""
Main entry point — initializes the bot and registers all handlers.

Run with: python -m bot.main
"""

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

from bot.config import config

# Import all routers
from bot.handlers import start, questionnaire, menu, contact, ai_chat, admin, twa, live_chat, booking_reminder
from bot.services.scheduler_service import create_scheduler


async def main():
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    logger = logging.getLogger(__name__)

    # Initialize bot
    bot = Bot(
        token=config.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    # Initialize dispatcher
    dp = Dispatcher()

    # Register routers IN ORDER (first match wins)
    # 1. Start command (highest priority)
    dp.include_router(start.router)
    # 2. Questionnaire (q_ callbacks + "other" text input + phone skip)
    dp.include_router(questionnaire.router)
    # 3. Admin commands
    dp.include_router(admin.router)
    # 4. Contact sharing
    dp.include_router(contact.router)
    # 5. TWA data
    dp.include_router(twa.router)
    # 6. Menu button callbacks
    dp.include_router(menu.router)
    # 7. Live chat — must be before partner-handoff to intercept active sessions
    dp.include_router(live_chat.router)
    # 7.5 Booking reminder callbacks (bk_confirm/bk_cancel/bk_resched)
    dp.include_router(booking_reminder.router)
    # 8. Partner-handoff catch-all (LAST — any unmatched text goes to a manager)
    dp.include_router(ai_chat.router)

    # Restore default menu button so the bot's command list (/start, /portfolio, etc.)
    # is visible. The TWA is launched instead via KeyboardButton/InlineKeyboardButton
    # flows, and live-chat messaging goes through the /api/live-chat endpoint
    # (bypasses sendData's launch-context restriction).
    from aiogram.types import MenuButtonCommands
    try:
        await bot.set_chat_menu_button(menu_button=MenuButtonCommands())
        logger.info("Menu button set to command list")
    except Exception as e:
        logger.warning(f"Could not set menu button: {e}")

    # Set bot commands (visible in Telegram menu)
    from aiogram.types import BotCommand, BotCommandScopeChat

    # Public commands — visible to all users
    await bot.set_my_commands(
        [
            BotCommand(command="start", description="Boshlash / Начать"),
            BotCommand(command="app", description="MQSD App — xizmatlar va keyslar / услуги и кейсы"),
            BotCommand(command="contact", description="Bog'lanish / Контакт"),
            BotCommand(command="language", description="Tilni o'zgartirish / Сменить язык"),
        ]
    )

    # Admin-only commands — shown only in each admin's private chat
    admin_commands = [
        BotCommand(command="start", description="Boshlash / Начать"),
        BotCommand(command="app", description="MQSD App"),
        BotCommand(command="contact", description="Контакт"),
        BotCommand(command="language", description="Сменить язык"),
        BotCommand(command="crm", description="CRM Dashboard"),
        BotCommand(command="leads", description="Последние лиды"),
        BotCommand(command="stats", description="Статистика"),
        BotCommand(command="export", description="Экспорт CSV"),
        BotCommand(command="broadcast", description="Рассылка"),
        BotCommand(command="jobs", description="Статус планировщика"),
        BotCommand(command="ask", description="Запрос к CRM (внутр.)"),
    ]
    for admin_id in config.ADMIN_IDS:
        try:
            await bot.set_my_commands(admin_commands, scope=BotCommandScopeChat(chat_id=admin_id))
        except Exception:
            pass  # admin may not have started the bot yet

    # Start scheduler
    scheduler = create_scheduler(bot)
    scheduler.start()

    logger.info("Bot starting...")
    logger.info(f"Admin IDs: {config.ADMIN_IDS}")

    logger.info("Bot starting. Polling with auto-restart on error.")

    # Polling with auto-restart — if polling drops due to a network blip or
    # unhandled exception, wait 5s and resume rather than dying silently.
    while True:
        try:
            await dp.start_polling(bot, handle_signals=False)
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Polling crashed: {e}. Restarting in 5s…", exc_info=True)
            await asyncio.sleep(5)

    scheduler.shutdown()
    await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
