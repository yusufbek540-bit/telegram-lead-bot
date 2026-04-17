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
    ("q_biz_restaurant", {"uz": "\U0001f37d Restoran / Kafe", "ru": "\U0001f37d Ресторан / Кафе"}),
    ("q_biz_beauty", {"uz": "\U0001f487 Go'zallik / Klinika", "ru": "\U0001f487 Красота / Клиника"}),
    ("q_biz_education", {"uz": "\U0001f4da Ta'lim / Kurslar", "ru": "\U0001f4da Образование / Курсы"}),
    ("q_biz_it", {"uz": "\U0001f4bb IT / Startap", "ru": "\U0001f4bb IT / Стартап"}),
    ("q_biz_ecommerce", {"uz": "\U0001f6d2 Onlayn do'kon", "ru": "\U0001f6d2 Онлайн-магазин"}),
    ("q_biz_other", {"uz": "\U0001f4dd Boshqa", "ru": "\U0001f4dd Другое"}),
]

SERVICES = [
    ("q_svc_smm", {"uz": "\U0001f4f1 SMM boshqaruvi", "ru": "\U0001f4f1 Ведение SMM"}),
    ("q_svc_targeting", {"uz": "\U0001f3af Targetlangan reklama", "ru": "\U0001f3af Таргетированная реклама"}),
    ("q_svc_website", {"uz": "\U0001f310 Veb-sayt", "ru": "\U0001f310 Сайт"}),
    ("q_svc_bot", {"uz": "\U0001f916 Telegram / Instagram bot", "ru": "\U0001f916 Telegram / Instagram бот"}),
    ("q_svc_ai", {"uz": "\U0001f9e0 AI avtomatizatsiya", "ru": "\U0001f9e0 AI автоматизация"}),
    ("q_svc_branding", {"uz": "\U0001f3a8 Brending", "ru": "\U0001f3a8 Брендинг"}),
    ("q_svc_consulting", {"uz": "\U0001f4a1 Bilmayman, maslahat kerak", "ru": "\U0001f4a1 Не знаю, нужна консультация"}),
]

MARKETING_STATUS = [
    ("q_mkt_has_no_results", {"uz": "\U0001f610 Ha, lekin natija yo'q", "ru": "\U0001f610 Да, но нет результатов"}),
    ("q_mkt_has_wants_scale", {"uz": "\U0001f4c8 Ha, yaxshi, kengaytirmoqchiman", "ru": "\U0001f4c8 Да, хорошо, хочу масштабировать"}),
    ("q_mkt_none", {"uz": "\U0001f195 Yo'q, noldan boshlayman", "ru": "\U0001f195 Нет, начинаю с нуля"}),
]

BUDGETS = [
    ("q_budget_200_500", {"uz": "\U0001f4b5 $200 — $500", "ru": "\U0001f4b5 $200 — $500"}),
    ("q_budget_500_1000", {"uz": "\U0001f4b0 $500 — $1 000", "ru": "\U0001f4b0 $500 — $1 000"}),
    ("q_budget_1000_3000", {"uz": "\U0001f3e6 $1 000 — $3 000", "ru": "\U0001f3e6 $1 000 — $3 000"}),
    ("q_budget_3000", {"uz": "\U0001f48e $3 000+", "ru": "\U0001f48e $3 000+"}),
    ("q_budget_unknown", {"uz": "\U0001f937 Bilmayman / hali aniq emas", "ru": "\U0001f937 Не знаю / пока не определил"}),
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
    rows = []
    for i in range(0, len(SERVICES), 2):
        row = []
        for cb, labels in SERVICES[i:i+2]:
            svc_key = cb.replace("q_svc_", "")
            prefix = "\u2705 " if svc_key in selected else ""
            row.append(InlineKeyboardButton(text=prefix + labels[lang], callback_data=cb))
        rows.append(row)
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
            [KeyboardButton(text="\U0001f4f1 " + t("btn_share_phone", lang).replace("\U0001f4f1 ", ""), request_contact=True)],
            [KeyboardButton(text="\u23ed " + t("q_skip_later", lang))],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )
