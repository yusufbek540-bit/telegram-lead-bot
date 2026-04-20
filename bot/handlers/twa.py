"""
TWA handler — receives data sent from the Telegram Web App.
"""

import json
from aiogram import Router, F
from aiogram.types import Message

from bot.config import config
from bot.texts import t
from bot.services.db_service import db
from bot.keyboards.main_menu import main_menu_keyboard

router = Router()


@router.message(F.web_app_data)
async def handle_web_app_data(message: Message):
    """Handle data sent from the Telegram Web App."""
    try:
        data = json.loads(message.web_app_data.data)
    except json.JSONDecodeError:
        return

    user = message.from_user
    action = data.get("action", "unknown")

    # Get language
    lead = await db.get_lead(user.id)
    lang = lead.get("preferred_lang", config.DEFAULT_LANG) if lead else config.DEFAULT_LANG

    # Track TWA interaction
    await db.track_event(user.id, "twa_action", data)

    if action == "contact_form":
        # Update lead with form data
        update_data = {}
        if data.get("phone"):
            update_data["phone"] = data["phone"]
        if data.get("email"):
            update_data["email"] = data["email"]
        if update_data:
            await db.update_lead(user.id, **update_data)

        # Recalculate score
        await db.recalculate_score(user.id)

        if lang == "ru":
            text = "✅ Спасибо! Данные получены. Мы свяжемся с вами в ближайшее время."
        else:
            text = "✅ Rahmat! Ma'lumotlar qabul qilindi. Tez orada bog'lanamiz."

        await message.answer(text, reply_markup=main_menu_keyboard(lang), parse_mode="HTML")

        # Notify admins
        for admin_id in config.ADMIN_IDS:
            try:
                name = f"{user.first_name or ''} {user.last_name or ''}".strip()
                await message.bot.send_message(
                    admin_id,
                    f"🌐 TWA форма!\n\n"
                    f"👤 {name} @{user.username or '—'}\n"
                    f"📱 {data.get('phone', '—')}\n"
                    f"📧 {data.get('email', '—')}\n"
                    f"💬 {data.get('interest', '—')}",
                )
            except Exception:
                pass

    elif action == "questionnaire_complete":
        twa_lang = data.get("lang", "uz")
        if twa_lang not in ("uz", "ru"):
            twa_lang = "uz"

        updates: dict = {"preferred_lang": twa_lang}
        if data.get("business_type"):
            updates["business_type"] = data["business_type"]
        if data.get("service_interest"):
            updates["service_interest"] = data["service_interest"]
        if data.get("current_marketing"):
            updates["current_marketing"] = data["current_marketing"]
        if data.get("budget_range"):
            updates["budget_range"] = data["budget_range"]
        if data.get("phone"):
            updates["phone"] = data["phone"]
        if data.get("name"):
            updates["first_name"] = data["name"]

        import datetime
        now = datetime.datetime.now(config.tz).isoformat()
        updates.update({
            "questionnaire_completed": True,
            "questionnaire_completed_at": now,
            "questionnaire_step": 6,
        })

        await db.update_lead(user.id, **updates)
        await db.track_event(user.id, "twa_questionnaire_complete", {
            "business_type": data.get("business_type"),
            "services": data.get("service_interest"),
        })
        await db.recalculate_score(user.id)

        from bot.handlers.questionnaire import _notify_admins_qualified
        updated_lead = await db.get_lead(user.id)
        if updated_lead:
            await _notify_admins_qualified(message.bot, updated_lead)

        if twa_lang == "ru":
            confirm = "✅ Спасибо! Мы скоро свяжемся с вами."
        else:
            confirm = "✅ Rahmat! Tez orada bog'lanamiz."

        await message.answer(confirm)
        await message.answer(
            t("welcome", twa_lang, agency_name=config.AGENCY_NAME),
            reply_markup=main_menu_keyboard(twa_lang),
            parse_mode="HTML",
        )

    elif action == "twa_opened":
        await db.track_event(user.id, "twa_open", {})

    elif action == "service_clicked":
        await db.track_event(
            user.id, "twa_service_click", {"service": data.get("service", "")}
        )
