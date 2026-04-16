"""
Keyboard layouts — all inline and reply keyboards.
"""

from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardRemove,
    WebAppInfo,
)
from bot.config import config
from bot.texts import t


def main_menu_keyboard(lang: str = "uz") -> InlineKeyboardMarkup:
    """Main menu with all primary actions."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=t("btn_services", lang), callback_data="services"
                ),
                InlineKeyboardButton(
                    text=t("btn_portfolio", lang),
                    web_app=WebAppInfo(url=config.TWA_URL),
                ),
            ],
            [
                InlineKeyboardButton(
                    text=t("btn_lang", lang), callback_data="change_lang"
                ),
                InlineKeyboardButton(
                    text=t("btn_live_chat", lang), callback_data="live_chat_request"
                ),
            ],
            [
                InlineKeyboardButton(
                    text=t("btn_callback", lang), callback_data="callback_request"
                ),
            ],
        ]
    )


def back_to_menu_keyboard(lang: str = "uz") -> InlineKeyboardMarkup:
    """Simple "back to menu" button shown after content."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=t("btn_back", lang), callback_data="main_menu"
                ),
            ],
            [
                InlineKeyboardButton(
                    text=t("btn_callback", lang), callback_data="callback_request"
                ),
            ],
        ]
    )


def contact_keyboard(lang: str = "uz") -> ReplyKeyboardMarkup:
    """Phone number sharing keyboard (native Telegram contact share)."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(
                    text=t("btn_share_phone", lang),
                    request_contact=True,
                )
            ]
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def language_keyboard() -> InlineKeyboardMarkup:
    """Language selection keyboard."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🇺🇿 O'zbekcha", callback_data="set_lang_uz"
                ),
                InlineKeyboardButton(
                    text="🇷🇺 Русский", callback_data="set_lang_ru"
                ),
            ],
        ]
    )


def remove_keyboard() -> ReplyKeyboardRemove:
    """Remove any reply keyboard."""
    return ReplyKeyboardRemove()
