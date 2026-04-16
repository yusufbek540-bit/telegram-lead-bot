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
from bot.handlers import start, menu, contact, ai_chat, admin, twa, live_chat
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
    # 2. Admin commands
    dp.include_router(admin.router)
    # 3. Contact sharing
    dp.include_router(contact.router)
    # 4. TWA data
    dp.include_router(twa.router)
    # 5. Menu button callbacks
    dp.include_router(menu.router)
    # 6. Live chat — must be before ai_chat to intercept messages when active
    dp.include_router(live_chat.router)
    # 7. AI chat (LAST — catches all remaining text messages)
    dp.include_router(ai_chat.router)

    # Set bot commands (visible in Telegram menu)
    from aiogram.types import BotCommand, BotCommandScopeChat

    # Public commands — visible to all users
    await bot.set_my_commands(
        [
            BotCommand(command="start", description="Boshlash / Начать"),
            BotCommand(command="portfolio", description="Portfolio / Портфолио"),
            BotCommand(command="services", description="Xizmatlar / Услуги"),
            BotCommand(command="faq", description="FAQ"),
            BotCommand(command="contact", description="Bog'lanish / Контакт"),
        ]
    )

    # Admin-only commands — shown only in each admin's private chat
    admin_commands = [
        BotCommand(command="start", description="Boshlash / Начать"),
        BotCommand(command="crm", description="CRM Dashboard"),
        BotCommand(command="leads", description="Последние лиды"),
        BotCommand(command="stats", description="Статистика"),
        BotCommand(command="export", description="Экспорт CSV"),
        BotCommand(command="broadcast", description="Рассылка"),
        BotCommand(command="jobs", description="Статус планировщика"),
        BotCommand(command="ask", description="Спросить AI о лидах"),
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

    # Start polling
    try:
        await dp.start_polling(bot)
    finally:
        scheduler.shutdown()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
