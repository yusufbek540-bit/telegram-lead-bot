"""
Bilingual text content for the bot.
All user-facing strings in Uzbek and Russian.
"""

TEXTS = {
    # ── WELCOME ────────────────────────────────────────────
    "welcome": {
        "uz": (
            "Assalomu alaykum! 👋\n\n"
            "Men {agency_name} yordamchisiman.\n\n"
            "Sizga xizmatlarimiz haqida ma'lumot berishim, "
            "loyihalarimizni ko'rsatishim yoki savollaringizga "
            "javob berishim mumkin.\n\n"
            "Quyidagi tugmalardan birini tanlang yoki "
            "savolingizni yozing — men yordam beraman 💬"
        ),
        "ru": (
            "Здравствуйте! 👋\n\n"
            "Я помощник {agency_name}.\n\n"
            "Могу рассказать о наших услугах, показать портфолио "
            "или ответить на ваши вопросы.\n\n"
            "Выберите кнопку ниже или напишите свой вопрос — "
            "я помогу 💬"
        ),
    },
    # ── SERVICES ───────────────────────────────────────────
    "services": {
        "uz": (
            "📋 <b>Bizning xizmatlar:</b>\n\n"
            "1️⃣ <b>SMM boshqaruvi</b>\n"
            "Instagram, Telegram, Facebook — kontent, posting, community\n\n"
            "2️⃣ <b>Targetlangan reklama</b>\n"
            "Meta Ads, Telegram Ads, Google Ads\n\n"
            "3️⃣ <b>Veb-sayt yaratish</b>\n"
            "Landing, korporativ sayt, e-commerce, veb-ilovalar\n\n"
            "4️⃣ <b>Telegram va Instagram botlar</b>\n"
            "Chatbotlar, lead capture, avto-javob, CRM integratsiya\n\n"
            "5️⃣ <b>AI avtomatizatsiya</b>\n"
            "AI chatbotlar, jarayonlarni avtomatlashtirish, ma'lumot tahlili\n\n"
            "6️⃣ <b>AI konsalting</b>\n"
            "AI strategiya, integratsiya, vositalarni tanlash\n\n"
            "7️⃣ <b>Brending va dizayn</b>\n"
            "Logo, brand book, vizual identifikatsiya\n\n"
            "8️⃣ <b>Kontent ishlab chiqarish</b>\n"
            "Foto, video, Reels/Shorts\n\n"
            "💡 Narx va batafsil ma'lumot uchun /contact bosing"
        ),
        "ru": (
            "📋 <b>Наши услуги:</b>\n\n"
            "1️⃣ <b>Ведение SMM</b>\n"
            "Instagram, Telegram, Facebook — контент, постинг, комьюнити\n\n"
            "2️⃣ <b>Таргетированная реклама</b>\n"
            "Meta Ads, Telegram Ads, Google Ads\n\n"
            "3️⃣ <b>Разработка сайтов</b>\n"
            "Лендинги, корпоративные сайты, e-commerce, веб-приложения\n\n"
            "4️⃣ <b>Telegram и Instagram боты</b>\n"
            "Чатботы, лид-захват, авто-ответы, интеграция с CRM\n\n"
            "5️⃣ <b>AI автоматизация</b>\n"
            "AI чатботы, автоматизация процессов, анализ данных\n\n"
            "6️⃣ <b>AI консалтинг</b>\n"
            "AI стратегия, интеграция, подбор инструментов\n\n"
            "7️⃣ <b>Брендинг и дизайн</b>\n"
            "Логотип, брендбук, визуальная айдентика\n\n"
            "8️⃣ <b>Производство контента</b>\n"
            "Фото, видео, Reels/Shorts\n\n"
            "💡 Для уточнения цен и деталей нажмите /contact"
        ),
    },
    # ── PROJECTS ───────────────────────────────────────────
    "projects": {
        "uz": (
            "🏗 <b>Bizning loyihalar:</b>\n\n"
            "📌 <b>[Loyiha 1 nomi]</b>\n"
            "[Qisqa tavsif: nima qildik, natija]\n\n"
            "📌 <b>[Loyiha 2 nomi]</b>\n"
            "[Qisqa tavsif: nima qildik, natija]\n\n"
            "📌 <b>[Loyiha 3 nomi]</b>\n"
            "[Qisqa tavsif: nima qildik, natija]\n\n"
            "🌐 To'liq portfoilo uchun veb-saytimizni oching 👇"
        ),
        "ru": (
            "🏗 <b>Наши проекты:</b>\n\n"
            "📌 <b>[Название проекта 1]</b>\n"
            "[Краткое описание: что сделали, результат]\n\n"
            "📌 <b>[Название проекта 2]</b>\n"
            "[Краткое описание: что сделали, результат]\n\n"
            "📌 <b>[Название проекта 3]</b>\n"
            "[Краткое описание: что сделали, результат]\n\n"
            "🌐 Полное портфолио на нашем сайте 👇"
        ),
    },
    # ── FAQ ────────────────────────────────────────────────
    "faq": {
        "uz": (
            "❓ <b>Ko'p so'raladigan savollar:</b>\n\n"
            "<b>💰 Qancha turadi?</b>\n"
            "Narxlar loyihaga qarab farq qiladi. Bepul konsultatsiya "
            "orqali aniq narx aytamiz.\n\n"
            "<b>⏱ Qancha vaqtda natija beradi?</b>\n"
            "Odatda 2-4 hafta ichida birinchi natijalar ko'rinadi. "
            "SMM va reklama — 1-2 oy ichida barqaror o'sish.\n\n"
            "<b>📄 Shartnoma tuzasizlarmi?</b>\n"
            "Ha, albatta. Barcha loyihalar rasmiy shartnoma asosida.\n\n"
            "<b>🏢 Qaysi sohalar bilan ishlaysizlar?</b>\n"
            "Barcha sohalarda: restoran, klinika, ta'lim, IT, "
            "e-commerce va boshqalar.\n\n"
            "<b>📊 Hisobot berasizlarmi?</b>\n"
            "Ha, har oy batafsil hisobot taqdim etamiz.\n\n"
            "💬 Boshqa savolingiz bormi? Yozing, javob beraman!"
        ),
        "ru": (
            "❓ <b>Часто задаваемые вопросы:</b>\n\n"
            "<b>💰 Сколько стоит?</b>\n"
            "Цены зависят от проекта. Точную цену скажем "
            "на бесплатной консультации.\n\n"
            "<b>⏱ Когда будут результаты?</b>\n"
            "Обычно первые результаты видны через 2-4 недели. "
            "SMM и реклама — стабильный рост через 1-2 месяца.\n\n"
            "<b>📄 Заключаете ли договор?</b>\n"
            "Да, обязательно. Все проекты ведутся на основе "
            "официального договора.\n\n"
            "<b>🏢 С какими нишами работаете?</b>\n"
            "Со всеми: рестораны, клиники, образование, IT, "
            "e-commerce и другие.\n\n"
            "<b>📊 Предоставляете ли отчёты?</b>\n"
            "Да, ежемесячно предоставляем детальный отчёт.\n\n"
            "💬 Есть другие вопросы? Пишите, отвечу!"
        ),
    },
    # ── ABOUT ──────────────────────────────────────────────
    "about": {
        "uz": (
            "ℹ️ <b>{agency_name} haqida:</b>\n\n"
            "[Agentlik haqida 2-3 jumla: qachon tashkil etilgan, "
            "missiya, tajriba]\n\n"
            "✅ [X]+ amalga oshirilgan loyihalar\n"
            "✅ [X]+ doimiy mijozlar\n"
            "✅ [X] yillik tajriba\n\n"
            "📍 Toshkent, O'zbekiston\n"
            "🕐 Du-Ju: 9:00 — 18:00\n\n"
            "📞 Bog'lanish: /contact"
        ),
        "ru": (
            "ℹ️ <b>О {agency_name}:</b>\n\n"
            "[2-3 предложения об агентстве: когда основано, "
            "миссия, опыт]\n\n"
            "✅ [X]+ реализованных проектов\n"
            "✅ [X]+ постоянных клиентов\n"
            "✅ [X] лет опыта\n\n"
            "📍 Ташкент, Узбекистан\n"
            "🕐 Пн-Пт: 9:00 — 18:00\n\n"
            "📞 Связаться: /contact"
        ),
    },
    # ── CONTACT REQUEST ────────────────────────────────────
    "contact_request": {
        "uz": (
            "📞 Siz bilan bog'lanishimiz uchun telefon raqamingizni "
            "ulashing.\n\n"
            "Quyidagi tugmani bosing — bir marta bosish yetarli 👇"
        ),
        "ru": (
            "📞 Поделитесь номером телефона, чтобы мы могли "
            "с вами связаться.\n\n"
            "Нажмите кнопку ниже — достаточно одного нажатия 👇"
        ),
    },
    "contact_received": {
        "uz": (
            "✅ Rahmat! Telefon raqamingiz qabul qilindi.\n\n"
            "Jamoamiz tez orada siz bilan bog'lanadi. "
            "Shu payt savollaringiz bo'lsa, yozing! 💬"
        ),
        "ru": (
            "✅ Спасибо! Ваш номер получен.\n\n"
            "Наша команда свяжется с вами в ближайшее время. "
            "А пока — задавайте вопросы! 💬"
        ),
    },
    # ── CALLBACK REQUEST ───────────────────────────────────
    "callback_request": {
        "uz": (
            "📞 Biz sizga qo'ng'iroq qilamiz!\n\n"
            "Telefon raqamingizni ulashing va biz 30 daqiqa ichida "
            "bog'lanamiz (ish vaqtida)."
        ),
        "ru": (
            "📞 Мы вам перезвоним!\n\n"
            "Поделитесь номером телефона, и мы свяжемся "
            "в течение 30 минут (в рабочее время)."
        ),
    },
    # ── LANGUAGE SWITCH ────────────────────────────────────
    "lang_switched": {
        "uz": "✅ Til o'zbekchaga o'zgartirildi.",
        "ru": "✅ Язык переключён на русский.",
    },
    "choose_lang": {
        "uz": "🌐 Tilni tanlang / Выберите язык:",
        "ru": "🌐 Tilni tanlang / Выберите язык:",
    },
    # ── LIVE CHAT ──────────────────────────────────────────
    "live_chat_request": {
        "uz": (
            "🙋 Jonli chat so'rovi yuborildi!\n\n"
            "Menejer tez orada siz bilan bog'lanadi. "
            "Shu payt savolingizni yozing — o'qib chiqamiz 💬"
        ),
        "ru": (
            "🙋 Запрос на живой чат отправлен!\n\n"
            "Менеджер свяжется с вами в ближайшее время. "
            "Пока можете написать свой вопрос — мы его прочитаем 💬"
        ),
    },
    "live_chat_active": {
        "uz": (
            "✅ Menejer chat qabul qildi! Endi yozishingiz mumkin 💬\n\n"
            "Chatni tugatish uchun /endchat bosing."
        ),
        "ru": (
            "✅ Менеджер принял чат! Теперь вы можете писать 💬\n\n"
            "Чтобы завершить чат, нажмите /endchat."
        ),
    },
    "live_chat_ended_user": {
        "uz": "✅ Chat yakunlandi. Rahmat! Boshqa savollar bo'lsa, yozing 😊",
        "ru": "✅ Чат завершён. Спасибо! Если появятся вопросы — пишите 😊",
    },
    "live_chat_forwarded": {
        "uz": "📨 Xabaringiz menejerlarga yuborildi.",
        "ru": "📨 Ваше сообщение отправлено менеджеру.",
    },
    "admin_live_chat_request": {
        "ru": (
            "🙋 <b>Запрос живого чата!</b>\n\n"
            "Лид: <b>{name}</b>\n"
            "Username: @{username}\n"
            "Телефон: {phone}\n"
            "Назначен: {assigned_to}\n\n"
            "Сообщение: {message}"
        ),
    },
    "admin_live_chat_message": {
        "ru": (
            "💬 <b>{name}</b> пишет:\n\n"
            "{message}"
        ),
    },
    # ── QUESTIONNAIRE ─────────────────────────────────────
    "q_intro": {
        "uz": "Sizga eng mos xizmatni taklif qilishimiz uchun bir necha savolga javob bering. 1 daqiqa vaqt oladi!",
        "ru": "Ответьте на пару вопросов, чтобы мы подобрали лучшее решение. Займёт 1 минуту!",
    },
    "q1_text": {
        "uz": "Qaysi sohada ishlaysiz?",
        "ru": "В какой сфере вы работаете?",
    },
    "q1_other_text": {
        "uz": "Qaysi sohada ishlaysiz? Qisqacha yozing.",
        "ru": "В какой сфере работаете? Напишите кратко.",
    },
    "q2_text": {
        "uz": "Sizga nima kerak? (1-2 ta tanlang, keyin \"Davom etish\" bosing)",
        "ru": "Что вам нужно? (выберите 1-2, затем нажмите \"Далее\")",
    },
    "q3_text": {
        "uz": "Hozirda marketing qilyapsizmi?",
        "ru": "Вы сейчас ведёте маркетинг?",
    },
    "q4_text": {
        "uz": "Oylik taxminiy byudjetingiz?",
        "ru": "Ваш примерный бюджет в месяц?",
    },
    "q5_text": {
        "uz": "Zo'r! Oxirgi qadam — jamoamiz siz bilan bog'lanishi uchun raqamingizni ulashing.",
        "ru": "Отлично! Последний шаг — поделитесь номером, чтобы команда могла связаться.",
    },
    "q_complete": {
        "uz": "Rahmat! Siz haqingizda bilib oldik.\n\nEndi savollaringizni yozing yoki menyudan tanlang",
        "ru": "Спасибо! Мы узнали о вас больше.\n\nТеперь напишите вопрос или выберите из меню",
    },
    "q_skip_later": {
        "uz": "Keyinroq",
        "ru": "Позже",
    },
    "q_continue": {
        "uz": "Davom etish",
        "ru": "Далее",
    },
    "btn_q_skip": {"uz": "Keyinroq", "ru": "Позже"},
    # ── BUTTONS ────────────────────────────────────────────
    "btn_services": {"uz": "📋 Xizmatlar", "ru": "📋 Услуги"},
    "btn_portfolio": {"uz": "🖼 Portfolio", "ru": "🖼 Портфолио"},
    "btn_faq": {"uz": "❓ FAQ", "ru": "❓ FAQ"},
    "btn_about": {"uz": "ℹ️ Biz haqimizda", "ru": "ℹ️ О нас"},
    "btn_website": {"uz": "🌐 Veb-sayt", "ru": "🌐 Сайт"},
    "btn_live_chat": {"uz": "💬 Menejer bilan chat", "ru": "💬 Чат с менеджером"},
    "btn_callback": {"uz": "📞 Qo'ng'iroq so'rash", "ru": "📞 Заказать звонок"},
    "btn_share_phone": {"uz": "📱 Raqamni ulashish", "ru": "📱 Поделиться номером"},
    "btn_back": {"uz": "🔙 Orqaga", "ru": "🔙 Назад"},
    "btn_lang": {"uz": "🌐 Tilni o'zgartirish", "ru": "🌐 Сменить язык"},
    "btn_uz": {"uz": "🇺🇿 O'zbekcha", "ru": "🇺🇿 Узбекский"},
    "btn_ru": {"uz": "🇷🇺 Ruscha", "ru": "🇷🇺 Русский"},
    # ── ADMIN ──────────────────────────────────────────────
    "admin_no_access": {
        "uz": "⛔ Sizda admin huquqi yo'q.",
        "ru": "⛔ У вас нет прав администратора.",
    },
    "admin_new_lead": {
        "uz": "🆕 Yangi lead!\n\n👤 {name}\n🆔 @{username}\n📱 {phone}\n📊 Manba: {source}",
        "ru": "🆕 Новый лид!\n\n👤 {name}\n🆔 @{username}\n📱 {phone}\n📊 Источник: {source}",
    },
    "admin_new_lead_organic": {
        "ru": (
            "👤 Новый лид (органика)\n\n"
            "Имя: <b>{name}</b>\n"
            "Username: @{username}\n"
            "Язык: {lang}\n"
            "Источник: organic"
        ),
    },
    "admin_phone_shared": {
        "ru": (
            "📱 Лид поделился номером!\n\n"
            "Имя: <b>{name}</b>\n"
            "Username: @{username}\n"
            "Телефон: <b>{phone}</b>\n"
            "Источник: {source}\n"
            "Баллы: {score}"
        ),
    },
    "admin_assigned": {
        "ru": (
            "📋 Вам назначен лид!\n\n"
            "Имя: <b>{name}</b>\n"
            "Username: @{username}\n"
            "Телефон: {phone}\n"
            "Источник: {source}\n"
            "Баллы: {score}\n\n"
            "Назначил: {assigned_by}"
        ),
    },
}


def t(key: str, lang: str = "uz", **kwargs) -> str:
    """Get translated text by key and language."""
    text_dict = TEXTS.get(key, {})
    text = text_dict.get(lang, text_dict.get("uz", f"[Missing: {key}]"))
    if kwargs:
        text = text.format(**kwargs)
    return text
