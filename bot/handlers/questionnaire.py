"""
Free Audit qualification flow.

Five audit-shaped questions, no phone step (phone is opt-in via the menu after).
Database-driven state via leads.questionnaire_step — survives restarts.

Step semantics:
    1 = vertical                       (callback q_v_*)
    2 = monthly ad spend               (callback q_spend_*)
    3 = current channels (multi)       (callbacks q_ch_*, finalized by q_ch_done)
    4 = CRM status                     (callback q_crm_*)
    5 = top problem (free text)        (text message OR q_problem_skip)
    6 = phone share                    (Contact OR "later" reply text)
    7 = complete
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
    q1_keyboard, q2_keyboard, q3_keyboard, q4_keyboard,
    q5b_skip_keyboard, q5c_skip_keyboard, q6_phone_keyboard,
)


# Module-level: track the Q5 sub-step per user. Resets on questionnaire restart.
_q5_substep: dict[int, str] = {}  # telegram_id -> 'awaiting_biz' | 'awaiting_web' | 'awaiting_social'

logger = logging.getLogger(__name__)
router = Router()


class QStepFilter(BaseFilter):
    """Match only when the lead's questionnaire_step equals self.step."""
    def __init__(self, step: int):
        self.step = step

    async def __call__(self, message: Message) -> bool:
        lead = await db.get_lead(message.from_user.id)
        if not lead or lead.get("questionnaire_step") != self.step:
            return False
        return True


# ── Helpers ──────────────────────────────────────────────────────

async def safe_edit(callback, text, reply_markup=None, parse_mode=None):
    try:
        await callback.message.edit_text(text, reply_markup=reply_markup, parse_mode=parse_mode)
    except Exception:
        pass


async def show_q1(target, lang: str):
    text = t("q1_text", lang)
    kb = q1_keyboard(lang)
    if isinstance(target, CallbackQuery):
        await safe_edit(target, text, reply_markup=kb)
    else:
        await target.answer(text, reply_markup=kb)


async def show_q2(callback, lang: str):
    await safe_edit(callback, t("q2_text", lang), reply_markup=q2_keyboard(lang))


async def show_q3(callback, lang: str, selected=None):
    await safe_edit(callback, t("q3_text", lang), reply_markup=q3_keyboard(lang, selected or []))


async def show_q4(callback, lang: str):
    await safe_edit(callback, t("q4_text", lang), reply_markup=q4_keyboard(lang))


async def show_q5(callback, lang: str):
    """Q5a = business name (required free text). No reply markup — must be answered."""
    await safe_edit(callback, t("q5a_prompt", lang))


async def show_q6(message_or_callback, lang: str):
    """Q6 = phone share. ReplyKeyboard requires a new message (can't edit)."""
    if isinstance(message_or_callback, CallbackQuery):
        msg = message_or_callback.message
    else:
        msg = message_or_callback
    await msg.answer(t("q6_text", lang), reply_markup=q6_phone_keyboard(lang))


async def start_questionnaire(message: Message, lang: str, user_id: int = None):
    uid = user_id or message.from_user.id
    await message.answer(t("q_intro", lang))
    await db.update_lead(uid, questionnaire_step=1)
    await db.track_event(uid, "questionnaire_started", {"step": 1})
    await message.answer(t("q1_text", lang), reply_markup=q1_keyboard(lang))


async def resume_questionnaire(message: Message, lang: str, step: int, user_id: int = None):
    uid = user_id or message.from_user.id
    if step <= 1:
        await message.answer(t("q1_text", lang), reply_markup=q1_keyboard(lang))
    elif step == 2:
        await message.answer(t("q2_text", lang), reply_markup=q2_keyboard(lang))
    elif step == 3:
        lead = await db.get_lead(uid)
        selected = lead.get("service_interest") or [] if lead else []
        await message.answer(t("q3_text", lang), reply_markup=q3_keyboard(lang, selected))
    elif step == 4:
        await message.answer(t("q4_text", lang), reply_markup=q4_keyboard(lang))
    elif step == 5:
        sub = _q5_substep.get(uid, "awaiting_biz")
        if sub == "awaiting_web":
            await message.answer(t("q5b_prompt", lang), reply_markup=q5b_skip_keyboard(lang))
        elif sub == "awaiting_social":
            await message.answer(t("q5c_prompt", lang), reply_markup=q5c_skip_keyboard(lang))
        else:
            _q5_substep[uid] = "awaiting_biz"
            await message.answer(t("q5a_prompt", lang))
    elif step == 6:
        await message.answer(t("q6_text", lang), reply_markup=q6_phone_keyboard(lang))


async def complete_questionnaire(telegram_id: int, message: Message, lang: str, bot=None):
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
    now = datetime.datetime.now(config.tz).isoformat()
    await db.update_lead(
        telegram_id,
        questionnaire_completed=True,
        questionnaire_completed_at=now,
        questionnaire_step=7,
    )
    await db.track_event(telegram_id, "questionnaire_completed", {})
    await db.recalculate_score(telegram_id)

    # 1) Completion ack — clears any active ReplyKeyboard
    await message.answer(t("q_complete", lang), reply_markup=remove_keyboard())

    # 2) Schedule CTA — inline button can't co-exist with ReplyKeyboardRemove
    schedule_label = "Выбрать время" if lang == "ru" else "Vaqtni tanlash"
    await message.answer(
        "👇",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(
                text=schedule_label,
                web_app=WebAppInfo(url=f"{config.TWA_URL}?tab=schedule&lang={lang}"),
            )
        ]]),
    )

    # 3) Main menu (schedule button is also there but other actions matter too)
    await message.answer(
        t("welcome", lang, agency_name=config.AGENCY_NAME),
        reply_markup=main_menu_keyboard(lang),
        parse_mode="HTML",
    )

    the_bot = bot or message.bot
    lead = await db.get_lead(telegram_id)
    if lead:
        await _notify_admins_qualified(the_bot, lead)


# ── Admin notification ──────────────────────────────────────────

VERTICAL_LABELS = {
    "q_v_realestate": "Жилая недвижимость / девелопмент",
    "q_v_clinic": "Частная медицинская клиника",
    "q_v_education": "Образование / коучинг",
    "q_v_other": "Другое направление",
}
SPEND_LABELS = {
    "q_spend_none": "Реклама пока не запущена",
    "q_spend_lt1k": "До $1 000",
    "q_spend_1k_3k": "$1 000 — $3 000",
    "q_spend_3k_10k": "$3 000 — $10 000",
    "q_spend_10k_plus": "$10 000+",
}
CHANNEL_LABELS = {
    "meta": "Meta Ads",
    "google": "Google Ads",
    "telegram": "Telegram",
    "organic": "Органический контент",
    "offline": "Офлайн",
    "none": "Ничего не работает",
}
CRM_LABELS = {
    "q_crm_yes": "Полноценная CRM",
    "q_crm_sheet": "Excel / Google Sheets",
    "q_crm_no": "Учёта нет",
}


async def _notify_admins_qualified(bot, lead):
    from html import escape
    name = escape(f"{lead.get('first_name') or ''} {lead.get('last_name') or ''}".strip() or "—")
    username = escape(lead.get("username") or "—")
    vertical = VERTICAL_LABELS.get(lead.get("business_type"), "—")
    spend = SPEND_LABELS.get(lead.get("budget_range"), "—")
    channels_raw = lead.get("service_interest") or []
    channels = ", ".join(CHANNEL_LABELS.get(c, c) for c in channels_raw) or "—"
    crm = CRM_LABELS.get(lead.get("current_marketing"), "—")
    biz = escape(lead.get("business_name") or "—")
    web = escape(lead.get("website") or "—")
    social = escape(lead.get("social_handle") or "—")
    phone = lead.get("phone") or "—"
    source = escape(lead.get("source") or "organic")
    score = lead.get("lead_score") or 0

    text = (
        "<b>Новая заявка — анкета пройдена</b>\n\n"
        f"Имя: <b>{name}</b> (@{username})\n"
        f"Направление: {escape(vertical)}\n"
        f"Бюджет на рекламу: {escape(spend)}\n"
        f"Каналы: {escape(channels)}\n"
        f"CRM: {escape(crm)}\n"
        f"<b>Бизнес:</b> {biz}\n"
        f"<b>Сайт:</b> {web}\n"
        f"<b>Соцсети:</b> {social}\n"
        f"Телефон: {phone}\n"
        f"Источник: {source}\n"
        f"Баллы: {score}"
    )

    for admin_id in config.ADMIN_IDS:
        try:
            await bot.send_message(admin_id, text, parse_mode="HTML")
        except Exception as e:
            logger.error(f"Failed to notify admin {admin_id}: {e}")


# ── Q1: Vertical ────────────────────────────────────────────────

@router.callback_query(F.data.startswith("q_v_"))
async def handle_vertical(callback: CallbackQuery):
    user_id = callback.from_user.id
    lead = await db.get_lead(user_id)
    lang = lead.get("preferred_lang", config.DEFAULT_LANG) if lead else config.DEFAULT_LANG

    await db.update_lead(user_id, business_type=callback.data, questionnaire_step=2)
    await db.track_event(user_id, "questionnaire_q1_answered", {"vertical": callback.data})
    await show_q2(callback, lang)
    await callback.answer()


# ── Q2: Ad spend ───────────────────────────────────────────────

@router.callback_query(F.data.startswith("q_spend_"))
async def handle_spend(callback: CallbackQuery):
    user_id = callback.from_user.id
    lead = await db.get_lead(user_id)
    lang = lead.get("preferred_lang", config.DEFAULT_LANG) if lead else config.DEFAULT_LANG

    await db.update_lead(user_id, budget_range=callback.data, questionnaire_step=3)
    await db.track_event(user_id, "questionnaire_q2_answered", {"ad_spend": callback.data})
    await show_q3(callback, lang)
    await callback.answer()


# ── Q3: Channels (multi-select) ────────────────────────────────

@router.callback_query(F.data.startswith("q_ch_") & ~F.data.in_({"q_ch_done"}))
async def handle_channel_toggle(callback: CallbackQuery):
    ch_key = callback.data.replace("q_ch_", "")
    user_id = callback.from_user.id
    lead = await db.get_lead(user_id)
    lang = lead.get("preferred_lang", config.DEFAULT_LANG) if lead else config.DEFAULT_LANG
    selected = list(lead.get("service_interest") or []) if lead else []

    if ch_key in selected:
        selected.remove(ch_key)
    else:
        selected.append(ch_key)

    await db.update_lead(user_id, service_interest=selected)
    await show_q3(callback, lang, selected)
    await callback.answer()


@router.callback_query(F.data == "q_ch_done")
async def handle_channels_done(callback: CallbackQuery):
    user_id = callback.from_user.id
    lead = await db.get_lead(user_id)
    lang = lead.get("preferred_lang", config.DEFAULT_LANG) if lead else config.DEFAULT_LANG
    selected = lead.get("service_interest") or []

    await db.track_event(user_id, "questionnaire_q3_answered", {"channels": selected})
    await db.update_lead(user_id, questionnaire_step=4)
    await show_q4(callback, lang)
    await callback.answer()


# ── Q4: CRM status ─────────────────────────────────────────────

@router.callback_query(F.data.startswith("q_crm_"))
async def handle_crm(callback: CallbackQuery):
    user_id = callback.from_user.id
    lead = await db.get_lead(user_id)
    lang = lead.get("preferred_lang", config.DEFAULT_LANG) if lead else config.DEFAULT_LANG

    await db.update_lead(user_id, current_marketing=callback.data, questionnaire_step=5)
    await db.track_event(user_id, "questionnaire_q4_answered", {"crm": callback.data})
    _q5_substep[user_id] = "awaiting_biz"
    await show_q5(callback, lang)
    await callback.answer()


# ── Q5: Intake (5a biz name → 5b website → 5c social) ──────────

@router.message(F.text, QStepFilter(step=5))
async def handle_q5_text(message: Message):
    user_id = message.from_user.id
    lead = await db.get_lead(user_id)
    lang = lead.get("preferred_lang", config.DEFAULT_LANG) if lead else config.DEFAULT_LANG
    sub = _q5_substep.get(user_id, "awaiting_biz")
    text = (message.text or "").strip()

    if sub == "awaiting_biz":
        if len(text) < 2:
            await message.answer(t("q5_biz_invalid", lang))
            return
        await db.update_lead(user_id, business_name=text[:100])
        _q5_substep[user_id] = "awaiting_web"
        await db.track_event(user_id, "questionnaire_q5a_answered", {})
        await message.answer(t("q5b_prompt", lang), reply_markup=q5b_skip_keyboard(lang))
        return

    if sub == "awaiting_web":
        await db.update_lead(user_id, website=text[:200])
        _q5_substep[user_id] = "awaiting_social"
        await db.track_event(user_id, "questionnaire_q5b_answered", {"has_text": True})
        await message.answer(t("q5c_prompt", lang), reply_markup=q5c_skip_keyboard(lang))
        return

    if sub == "awaiting_social":
        await db.update_lead(user_id, social_handle=text[:200], questionnaire_step=6)
        _q5_substep.pop(user_id, None)
        await db.track_event(user_id, "questionnaire_q5c_answered", {"has_text": True})
        await show_q6(message, lang)
        return


@router.callback_query(F.data == "q5b_skip")
async def handle_q5b_skip(callback: CallbackQuery):
    user_id = callback.from_user.id
    lead = await db.get_lead(user_id)
    lang = lead.get("preferred_lang", config.DEFAULT_LANG) if lead else config.DEFAULT_LANG

    _q5_substep[user_id] = "awaiting_social"
    await db.track_event(user_id, "questionnaire_q5b_answered", {"skipped": True})
    await safe_edit(callback, t("q5c_prompt", lang), reply_markup=q5c_skip_keyboard(lang))
    await callback.answer()


@router.callback_query(F.data == "q5c_skip")
async def handle_q5c_skip(callback: CallbackQuery):
    user_id = callback.from_user.id
    lead = await db.get_lead(user_id)
    lang = lead.get("preferred_lang", config.DEFAULT_LANG) if lead else config.DEFAULT_LANG

    _q5_substep.pop(user_id, None)
    await db.update_lead(user_id, questionnaire_step=6)
    await db.track_event(user_id, "questionnaire_q5c_answered", {"skipped": True})
    await safe_edit(callback, t("q_problem_skipped", lang))
    await callback.answer()
    await show_q6(callback, lang)


# ── Q6: Phone share — "later" skip ─────────────────────────────
# Phone Contact itself is captured by handlers/contact.py; that handler will
# call complete_questionnaire(...) when it sees questionnaire_step == 6.

@router.message(F.text.regexp(r"^(⏭|Keyinroq|Позже)"), QStepFilter(step=6))
async def handle_phone_skip(message: Message):
    user_id = message.from_user.id
    lead = await db.get_lead(user_id)
    lang = lead.get("preferred_lang", config.DEFAULT_LANG) if lead else config.DEFAULT_LANG

    await db.track_event(user_id, "questionnaire_q6_answered", {"phone_skipped": True})
    await complete_questionnaire(user_id, message, lang)
