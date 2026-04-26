"""
Bilingual text content for the bot.

NOTE (2026-04 realignment): RU is the primary language and reflects the
current MQSD positioning (no AI mentions, three-layer messaging, formal вы,
named verticals). UZ strings are still legacy-positioned and will be updated
in a follow-up pass.
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
            "{agency_name}.\n\n"
            "Собираем продажи в систему: от первого объявления "
            "до закрытой сделки. Запускаем за дни, работает с первого дня.\n\n"
            "Здесь вы можете запросить бесплатный аудит вашей воронки, "
            "посмотреть, как мы строим, или связаться с партнёром.\n\n"
            "Выберите ниже или напишите — мы свяжемся в течение 24 часов."
        ),
    },
    # ── SERVICES ───────────────────────────────────────────
    "services": {
        "uz": (
            "📋 <b>Bizning xizmatlar:</b>\n\n"
            "1️⃣ <b>Reklama uchun kontent</b>\n"
            "Targetlash uchun video, kreativlar, vizuallar — fotosessiyasiz\n\n"
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
            "<b>Что мы делаем</b>\n\n"
            "Строим и ведём систему продаж целиком — от первого "
            "объявления до закрытой сделки. Никаких разрозненных "
            "услуг: одна команда отвечает за результат.\n\n"
            "<b>Как с нами можно работать</b>\n\n"
            "<b>1. Бесплатный аудит воронки</b>\n"
            "Разбираем вашу текущую воронку, показываем, где теряются "
            "лиды и деньги. Ограничено первыми 10 партнёрами.\n\n"
            "<b>2. Полная сборка системы</b>\n"
            "Реклама, посадочная, квалификация, CRM, отчётность — "
            "под ключ за 4–8 недель. От $4 000 до $12 000.\n\n"
            "<b>3. Сопровождение</b>\n"
            "<i>Self-Drive</i> — вы ведёте, мы поддерживаем "
            "($300–$500/мес).\n"
            "<i>Co-Pilot</i> — ведём вместе, отвечаем за цифры "
            "($1 500–$6 000/мес + % от рекламного бюджета).\n\n"
            "Чтобы начать — запросите бесплатный аудит."
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
            "Reklama va kontent — 1-2 oy ichida barqaror o'sish.\n\n"
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
            "<b>Частые вопросы</b>\n\n"
            "<b>С кем вы работаете?</b>\n"
            "Активно — с застройщиками жилой недвижимости, "
            "частными медицинскими клиниками и образовательными "
            "проектами/коучами. Остальные направления (B2B, "
            "e-commerce, HoReCa) — по запросу.\n\n"
            "<b>Сколько это стоит?</b>\n"
            "Полная сборка системы — от $4 000 до $12 000 "
            "за 4–8 недель. Сопровождение — от $300/мес "
            "(Self-Drive) до $1 500–$6 000/мес плюс % "
            "от рекламного бюджета (Co-Pilot).\n\n"
            "<b>Сколько ждать первых результатов?</b>\n"
            "Воронка запускается за дни, работает с первого "
            "дня. Стабильные цифры по стоимости лида "
            "и закрытой сделке — обычно с первого месяца.\n\n"
            "<b>Заключаете договор?</b>\n"
            "Да. Все проекты — по договору, с прозрачной "
            "отчётностью и согласованными метриками.\n\n"
            "Чтобы получить разбор именно вашей воронки — "
            "запросите бесплатный аудит."
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
            "<b>{agency_name}</b>\n\n"
            "Мы — стратегический партнёр по продажам. Не подрядчик "
            "по кускам, а команда, которая отвечает за всю систему: "
            "от первого объявления до закрытой сделки.\n\n"
            "<b>Что вы получаете</b>\n"
            "— Запуск за дни, не за месяцы.\n"
            "— Один владелец результата, а не пять подрядчиков.\n"
            "— Понятная экономика лида и сделки. Вы перестаёте "
            "гадать, откуда приходят клиенты.\n\n"
            "Базируемся в Ташкенте. Работаем по договору."
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
    "partner_handoff_received": {
        "uz": (
            "Vazifani muhokama qilish uchun bepul strategik sessiya uchun "
            "qulay vaqtni tanlang — aynan o'sha vaqtda bog'lanamiz va biznesni tahlil qilamiz."
        ),
        "ru": (
            "Чтобы обсудить вашу задачу, выберите время для бесплатной "
            "стратегической сессии — мы свяжемся точно в это время и "
            "разберём бизнес."
        ),
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
    # ── QUESTIONNAIRE (Free Audit qualification) ──────────
    "q_intro": {
        "uz": "Sizga bepul auditni taqdim etishimiz uchun 5 ta qisqa savol. Taxminan 1 daqiqa.",
        "ru": (
            "Чтобы подготовить ваш бесплатный аудит, ответьте на 5 коротких вопросов. "
            "Это займёт около минуты."
        ),
    },
    "q1_text": {
        "uz": "Qaysi yo'nalishda ishlaysiz?",
        "ru": "В каком направлении вы работаете?",
    },
    "q2_text": {
        "uz": "Hozirda oyiga reklamaga taxminan qancha ajratasiz?",
        "ru": "Сколько примерно вы тратите на рекламу в месяц?",
    },
    "q3_text": {
        "uz": "Hozirgi paytda qaysi kanallar ishlaydi? (bir nechta tanlang, keyin \"Davom etish\")",
        "ru": "Какие каналы работают у вас сейчас? (выберите все подходящие, затем «Далее»)",
    },
    "q4_text": {
        "uz": "Lidlarni qanday yuritasiz?",
        "ru": "Как вы ведёте лидов и сделки?",
    },
    "q5_text": {
        "uz": (
            "Bizga aniq yordam berishimiz uchun ayting: hozirda eng katta muammo nima? "
            "Bir-ikki jumla yetadi."
        ),
        "ru": (
            "Чтобы аудит был по делу, опишите коротко: какая сейчас главная "
            "проблема в продажах? Хватит одного-двух предложений."
        ),
    },
    "q6_text": {
        "uz": (
            "So'nggi qadam — biz siz bilan bog'lanishimiz uchun telefoningizni ulashing. "
            "Kechiktirsangiz ham bo'ladi — Telegram orqali yozamiz."
        ),
        "ru": (
            "Последний шаг — поделитесь номером, чтобы партнёр мог связаться. "
            "Можно пропустить — тогда напишем в Telegram."
        ),
    },
    "q_problem_skipped": {
        "uz": "Yaxshi, davom etamiz.",
        "ru": "Хорошо, идём дальше.",
    },
    "q_complete": {
        "uz": (
            "Rahmat. Kontekst qabul qilindi.\n\n"
            "Bepul strategik sessiya uchun qulay vaqtni tanlang — "
            "uchrashuvda biznesni tahlil qilamiz va auditni siz bilan birga tayyorlaymiz."
        ),
        "ru": (
            "Спасибо. Контекст получен.\n\n"
            "Выберите удобное время для бесплатной стратегической сессии — "
            "на встрече разберём бизнес и подготовим аудит вместе с вами."
        ),
    },
    "q5a_prompt": {
        "uz": "Biznesingiz nomi qanday? Bitta xabarda yuboring.",
        "ru": "Как называется ваш бизнес? Введите название одним сообщением.",
    },
    "q5_biz_invalid": {
        "uz": "Juda qisqa. Biznes nomini kiriting (kamida 2 belgi).",
        "ru": "Слишком коротко. Введите название бизнеса (минимум 2 символа).",
    },
    "q5b_prompt": {
        "uz": "Biznesning sayti bormi? Havolani yuboring yoki «O'tkazib yuborish» tugmasini bosing.",
        "ru": "Есть ли у бизнеса сайт? Пришлите ссылку, или нажмите «Пропустить».",
    },
    "q5c_prompt": {
        "uz": "Ijtimoiy tarmoqlar — istalgan profil. Havola yoki @username yuboring, yoki «O'tkazib yuborish» tugmasini bosing.",
        "ru": "Соцсети — любой профиль. Пришлите ссылку или @username, или нажмите «Пропустить».",
    },
    "q_skip_btn": {
        "uz": "O'tkazib yuborish",
        "ru": "Пропустить",
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
    "btn_my_sessions": {"uz": "🗓 Sessiyalarim", "ru": "🗓 Мои сессии"},
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
        "ru": (
            "<b>Новый лид</b>\n\n"
            "Имя: <b>{name}</b>\n"
            "Username: @{username}\n"
            "Телефон: {phone}\n"
            "Источник: {source}"
        ),
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
            "<b>Лид поделился номером</b>\n\n"
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
