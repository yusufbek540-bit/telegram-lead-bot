"""
Free Audit qualification flow keyboards.

Maps to existing DB columns (no migration):
- business_type        → vertical
- budget_range         → monthly ad-spend tier
- service_interest[]   → currently-running channels (multi-select)
- current_marketing    → CRM status
- business_name        → top problem (free text, captured at Q5)

UZ labels still legacy until follow-up pass; RU is the source of truth.
"""

from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton,
)
from bot.texts import t


# ── Q1: Vertical ───────────────────────────────────────────────
# Active outbound verticals per MQSD positioning. "other" is allowed
# but routed inbound only — we still capture them.
VERTICALS = [
    ("q_v_realestate", {"uz": "Ko'chmas mulk (devlopment)", "ru": "Жилая недвижимость / девелопмент"}),
    ("q_v_clinic", {"uz": "Xususiy klinika", "ru": "Частная медицинская клиника"}),
    ("q_v_education", {"uz": "Ta'lim / kouching", "ru": "Образование / коучинг"}),
    ("q_v_other", {"uz": "Boshqa yo'nalish", "ru": "Другое направление"}),
]

# ── Q2: Monthly ad spend ──────────────────────────────────────
AD_SPENDS = [
    ("q_spend_none", {"uz": "Hali reklama qilmaymiz", "ru": "Пока не запускаем рекламу"}),
    ("q_spend_lt1k", {"uz": "$1 000 gacha", "ru": "До $1 000"}),
    ("q_spend_1k_3k", {"uz": "$1 000 — $3 000", "ru": "$1 000 — $3 000"}),
    ("q_spend_3k_10k", {"uz": "$3 000 — $10 000", "ru": "$3 000 — $10 000"}),
    ("q_spend_10k_plus", {"uz": "$10 000+", "ru": "$10 000+"}),
]

# ── Q3: Current channels (multi-select) ───────────────────────
CHANNELS = [
    ("q_ch_meta", {"uz": "Instagram / Facebook reklama", "ru": "Реклама Instagram / Facebook"}),
    ("q_ch_google", {"uz": "Google Ads", "ru": "Google Ads"}),
    ("q_ch_telegram", {"uz": "Telegram (kanal/reklama)", "ru": "Telegram (канал/реклама)"}),
    ("q_ch_organic", {"uz": "Organik kontent / SMM", "ru": "Органический контент / SMM"}),
    ("q_ch_offline", {"uz": "Offline (bilbord, agentlar)", "ru": "Офлайн (билборды, агенты)"}),
    ("q_ch_none", {"uz": "Hozircha hech narsa", "ru": "Пока ничего не работает"}),
]

# ── Q4: CRM status ────────────────────────────────────────────
CRM_STATUS = [
    ("q_crm_yes", {"uz": "Ha, to'liq CRM ishlaydi", "ru": "Да, полноценная CRM"}),
    ("q_crm_sheet", {"uz": "Excel/Google Sheets", "ru": "Excel / Google Sheets"}),
    ("q_crm_no", {"uz": "Yo'q, hech narsa yo'q", "ru": "Нет, ничего не ведём"}),
]


def _grid(items, lang: str, cols: int = 1) -> InlineKeyboardMarkup:
    rows = []
    for i in range(0, len(items), cols):
        row = [InlineKeyboardButton(text=labels[lang], callback_data=cb)
               for cb, labels in items[i:i+cols]]
        rows.append(row)
    return InlineKeyboardMarkup(inline_keyboard=rows)


def q1_keyboard(lang: str) -> InlineKeyboardMarkup:
    return _grid(VERTICALS, lang, cols=1)


def q2_keyboard(lang: str) -> InlineKeyboardMarkup:
    return _grid(AD_SPENDS, lang, cols=1)


def q3_keyboard(lang: str, selected: list = None) -> InlineKeyboardMarkup:
    selected = selected or []
    rows = []
    for cb, labels in CHANNELS:
        ch_key = cb.replace("q_ch_", "")
        prefix = "✓ " if ch_key in selected else ""
        rows.append([InlineKeyboardButton(text=prefix + labels[lang], callback_data=cb)])
    if selected:
        rows.append([InlineKeyboardButton(text=t("q_continue", lang) + " →", callback_data="q_ch_done")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def q4_keyboard(lang: str) -> InlineKeyboardMarkup:
    return _grid(CRM_STATUS, lang, cols=1)


def q5b_skip_keyboard(lang: str) -> InlineKeyboardMarkup:
    """Inline 'skip' for the optional website prompt (Q5b)."""
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=t("q_skip_btn", lang), callback_data="q5b_skip"),
    ]])


def q5c_skip_keyboard(lang: str) -> InlineKeyboardMarkup:
    """Inline 'skip' for the optional social handle prompt (Q5c)."""
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=t("q_skip_btn", lang), callback_data="q5c_skip"),
    ]])


def q6_phone_keyboard(lang: str) -> ReplyKeyboardMarkup:
    """Q6: phone share (request_contact) + 'later' skip button."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📱 " + t("btn_share_phone", lang).replace("📱 ", ""), request_contact=True)],
            [KeyboardButton(text="⏭ " + t("q_skip_later", lang))],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )
