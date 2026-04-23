"""
Questionnaire keyboard layouts.
"""

from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton,
)
from bot.texts import t


BUSINESS_TYPES = [
    ("q_biz_health", {"uz": "🏥 Salomatlik / Klinika", "ru": "🏥 Здоровье / Клиника"}),
    ("q_biz_beauty", {"uz": "🛍 Fashion / Retail", "ru": "🛍 Fashion / Retail"}),
    ("q_biz_realestate", {"uz": "🏠 Ko'chmas mulk", "ru": "🏠 Недвижимость"}),
    ("q_biz_education", {"uz": "📚 Ta'lim / Kurslar", "ru": "📚 Образование / Курсы"}),
    ("q_biz_auto", {"uz": "🚗 Avto / Dilerlik", "ru": "🚗 Авто / Дилерство"}),
    ("q_biz_b2b", {"uz": "🚀 B2B / Startap", "ru": "🚀 B2B / Стартап"}),
    ("q_biz_consulting", {"uz": "💡 Konsalting / Kouching", "ru": "💡 Консалтинг / Коучинг"}),
    ("q_biz_ecommerce", {"uz": "🛒 Savdo / E-com", "ru": "🛒 Продажи / E-com"}),
    ("q_biz_fitness", {"uz": "💪 Fitnes", "ru": "💪 Фитнес"}),
    ("q_biz_horeca", {"uz": "🍽 HoReCa / Restoran", "ru": "🍽 HoReCa / Ресторан"}),
    ("q_biz_fmcg", {"uz": "📦 FMCG mahsulotlar", "ru": "📦 FMCG продукты"}),
    ("q_biz_other", {"uz": "📝 Boshqa", "ru": "📝 Другое"}),
]

SERVICES = [
    ("q_svc_smm", {"uz": "📱 SMM boshqaruvi", "ru": "📱 Ведение SMM"}),
    ("q_svc_targeting", {"uz": "🎯 Targeting", "ru": "🎯 Таргетинг"}),
    ("q_svc_website", {"uz": "🌐 Veb-sayt", "ru": "🌐 Сайт"}),
    ("q_svc_bot", {"uz": "🤖 TG / Insta bot", "ru": "🤖 TG / Insta бот"}),
    ("q_svc_ai", {"uz": "🧠 AI avtomatizatsiya", "ru": "🧠 AI автоматизация"}),
    ("q_svc_branding", {"uz": "🎨 Brending", "ru": "🎨 Брендинг"}),
    ("q_svc_consulting", {"uz": "💡 Maslahat kerak", "ru": "💡 Нужна консультация"}),
]
SERVICES_PAIRED = [
    ("q_svc_smm", "q_svc_targeting"),
    ("q_svc_website", "q_svc_bot"),
    ("q_svc_ai", "q_svc_branding"),
]
SERVICES_SOLO = ["q_svc_consulting"]

MARKETING_STATUS = [
    ("q_mkt_has_no_results", {"uz": "😐 Ha, lekin natija yo'q", "ru": "😐 Да, но нет результатов"}),
    ("q_mkt_has_wants_scale", {"uz": "📈 Ha, kengaytirmoqchiman", "ru": "📈 Да, хочу масштабировать"}),
    ("q_mkt_none", {"uz": "🆕 Yo'q, noldan", "ru": "🆕 Нет, с нуля"}),
]

BUDGETS = [
    ("q_budget_1000_1500", {"uz": "💵 $1 000 — $1 500", "ru": "💵 $1 000 — $1 500"}),
    ("q_budget_2000_3000", {"uz": "💰 $2 000 — $3 000", "ru": "💰 $2 000 — $3 000"}),
    ("q_budget_3000_5000", {"uz": "🏦 $3 000 — $5 000", "ru": "🏦 $3 000 — $5 000"}),
    ("q_budget_5000_plus", {"uz": "💎 $5 000+", "ru": "💎 $5 000+"}),
]


def q1_keyboard(lang: str) -> InlineKeyboardMarkup:
    rows = []
    for i in range(0, len(BUSINESS_TYPES), 2):
        row = []
        for cb, labels in BUSINESS_TYPES[i:i+2]:
            row.append(InlineKeyboardButton(text=labels[lang], callback_data=cb))
        rows.append(row)
    return InlineKeyboardMarkup(inline_keyboard=rows)


def q2_keyboard(lang: str, selected: list = None) -> InlineKeyboardMarkup:
    selected = selected or []
    svc_map = {cb: labels for cb, labels in SERVICES}
    rows = []
    for pair in SERVICES_PAIRED:
        row = []
        for cb in pair:
            labels = svc_map[cb]
            svc_key = cb.replace("q_svc_", "")
            prefix = "\u2705 " if svc_key in selected else ""
            row.append(InlineKeyboardButton(text=prefix + labels[lang], callback_data=cb))
        rows.append(row)
    for cb in SERVICES_SOLO:
        labels = svc_map[cb]
        svc_key = cb.replace("q_svc_", "")
        prefix = "\u2705 " if svc_key in selected else ""
        rows.append([InlineKeyboardButton(text=prefix + labels[lang], callback_data=cb)])
    if selected:
        rows.append([InlineKeyboardButton(text=t("q_continue", lang) + " \u2192", callback_data="q_svc_done")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def q3_keyboard(lang: str) -> InlineKeyboardMarkup:
    rows = []
    for cb, labels in MARKETING_STATUS:
        rows.append([InlineKeyboardButton(text=labels[lang], callback_data=cb)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def q4_keyboard(lang: str) -> InlineKeyboardMarkup:
    rows = []
    for i in range(0, len(BUDGETS), 2):
        row = []
        for cb, labels in BUDGETS[i:i+2]:
            row.append(InlineKeyboardButton(text=labels[lang], callback_data=cb))
        rows.append(row)
    return InlineKeyboardMarkup(inline_keyboard=rows)


def q5_keyboard(lang: str) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📱 " + t("btn_share_phone", lang).replace("📱 ", ""), request_contact=True)],
            [KeyboardButton(text="\u23ed " + t("q_skip_later", lang))],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )
