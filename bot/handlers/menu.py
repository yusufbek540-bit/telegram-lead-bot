"""
Menu handler — processes all inline button callbacks.
Services, FAQ, About, Language, Callback Request.
"""

from aiogram import Router, F
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo

from bot.config import config
from bot.texts import t
from bot.services.db_service import db
from bot.keyboards.main_menu import (
    main_menu_keyboard,
    back_to_menu_keyboard,
    contact_keyboard,
    language_keyboard,
)

router = Router()


async def get_lang(telegram_id: int) -> str:
    lead = await db.get_lead(telegram_id)
    if lead and lead.get("preferred_lang"):
        return lead["preferred_lang"]
    return config.DEFAULT_LANG


async def safe_edit(callback: CallbackQuery, text: str, **kwargs):
    """Edit message, silently ignore if content hasn't changed."""
    try:
        await callback.message.edit_text(text, **kwargs)
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            raise


# ── MAIN MENU ─────────────────────────────────────────────

@router.callback_query(F.data == "main_menu")
async def cb_main_menu(callback: CallbackQuery):
    lang = await get_lang(callback.from_user.id)
    await safe_edit(
        callback,
        t("welcome", lang, agency_name=config.AGENCY_NAME),
        reply_markup=main_menu_keyboard(lang),
        parse_mode="HTML",
    )
    await callback.answer()


# ── SERVICES ──────────────────────────────────────────────

@router.callback_query(F.data == "services")
async def cb_services(callback: CallbackQuery):
    lang = await get_lang(callback.from_user.id)
    await db.track_event(callback.from_user.id, "button_click", {"button": "services"})
    await safe_edit(
        callback,
        t("services", lang),
        reply_markup=back_to_menu_keyboard(lang),
        parse_mode="HTML",
    )
    await callback.answer()


# ── FAQ ───────────────────────────────────────────────────

@router.callback_query(F.data == "faq")
async def cb_faq(callback: CallbackQuery):
    lang = await get_lang(callback.from_user.id)
    await db.track_event(callback.from_user.id, "button_click", {"button": "faq"})
    await safe_edit(
        callback,
        t("faq", lang),
        reply_markup=back_to_menu_keyboard(lang),
        parse_mode="HTML",
    )
    await callback.answer()


# ── ABOUT ─────────────────────────────────────────────────

@router.callback_query(F.data == "about")
async def cb_about(callback: CallbackQuery):
    lang = await get_lang(callback.from_user.id)
    await db.track_event(callback.from_user.id, "button_click", {"button": "about"})
    await safe_edit(
        callback,
        t("about", lang, agency_name=config.AGENCY_NAME),
        reply_markup=back_to_menu_keyboard(lang),
        parse_mode="HTML",
    )
    await callback.answer()


# ── CALLBACK REQUEST ──────────────────────────────────────

@router.callback_query(F.data == "callback_request")
async def cb_callback_request(callback: CallbackQuery):
    lang = await get_lang(callback.from_user.id)
    await db.track_event(
        callback.from_user.id, "callback_request", {"button": "callback_request"}
    )

    lead = await db.get_lead(callback.from_user.id)
    if lead and lead.get("phone"):
        text = (
            "✅ Ваш номер у нас уже есть. Мы перезвоним в ближайшее время!"
            if lang == "ru"
            else "✅ Sizning raqamingiz bizda bor. Tez orada qo'ng'iroq qilamiz!"
        )
        await safe_edit(callback, text, reply_markup=back_to_menu_keyboard(lang))
    else:
        # ReplyKeyboard can't be set via edit — send new message, edit current to prompt
        await safe_edit(
            callback,
            t("callback_request", lang),
            parse_mode="HTML",
        )
        await callback.message.answer(
            "👇",
            reply_markup=contact_keyboard(lang),
        )
    await callback.answer()


# ── LANGUAGE SWITCH ───────────────────────────────────────

@router.callback_query(F.data == "change_lang")
async def cb_change_lang(callback: CallbackQuery):
    await safe_edit(
        callback,
        t("choose_lang", "uz"),
        reply_markup=language_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("set_lang_"))
async def cb_set_lang(callback: CallbackQuery):
    lang = callback.data.split("_")[-1]
    await db.update_lead_lang(callback.from_user.id, lang)
    await db.track_event(callback.from_user.id, "lang_switch", {"lang": lang})

    lead = await db.get_lead(callback.from_user.id)
    q_done = lead.get("questionnaire_completed") if lead else False

    if not q_done:
        if lang == "ru":
            twa_msg = "👋 Добро пожаловать! Нажмите кнопку ниже, чтобы пройти короткий опрос — 1 минута."
            btn_text = "📝 Начать опрос"
        else:
            twa_msg = "👋 Xush kelibsiz! Qisqa so'rovnomadan o'tish uchun pastdagi tugmani bosing — 1 daqiqa."
            btn_text = "📝 So'rovnomani boshlash"
        try:
            await callback.message.edit_text(
                "🇺🇿 O'zbekcha" if lang == "uz" else "🇷🇺 Русский"
            )
        except Exception:
            pass
        await callback.message.answer(
            twa_msg,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(
                    text=btn_text,
                    web_app=WebAppInfo(url=f"{config.TWA_URL}?lang={lang}"),
                )
            ]]),
        )
    else:
        await safe_edit(
            callback,
            t("lang_switched", lang) + "\n\n" + t("welcome", lang, agency_name=config.AGENCY_NAME),
            reply_markup=main_menu_keyboard(lang),
            parse_mode="HTML",
        )
    await callback.answer()
