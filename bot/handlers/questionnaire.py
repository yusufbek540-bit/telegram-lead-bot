"""
Questionnaire handler — 5-question onboarding flow after /start + language selection.
Uses database-driven state (questionnaire_step column) — no FSM, survives restarts.
"""

import datetime
import logging

from aiogram import Router, F
from aiogram.filters import BaseFilter
from aiogram.types import Message, CallbackQuery

from bot.config import config
from bot.texts import t
from bot.services.db_service import db
from bot.keyboards.main_menu import main_menu_keyboard, remove_keyboard
from bot.keyboards.questionnaire import (
    q1_keyboard, q2_keyboard, q3_keyboard, q4_keyboard, q5_keyboard,
)

logger = logging.getLogger(__name__)
router = Router()


class QStepFilter(BaseFilter):
    """Only match if lead is at the given questionnaire step with optional extra condition."""
    def __init__(self, step: int, biz_type: str = None):
        self.step = step
        self.biz_type = biz_type

    async def __call__(self, message: Message) -> bool:
        lead = await db.get_lead(message.from_user.id)
        if not lead or lead.get("questionnaire_step") != self.step:
            return False
        if self.biz_type and lead.get("business_type") != self.biz_type:
            return False
        return True


# ── Helper: safe edit (suppress "message not modified") ──────────

async def safe_edit(callback, text, reply_markup=None, parse_mode=None):
    try:
        await callback.message.edit_text(text, reply_markup=reply_markup, parse_mode=parse_mode)
    except Exception:
        pass


# ── Show question helpers ────────────────────────────────────────

async def show_q1(target, lang: str):
    """Show Q1 — business type. target is Message or CallbackQuery."""
    text = t("q1_text", lang)
    kb = q1_keyboard(lang)
    if isinstance(target, CallbackQuery):
        await safe_edit(target, text, reply_markup=kb)
    else:
        await target.answer(text, reply_markup=kb)


async def show_q2(callback, lang: str, selected=None):
    text = t("q2_text", lang)
    kb = q2_keyboard(lang, selected or [])
    await safe_edit(callback, text, reply_markup=kb)


async def show_q3(callback, lang: str):
    text = t("q3_text", lang)
    kb = q3_keyboard(lang)
    await safe_edit(callback, text, reply_markup=kb)


async def show_q4(callback, lang: str):
    text = t("q4_text", lang)
    kb = q4_keyboard(lang)
    await safe_edit(callback, text, reply_markup=kb)


async def show_q5(message_or_callback, lang: str):
    """Q5 uses ReplyKeyboard for phone share — must send new message."""
    text = t("q5_text", lang)
    kb = q5_keyboard(lang)
    if isinstance(message_or_callback, CallbackQuery):
        msg = message_or_callback.message
    else:
        msg = message_or_callback
    await msg.answer(text, reply_markup=kb)


async def start_questionnaire(message: Message, lang: str, user_id: int = None):
    """Entry point — show intro + Q1."""
    uid = user_id or message.from_user.id
    await message.answer(t("q_intro", lang))
    await db.update_lead(uid, questionnaire_step=1)
    await db.track_event(uid, "questionnaire_started", {"step": 1})
    await message.answer(t("q1_text", lang), reply_markup=q1_keyboard(lang))


async def resume_questionnaire(message: Message, lang: str, step: int, user_id: int = None):
    """Resume from where the lead left off."""
    uid = user_id or message.from_user.id
    if step <= 1:
        await message.answer(t("q1_text", lang), reply_markup=q1_keyboard(lang))
    elif step == 2:
        lead = await db.get_lead(uid)
        selected = lead.get("service_interest") or []
        await message.answer(t("q2_text", lang), reply_markup=q2_keyboard(lang, selected))
    elif step == 3:
        await message.answer(t("q3_text", lang), reply_markup=q3_keyboard(lang))
    elif step == 4:
        await message.answer(t("q4_text", lang), reply_markup=q4_keyboard(lang))
    elif step == 5:
        await show_q5(message, lang)


async def complete_questionnaire(telegram_id: int, message: Message, lang: str, bot=None):
    """Mark questionnaire as complete, recalculate score, show menu."""
    now = datetime.datetime.now(config.tz).isoformat()
    await db.update_lead(
        telegram_id,
        questionnaire_completed=True,
        questionnaire_completed_at=now,
        questionnaire_step=6,
    )
    await db.track_event(telegram_id, "questionnaire_completed", {})
    await db.recalculate_score(telegram_id)

    await message.answer(t("q_complete", lang), reply_markup=remove_keyboard())
    await message.answer(
        t("welcome", lang, agency_name=config.AGENCY_NAME),
        reply_markup=main_menu_keyboard(lang),
        parse_mode="HTML",
    )

    # Notify admins with rich summary
    the_bot = bot or message.bot
    lead = await db.get_lead(telegram_id)
    if lead:
        await _notify_admins_qualified(the_bot, lead)


async def _notify_admins_qualified(bot, lead):
    from html import escape
    name = escape(f"{lead.get('first_name') or ''} {lead.get('last_name') or ''}".strip() or "\u2014")
    username = escape(lead.get("username") or "\u2014")
    biz_name = escape(lead.get("business_name") or "")
    biz = lead.get("business_type") or "\u2014"
    if biz == "other" and lead.get("business_type_other"):
        biz = escape(lead["business_type_other"])
    services = ", ".join(lead.get("service_interest") or []) or "\u2014"
    mkt_map = {"has_no_results": "Есть, нет результатов", "has_wants_scale": "Есть, хочет масштабировать", "no_marketing": "Нет, с нуля"}
    marketing = mkt_map.get(lead.get("current_marketing"), "\u2014")
    budget = lead.get("budget_range") or "\u2014"
    phone = lead.get("phone") or "\u2014"
    source = lead.get("source") or "organic"
    score = lead.get("lead_score") or 0

    text = (
        "\U0001f4cb <b>Квалифицированный лид!</b>\n\n"
        f"\U0001f464 {name} (@{username})\n"
        f"\U0001f3e2 {biz}" + (f" — {biz_name}" if biz_name else "") + "\n"
        f"\U0001f4cb {services}\n"
        f"\U0001f4ca {marketing}\n"
        f"\U0001f4b0 {budget}\n"
        f"\U0001f4f1 {phone}\n"
        f"\U0001f4ca Источник: {escape(source)}\n"
        f"\u2b50 Score: {score}"
    )

    for admin_id in config.ADMIN_IDS:
        try:
            await bot.send_message(admin_id, text, parse_mode="HTML")
        except Exception as e:
            logger.error(f"Failed to notify admin {admin_id}: {e}")


# ── Q1: Business Type ────────────────────────────────────────────

@router.callback_query(F.data.startswith("q_biz_"))
async def handle_business_type(callback: CallbackQuery):
    biz_type = callback.data.replace("q_biz_", "")
    user_id = callback.from_user.id
    lead = await db.get_lead(user_id)
    lang = lead.get("preferred_lang", config.DEFAULT_LANG) if lead else config.DEFAULT_LANG

    await db.update_lead(user_id, business_type=biz_type)
    await db.track_event(user_id, "questionnaire_q1_answered", {"business_type": biz_type})

    if biz_type == "other":
        await safe_edit(callback, t("q1_other_text", lang))
        await callback.answer()
        return

    await db.update_lead(user_id, questionnaire_step=2)
    await show_q2(callback, lang)
    await callback.answer()


# ── Q1 "Other": free text input ─────────────────────────────────

@router.message(F.text, QStepFilter(step=1, biz_type="other"))
async def handle_other_text(message: Message):
    """Catch free text when waiting for 'other' business type."""
    user_id = message.from_user.id
    lead = await db.get_lead(user_id)
    lang = lead.get("preferred_lang", config.DEFAULT_LANG) if lead else config.DEFAULT_LANG

    await db.update_lead(user_id, business_type_other=message.text.strip(), questionnaire_step=2)
    await db.track_event(user_id, "questionnaire_q1_answered", {"business_type": "other", "other_text": message.text.strip()})

    await message.answer(t("q2_text", lang), reply_markup=q2_keyboard(lang))


# ── Q2: Service Interest (multi-select) ─────────────────────────

@router.callback_query(F.data.startswith("q_svc_") & ~F.data.in_({"q_svc_done"}))
async def handle_service_toggle(callback: CallbackQuery):
    svc_key = callback.data.replace("q_svc_", "")
    user_id = callback.from_user.id
    lead = await db.get_lead(user_id)
    lang = lead.get("preferred_lang", config.DEFAULT_LANG) if lead else config.DEFAULT_LANG
    selected = list(lead.get("service_interest") or []) if lead else []

    if svc_key in selected:
        selected.remove(svc_key)
    else:
        selected.append(svc_key)

    await db.update_lead(user_id, service_interest=selected)
    await show_q2(callback, lang, selected)
    await callback.answer()


@router.callback_query(F.data == "q_svc_done")
async def handle_service_done(callback: CallbackQuery):
    user_id = callback.from_user.id
    lead = await db.get_lead(user_id)
    lang = lead.get("preferred_lang", config.DEFAULT_LANG) if lead else config.DEFAULT_LANG
    selected = lead.get("service_interest") or []

    await db.track_event(user_id, "questionnaire_q2_answered", {"services": selected})
    await db.update_lead(user_id, questionnaire_step=3)
    await show_q3(callback, lang)
    await callback.answer()


# ── Q3: Current Marketing Status ─────────────────────────────────

@router.callback_query(F.data.startswith("q_mkt_"))
async def handle_marketing_status(callback: CallbackQuery):
    mkt_key = callback.data.replace("q_mkt_", "")
    user_id = callback.from_user.id
    lead = await db.get_lead(user_id)
    lang = lead.get("preferred_lang", config.DEFAULT_LANG) if lead else config.DEFAULT_LANG

    await db.update_lead(user_id, current_marketing=mkt_key, questionnaire_step=4)
    await db.track_event(user_id, "questionnaire_q3_answered", {"current_marketing": mkt_key})
    await show_q4(callback, lang)
    await callback.answer()


# ── Q4: Budget Range ─────────────────────────────────────────────

@router.callback_query(F.data.startswith("q_budget_"))
async def handle_budget(callback: CallbackQuery):
    budget_key = callback.data.replace("q_budget_", "")
    user_id = callback.from_user.id
    lead = await db.get_lead(user_id)
    lang = lead.get("preferred_lang", config.DEFAULT_LANG) if lead else config.DEFAULT_LANG

    await db.update_lead(user_id, budget_range=budget_key, questionnaire_step=5)
    await db.track_event(user_id, "questionnaire_q4_answered", {"budget_range": budget_key})
    await show_q5(callback, lang)
    await callback.answer()


# ── Q5: Phone skip via text button ──────────────────────────────

@router.message(F.text.regexp(r"^(\u23ed|Keyinroq|Позже)"), QStepFilter(step=5))
async def handle_phone_skip(message: Message):
    user_id = message.from_user.id
    lead = await db.get_lead(user_id)
    lang = lead.get("preferred_lang", config.DEFAULT_LANG) if lead else config.DEFAULT_LANG

    await db.track_event(user_id, "questionnaire_q5_answered", {"phone_skipped": True})
    await complete_questionnaire(user_id, message, lang)
