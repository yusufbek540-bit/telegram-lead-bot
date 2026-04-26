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
    schedule_label = "📅 Записаться на сессию" if lang == "ru" else "📅 Sessiyaga yozilish"
    schedule_url = f"{config.TWA_URL}?tab=schedule&lang={lang}"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=schedule_label, web_app=WebAppInfo(url=schedule_url)),
            ],
            [
                InlineKeyboardButton(
                    text=t("btn_services", lang),
                    web_app=WebAppInfo(url=config.TWA_URL),
                ),
            ],
            [
                InlineKeyboardButton(
                    text=t("btn_my_sessions", lang), callback_data="my_sessions"
                ),
            ],
            [
                InlineKeyboardButton(
                    text=t("btn_live_chat", lang), callback_data="live_chat_request"
                ),
                InlineKeyboardButton(
                    text=t("btn_lang", lang), callback_data="change_lang"
                ),
            ],
        ]
    )


def back_to_menu_keyboard(lang: str = "uz", show_callback: bool = True) -> InlineKeyboardMarkup:
    """Simple "back to menu" button shown after content.

    The `show_callback` flag is retained for back-compat; the callback CTA was
    replaced by the schedule CTA on the main menu, so it now only adds a
    schedule shortcut when requested.
    """
    rows = [[InlineKeyboardButton(text=t("btn_back", lang), callback_data="main_menu")]]
    if show_callback:
        schedule_label = "📅 Выбрать время" if lang == "ru" else "📅 Vaqtni tanlash"
        schedule_url = f"{config.TWA_URL}?tab=schedule&lang={lang}"
        rows.append([
            InlineKeyboardButton(text=schedule_label, web_app=WebAppInfo(url=schedule_url))
        ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


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
