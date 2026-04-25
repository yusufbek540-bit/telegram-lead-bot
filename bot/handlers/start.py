"""
/start handler — entry point for all leads.
Parses deep link parameters, captures lead, sends welcome.
"""

from aiogram import Router
from aiogram.filters import CommandStart, CommandObject, Command
from aiogram.types import Message

from bot.config import config
from bot.texts import t
from bot.services.db_service import db
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton, WebAppInfo
from bot.keyboards.main_menu import main_menu_keyboard, back_to_menu_keyboard, contact_keyboard, language_keyboard

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message, command: CommandObject):
    """Handle /start and /start <deep_link_param>."""
    user = message.from_user

    # Extract source from deep link: t.me/botname?start=meta_campaign1
    source = command.args if command.args else "organic"

    # Check if returning user BEFORE upsert
    existing_lead = await db.get_lead(user.id)
    is_new = existing_lead is None
    has_lang = existing_lead and existing_lead.get("preferred_lang")

    source_to_save = source if (is_new or source != "organic") else None
    await db.upsert_lead(
        telegram_id=user.id,
        first_name=user.first_name,
        last_name=user.last_name,
        username=user.username,
        language_code=user.language_code,
        source=source_to_save,
    )

    # Telemetry: Touchpoints and Original Source
    import datetime
    now_iso = datetime.datetime.now(config.tz).isoformat()
    if is_new:
        db.supabase.table("leads").update({
            "original_source": source,
            "touchpoints": [{"source": source, "timestamp": now_iso}]
        }).eq("telegram_id", user.id).execute()
    elif source != "organic":
        # Returning user with a distinct deep link — append touchpoint
        tps = existing_lead.get("touchpoints") or []
        # Prevent rapid duplicate logging
        if not tps or tps[-1].get("source") != source or (datetime.datetime.now(config.tz) - datetime.datetime.fromisoformat(tps[-1].get("timestamp", now_iso))).total_seconds() > 3600:
            tps.append({"source": source, "timestamp": now_iso})
            db.supabase.table("leads").update({"touchpoints": tps}).eq("telegram_id", user.id).execute()

    # Track event
    await db.track_event(user.id, "bot_start", {"source": source})

    if not has_lang:
        # First time — ask language once
        await message.answer(
            t("choose_lang", "uz"),
            reply_markup=language_keyboard(),
        )
        if is_new:
            from bot.services.routing import route_new_lead
            assigned = await route_new_lead(user.id, source_to_save or "organic")
            await notify_admins_new_lead(message, user, source, assigned)
    else:
        lang = existing_lead["preferred_lang"]
        q_done = (
            existing_lead.get("questionnaire_completed")
            or bool(existing_lead.get("phone"))
            or (existing_lead.get("questionnaire_step") or 0) >= 7
        )
        if not q_done:
            if lang == "ru":
                twa_msg = (
                    "Чтобы подготовить ваш бесплатный аудит, ответьте "
                    "на 5 коротких вопросов — около минуты."
                )
                btn_text = "Запросить бесплатный аудит"
            else:
                twa_msg = (
                    "Bepul auditni tayyorlashimiz uchun 5 ta qisqa savolga "
                    "javob bering — taxminan 1 daqiqa."
                )
                btn_text = "Bepul auditni so'rash"
            await message.answer(
                twa_msg,
                reply_markup=ReplyKeyboardMarkup(
                    keyboard=[[KeyboardButton(
                        text=btn_text,
                        web_app=WebAppInfo(url=f"{config.TWA_URL}?lang={lang}")
                    )]],
                    resize_keyboard=True,
                    one_time_keyboard=False,
                ),
            )
        else:
            await message.answer(
                t("welcome", lang, agency_name=config.AGENCY_NAME),
                reply_markup=main_menu_keyboard(lang),
                parse_mode="HTML",
            )


@router.message(Command("contact"))
async def cmd_contact(message: Message):
    lead = await db.get_lead(message.from_user.id)
    lang = lead.get("preferred_lang", config.DEFAULT_LANG) if lead else config.DEFAULT_LANG
    if lead and lead.get("phone"):
        text = "✅ Sizning raqamingiz bizda bor. Tez orada qo'ng'iroq qilamiz!" if lang == "uz" else "✅ Ваш номер у нас уже есть. Мы перезвоним в ближайшее время!"
        await message.answer(text, reply_markup=back_to_menu_keyboard(lang))
    else:
        await message.answer(t("callback_request", lang), reply_markup=contact_keyboard(lang), parse_mode="HTML")


@router.message(Command("services"))
async def cmd_services(message: Message):
    lead = await db.get_lead(message.from_user.id)
    lang = lead.get("preferred_lang", config.DEFAULT_LANG) if lead else config.DEFAULT_LANG
    await message.answer(t("services", lang), reply_markup=back_to_menu_keyboard(lang), parse_mode="HTML")




@router.message(Command("faq"))
async def cmd_faq(message: Message):
    lead = await db.get_lead(message.from_user.id)
    lang = lead.get("preferred_lang", config.DEFAULT_LANG) if lead else config.DEFAULT_LANG
    await message.answer(t("faq", lang), reply_markup=back_to_menu_keyboard(lang), parse_mode="HTML")


@router.message(Command("language", "lang"))
async def cmd_language(message: Message):
    await message.answer(t("choose_lang", "uz"), reply_markup=language_keyboard())


@router.message(Command("app", "portfolio"))
async def cmd_portfolio(message: Message):
    lead = await db.get_lead(message.from_user.id)
    lang = lead.get("preferred_lang", config.DEFAULT_LANG) if lead else config.DEFAULT_LANG

    if lang == "ru":
        lines = [
            "✨ <b>MQSD App</b>",
            (
                "Внутри — услуги, кейсы, тарифы и прямой чат с менеджером.\n\n"
                "SMM · AI-контент · автоматизация · продакшн — всё в одном приложении."
            ),
            "Открывайте 👇",
        ]
        btn_text = "✨ Открыть MQSD"
    else:
        lines = [
            "✨ <b>MQSD App</b>",
            (
                "Ichida — xizmatlar, keyslar, tariflar va menejer bilan to'g'ridan-to'g'ri chat.\n\n"
                "SMM · AI-kontent · avtomatizatsiya · prodakshn — hammasi bir ilovada."
            ),
            "Oching 👇",
        ]
        btn_text = "✨ MQSD ni ochish"

    for i, text in enumerate(lines):
        is_last = i == len(lines) - 1
        await message.answer(
            text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text=btn_text, web_app=WebAppInfo(url=config.TWA_URL))
            ]]) if is_last else None,
            parse_mode="HTML",
        )


async def notify_admins_new_lead(message: Message, user, source: str, assigned: str = None):
    """Notify all admins about a new lead."""
    from html import escape
    import logging
    name = escape(f"{user.first_name or ''} {user.last_name or ''}".strip() or "—")
    username = escape(user.username or "—")
    lang = escape(user.language_code or "—")

    if source == "organic":
        text = t("admin_new_lead_organic", "ru", name=name, username=username, lang=lang)
    else:
        text = t("admin_new_lead", "ru", name=name, username=username, phone="—", source=escape(source))

    if assigned:
        text += f"\n👤 <b>Назначен:</b> {escape(assigned)}"

    for admin_id in config.ADMIN_IDS:
        try:
            await message.bot.send_message(admin_id, text, parse_mode="HTML")
        except Exception as e:
            logging.getLogger(__name__).error(f"Failed to notify admin {admin_id}: {e}")
