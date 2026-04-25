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


# ── Audit-shape value translation ──────────────────────────────
# The TWA form may post either new audit-shaped keys (q_v_*, q_spend_*,
# q_ch_*, q_crm_*) OR legacy values from a cached HTML build (health,
# realestate, smm, has_no_results, 1000_1500, etc.). Normalize either
# shape to the new keys so scoring + admin labels behave correctly.

_VERTICAL_LEGACY = {
    "realestate": "q_v_realestate",
    "health": "q_v_clinic",
    "education": "q_v_education",
    "consulting": "q_v_education",
    # everything else collapses to "other" (B2B, e-com, HoReCa, etc. = inbound only)
}

_SPEND_LEGACY = {
    "1000_1500": "q_spend_1k_3k",
    "2000_3000": "q_spend_1k_3k",
    "3000_5000": "q_spend_3k_10k",
    "5000_plus": "q_spend_10k_plus",
}

_CHANNEL_LEGACY = {
    "smm": "organic",
    "targeting": "meta",
    "bot": "organic",
    "production": "organic",
    "branding": "organic",
    "website": "organic",
    "ai": "organic",
    "consulting": "organic",
}

_CRM_LEGACY = {
    "no_marketing": "q_crm_no",
    "has_no_results": "q_crm_sheet",
    "has_wants_scale": "q_crm_yes",
}


def _normalize_vertical(v: str | None) -> str | None:
    if not v:
        return None
    if v.startswith("q_v_"):
        return v
    return _VERTICAL_LEGACY.get(v, "q_v_other")


def _normalize_spend(v: str | None) -> str | None:
    if not v:
        return None
    if v.startswith("q_spend_"):
        return v
    return _SPEND_LEGACY.get(v)


def _normalize_channels(arr) -> list:
    if not arr:
        return []
    out = []
    seen = set()
    for v in arr:
        if not v:
            continue
        key = v if v.startswith("q_ch_") else "q_ch_" + _CHANNEL_LEGACY.get(v, "organic")
        # also accept short keys like "meta", "google", etc.
        if not v.startswith("q_ch_") and v in {"meta", "google", "telegram", "organic", "offline", "none"}:
            key = "q_ch_" + v
        if key in seen:
            continue
        seen.add(key)
        out.append(key.replace("q_ch_", ""))
    return out


def _normalize_crm(v: str | None) -> str | None:
    if not v:
        return None
    if v.startswith("q_crm_"):
        return v
    return _CRM_LEGACY.get(v)


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
        if data.get("name"):
            lead = await db.get_lead(user.id)
            if not (lead and lead.get("first_name")):
                update_data["first_name"] = data["name"]
        if data.get("interest"):
            update_data["service_interest"] = [data["interest"]]
        if update_data:
            await db.update_lead(user.id, **update_data)

        # Recalculate score
        await db.recalculate_score(user.id)

        if lang == "ru":
            text = "Спасибо. Данные получены — партнёр свяжется в течение 24 часов."
        else:
            text = "Rahmat. Ma'lumotlar qabul qilindi — partnyor 24 soat ichida bog'lanadi."

        await message.answer(text, reply_markup=main_menu_keyboard(lang), parse_mode="HTML")

        # Notify admins
        for admin_id in config.ADMIN_IDS:
            try:
                name = f"{user.first_name or ''} {user.last_name or ''}".strip() or "—"
                await message.bot.send_message(
                    admin_id,
                    "<b>Заявка с TWA</b>\n\n"
                    f"Имя: {name} (@{user.username or '—'})\n"
                    f"Телефон: {data.get('phone', '—')}\n"
                    f"Email: {data.get('email', '—')}\n"
                    f"Интерес: {data.get('interest', '—')}",
                    parse_mode="HTML",
                )
            except Exception:
                pass

    elif action == "questionnaire_complete":
        twa_lang = data.get("lang", "uz")
        if twa_lang not in ("uz", "ru"):
            twa_lang = "uz"

        updates: dict = {"preferred_lang": twa_lang}

        vertical = _normalize_vertical(data.get("business_type"))
        if vertical:
            updates["business_type"] = vertical

        spend = _normalize_spend(data.get("budget_range"))
        if spend:
            updates["budget_range"] = spend

        channels = _normalize_channels(data.get("service_interest"))
        if channels:
            updates["service_interest"] = channels

        crm = _normalize_crm(data.get("current_marketing"))
        if crm:
            updates["current_marketing"] = crm

        if data.get("phone"):
            updates["phone"] = data["phone"]
        if data.get("name"):
            updates["first_name"] = data["name"]
        if data.get("business_name"):
            # business_name now carries the top-problem text (audit-shape).
            updates["business_name"] = data["business_name"]

        import datetime
        now = datetime.datetime.now(config.tz).isoformat()
        updates.update({
            "questionnaire_completed": True,
            "questionnaire_completed_at": now,
            "questionnaire_step": 7,
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

        # Contact flow:
        # - If the user shared contact via TWA's native requestContact popup,
        #   Telegram delivers a Contact message to the bot which contact.py
        #   handles — it sends the welcome + main menu itself. Nothing to do here.
        # - If the user skipped sharing and no phone is on file, we send the
        #   welcome + main menu now so the user lands somewhere useful.
        contact_shared = bool(data.get("contact_shared"))
        has_phone = bool(updated_lead and updated_lead.get("phone"))
        if not contact_shared and not has_phone:
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

    elif action == "live_chat_request":
        msg_text = data.get("message", "").strip()
        if not msg_text:
            return

        await db.update_lead(user.id, live_chat=True)
        await db.track_event(user.id, "live_chat_requested", {"source": "twa"})
        await db.save_message(user.id, "user", msg_text, source="live_chat")

        from bot.handlers.live_chat import _notify_managers
        fresh_lead = await db.get_lead(user.id)
        await _notify_managers(message.bot, fresh_lead, message_text=msg_text)

        if lang == "ru":
            confirm = "✅ Сообщение отправлено! Мы ответим в Telegram в ближайшее время."
        else:
            confirm = "✅ Xabaringiz yuborildi! Tez orada Telegram orqali javob beramiz."
        await message.answer(confirm)
