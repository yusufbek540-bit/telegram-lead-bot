# Lead Qualification Questionnaire — Implementation Plan

## Overview

A 5-question onboarding flow that runs once per lead, right after /start and language selection. Collects: business type, service interest, current marketing status, budget range, and phone number. All questions use inline buttons (single tap) — no typing required. Total time: under 60 seconds. Total taps: 6-7.

The questionnaire is NOT a gate — leads who skip or abandon mid-way can still access the main menu and AI chat. Incomplete questionnaires are tracked and the bot can ask remaining questions naturally during later conversation.

---

## 1. Database Changes

### New Columns on `leads` Table

```sql
ALTER TABLE leads ADD COLUMN IF NOT EXISTS business_type TEXT;
-- Values: restaurant, beauty, education, it, ecommerce, other

ALTER TABLE leads ADD COLUMN IF NOT EXISTS business_type_other TEXT;
-- Free text, only filled if business_type = 'other'

ALTER TABLE leads ADD COLUMN IF NOT EXISTS service_interest JSONB DEFAULT '[]';
-- Array of strings: ["smm", "targeting", "website", "bot", "ai", "branding", "consulting"]

ALTER TABLE leads ADD COLUMN IF NOT EXISTS current_marketing TEXT;
-- Values: no_marketing, has_no_results, has_wants_scale

ALTER TABLE leads ADD COLUMN IF NOT EXISTS budget_range TEXT;
-- Values: 200-500, 500-1000, 1000-3000, 3000+, unknown

ALTER TABLE leads ADD COLUMN IF NOT EXISTS questionnaire_completed BOOLEAN DEFAULT FALSE;

ALTER TABLE leads ADD COLUMN IF NOT EXISTS questionnaire_completed_at TIMESTAMPTZ;
```

Save as: `database/migrations/003_questionnaire.sql`

Must be idempotent (safe to re-run). Use `IF NOT EXISTS` on every statement.

### No New Tables Needed

All data fits on the existing `leads` table. The questionnaire is a property of the lead, not a separate entity.

---

## 2. Questionnaire Content (Bilingual)

### Q1 — Business Type

```
UZ: Qaysi sohada ishlaysiz?
RU: В какой сфере вы работаете?
```

Buttons (2 rows of 3):
| callback_data        | UZ label              | RU label                 |
|----------------------|-----------------------|--------------------------|
| `q_biz_restaurant`   | 🍽 Restoran / Kafe     | 🍽 Ресторан / Кафе        |
| `q_biz_beauty`       | 💇 Go'zallik / Klinika | 💇 Красота / Клиника      |
| `q_biz_education`    | 📚 Ta'lim / Kurslar    | 📚 Образование / Курсы    |
| `q_biz_it`           | 💻 IT / Startap        | 💻 IT / Стартап           |
| `q_biz_ecommerce`    | 🛒 Onlayn do'kon       | 🛒 Онлайн-магазин         |
| `q_biz_other`        | 📝 Boshqa              | 📝 Другое                 |

If "other" is selected → send a text message asking for free-text input:
```
UZ: Qaysi sohada ishlaysiz? Qisqacha yozing.
RU: В какой сфере работаете? Напишите кратко.
```
Bot waits for one text message, saves it to `business_type_other`, then moves to Q2.

### Q2 — Service Interest

```
UZ: Sizga nima kerak? (1-2 ta tanlang)
RU: Что вам нужно? (выберите 1-2)
```

Buttons (4 rows of 2 + 1 row of 1):
| callback_data        | UZ label                    | RU label                      |
|----------------------|-----------------------------|-------------------------------|
| `q_svc_smm`          | 📱 SMM boshqaruvi            | 📱 Ведение SMM                 |
| `q_svc_targeting`    | 🎯 Targetlangan reklama      | 🎯 Таргетированная реклама     |
| `q_svc_website`      | 🌐 Veb-sayt                  | 🌐 Сайт                       |
| `q_svc_bot`          | 🤖 Telegram / Instagram bot  | 🤖 Telegram / Instagram бот   |
| `q_svc_ai`           | 🧠 AI avtomatizatsiya        | 🧠 AI автоматизация            |
| `q_svc_branding`     | 🎨 Brending                  | 🎨 Брендинг                    |
| `q_svc_consulting`   | 💡 Bilmayman, maslahat kerak | 💡 Не знаю, нужна консультация |

**Multi-select behavior:**
- Each tap toggles the option (adds ✅ prefix if selected, removes on second tap)
- Show a "Davom etish →" / "Далее →" button at the bottom that appears after at least 1 selection
- Edit the same message on each tap (using `safe_edit()`) to update button states
- When "Davom etish" is tapped → save selections and move to Q3

### Q3 — Current Marketing Status

```
UZ: Hozirda marketing qilyapsizmi?
RU: Вы сейчас ведёте маркетинг?
```

Buttons (3 rows of 1):
| callback_data             | UZ label                                     | RU label                                           |
|---------------------------|----------------------------------------------|----------------------------------------------------|
| `q_mkt_has_no_results`    | 😐 Ha, lekin natija yo'q                      | 😐 Да, но нет результатов                           |
| `q_mkt_has_wants_scale`   | 📈 Ha, yaxshi, kengaytirmoqchiman             | 📈 Да, хорошо, хочу масштабировать                   |
| `q_mkt_none`              | 🆕 Yo'q, noldan boshlayman                    | 🆕 Нет, начинаю с нуля                              |

Single-select — one tap moves to Q4.

### Q4 — Budget Range

```
UZ: Oylik taxminiy byudjetingiz?
RU: Ваш примерный бюджет в месяц?
```

Buttons (3 rows of 2):
| callback_data           | UZ label                      | RU label                       |
|-------------------------|-------------------------------|--------------------------------|
| `q_budget_200_500`      | 💵 $200 — $500                | 💵 $200 — $500                 |
| `q_budget_500_1000`     | 💰 $500 — $1 000              | 💰 $500 — $1 000               |
| `q_budget_1000_3000`    | 🏦 $1 000 — $3 000            | 🏦 $1 000 — $3 000             |
| `q_budget_3000`         | 💎 $3 000+                    | 💎 $3 000+                     |
| `q_budget_unknown`      | 🤷 Bilmayman / hali aniq emas | 🤷 Не знаю / пока не определил |

Single-select — one tap moves to Q5.

### Q5 — Phone Number (Contact Share)

```
UZ: Zo'r! Oxirgi qadam — jamoamiz siz bilan bog'lanishi uchun raqamingizni ulashing.
RU: Отлично! Последний шаг — поделитесь номером, чтобы команда могла связаться.
```

Two options:
1. **ReplyKeyboard with contact share button** (native Telegram, one tap)
   - `📱 Raqamni ulashish` / `📱 Поделиться номером`
2. **Skip button** (inline)
   - `⏭ Keyinroq` / `⏭ Позже`

**Important UX pattern (from CLAUDE.md):**
- InlineKeyboard does NOT dismiss ReplyKeyboard
- Send ReplyKeyboard for phone share
- If they share phone → dismiss ReplyKeyboard with `ReplyKeyboardRemove()`, then send completion message with main menu InlineKeyboard
- If they tap skip (this must be a separate inline message, or handle via text detection since ReplyKeyboard is showing)

**Alternative skip approach:** Add "Keyinroq / Позже" as a second ReplyKeyboard button (not contact request, just text). When bot receives this text → treat as skip.

### Completion Message

```
UZ: ✅ Rahmat! Siz haqingizda bilib oldik.

Endi savollaringizni yozing yoki menyudan tanlang 👇
RU: ✅ Спасибо! Мы узнали о вас больше.

Теперь напишите вопрос или выберите из меню 👇
```

Followed by main menu inline keyboard (same as current welcome).

---

## 3. Bot Implementation

### New File: `bot/handlers/questionnaire.py`

This is a new router registered in `main.py` AFTER `start.py` but BEFORE all other handlers.

**Updated router order in `main.py`:**
```
start → questionnaire → admin → contact → twa → menu → ai_chat
```

The questionnaire router handles:
- All `callback_data` starting with `q_` prefix
- Free-text input when waiting for "other" business type
- Contact sharing during Q5 (or reuse existing `contact.py` handler)

### State Management

**Option A — Database-driven (recommended, no FSM dependency):**
- Add column `questionnaire_step INTEGER DEFAULT 0` to `leads`
- Step 0 = not started, 1 = Q1 shown, 2 = Q2 shown, ..., 5 = Q5 shown, 6 = completed
- On each callback, check current step, save answer, increment step, show next question
- If user sends a random text while questionnaire is active → still route to AI chat but record that questionnaire is incomplete

**Option B — aiogram FSM:**
- Use `StatesGroup` with states for each question
- Problem: state is lost on bot restart. A lead mid-questionnaire would get stuck.
- Not recommended for this reason.

**Go with Option A.** Stateless, survives restarts, queryable in CRM.

### New Column

```sql
ALTER TABLE leads ADD COLUMN IF NOT EXISTS questionnaire_step INTEGER DEFAULT 0;
```

Add to the same migration file `003_questionnaire.sql`.

### Flow Logic (pseudocode)

```python
# In handlers/start.py — modify the /start handler:
async def cmd_start(message, command):
    # ... existing lead capture logic ...
    
    # After language selection, check if questionnaire is completed
    lead = await db.get_lead(user.id)
    if not lead.get("questionnaire_completed"):
        # Start questionnaire instead of showing main menu
        await show_question_1(message, lang)
        await db.update_lead(user.id, questionnaire_step=1)
    else:
        # Returning user — show main menu
        await message.answer(welcome_text, reply_markup=main_menu_keyboard(lang))
```

```python
# In handlers/questionnaire.py:

@router.callback_query(F.data.startswith("q_biz_"))
async def handle_business_type(callback):
    # Extract business type from callback_data
    # Save to leads.business_type
    # If "other" → ask for free text, stay on step 1
    # Otherwise → show Q2, set step = 2

@router.callback_query(F.data.startswith("q_svc_"))
async def handle_service_toggle(callback):
    # Toggle service in the selections list
    # Update button display (add/remove ✅)
    # Use safe_edit() to update in place

@router.callback_query(F.data == "q_svc_done")
async def handle_service_done(callback):
    # Save service_interest array
    # Show Q3, set step = 3

@router.callback_query(F.data.startswith("q_mkt_"))
async def handle_marketing_status(callback):
    # Save current_marketing
    # Show Q4, set step = 4

@router.callback_query(F.data.startswith("q_budget_"))
async def handle_budget(callback):
    # Save budget_range
    # Show Q5 (phone request), set step = 5

# Phone share handled by existing contact.py handler
# Skip handled by text match or inline button

async def complete_questionnaire(telegram_id, message, lang):
    # Set questionnaire_completed = True
    # Set questionnaire_completed_at = now()
    # Set questionnaire_step = 6
    # Recalculate lead score (questionnaire completion adds points)
    # Track event: "questionnaire_completed"
    # Show completion message + main menu
    # Notify admins about new qualified lead
```

### Handling Edge Cases

**Lead abandons mid-questionnaire and sends random text:**
- The `ai_chat.py` handler (registered last) catches it
- AI responds normally
- Questionnaire stays at whatever step they left off
- NOT blocked from using the bot

**Lead comes back after abandoning:**
- On next `/start`, check `questionnaire_step`
- If step > 0 and step < 6 → resume from where they left off
- Don't make them start over

**Lead already completed questionnaire and presses /start again:**
- Skip questionnaire entirely
- Show main menu directly (existing behavior)

**"Other" business type — waiting for free text:**
- Set a flag: `questionnaire_awaiting_text = True` on the lead (or use step = 1.5 convention)
- In `questionnaire.py`, add a `F.text` handler that checks this flag
- If flag is set → save text as `business_type_other`, clear flag, move to Q2
- Register this handler BEFORE `ai_chat.py` but use a filter: only match if the lead's `questionnaire_step == 1` and `business_type == 'other'`

**Language switch mid-questionnaire:**
- Show all questions in the lead's `preferred_lang`
- If they switch language via menu → redisplay current question in new language

---

## 4. AI Assistant Integration

### Update `user_info` String

In `ai_chat.py`, the `user_info` string built from lead data should now include questionnaire answers:

```python
user_info = (
    f"Name: {lead.get('first_name', '')} {lead.get('last_name', '')}\n"
    f"Username: @{lead.get('username', '')}\n"
    f"Phone: {lead.get('phone', 'not shared yet')}\n"
    f"Language: {lead.get('preferred_lang', 'uz')}\n"
    f"Business: {lead.get('business_type', 'unknown')}"
    f"{' (' + lead.get('business_type_other', '') + ')' if lead.get('business_type_other') else ''}\n"
    f"Interested in: {', '.join(lead.get('service_interest', []))}\n"
    f"Current marketing: {lead.get('current_marketing', 'unknown')}\n"
    f"Budget range: {lead.get('budget_range', 'unknown')}\n"
)
```

This gets injected into `{user_info}` in the system prompt. Now when a restaurant owner with a $500-1000 budget asks "qancha turadi?", the AI gives a relevant answer, not generic pricing.

### Update System Prompt

Add a section to `prompts/system_prompt.txt`:

```
USER CONTEXT:
{user_info}

Use this information to personalize your responses:
- Reference their specific business type when giving examples
- Recommend services that match their stated interests
- Be mindful of their budget range when discussing pricing
- If they said they have marketing but no results, focus on what might be wrong
- If they're starting from zero, explain the basics without jargon
- If user_info shows "unknown" for fields, the user hasn't completed the questionnaire — you can naturally ask these questions during conversation
```

---

## 5. Lead Scoring Updates

Update `db.recalculate_score()` to include questionnaire data:

```python
# Existing scoring...

# Questionnaire completion
if lead.get("questionnaire_completed"):
    score += 15  # completed full questionnaire = engaged lead

# Budget signals
budget = lead.get("budget_range", "")
if budget == "3000+":
    score += 20  # high-value prospect
elif budget in ("1000-3000",):
    score += 15
elif budget in ("500-1000",):
    score += 10
elif budget in ("200-500",):
    score += 5
# "unknown" adds 0

# Service interest breadth
services = lead.get("service_interest", [])
if len(services) >= 3:
    score += 10  # wants multiple services = higher deal size
elif len(services) >= 2:
    score += 5

# Marketing status signals
marketing = lead.get("current_marketing", "")
if marketing == "has_wants_scale":
    score += 10  # already spending, wants more = ready to buy
elif marketing == "has_no_results":
    score += 5   # has pain = motivated
```

---

## 6. CRM Dashboard Integration

### Lead Card Updates

Show questionnaire data on each lead card in the CRM:

- **Business type** — icon + label badge (e.g., 🍽 Ресторан)
- **Service interest** — tag chips (e.g., `SMM` `Targeting`)
- **Budget range** — colored badge (green for $3000+, yellow for $1000-3000, gray for unknown)
- **Marketing status** — text label
- **Questionnaire status** — ✅ completed or ⚠️ incomplete (step X/5)

### New Filters

Add to leads table filter bar:
- Filter by business type (dropdown)
- Filter by service interest (multi-select)
- Filter by budget range (dropdown)
- Filter by questionnaire completed (yes/no)

### New Analytics

**Dashboard widgets:**
- "Leads by business type" — pie/donut chart
- "Most requested services" — horizontal bar chart
- "Budget distribution" — bar chart
- "Questionnaire completion rate" — percentage (completed ÷ total × 100%)

**Useful cross-references:**
- Conversion rate by business type (which industries convert best)
- Average deal size by budget range (do people who say $1000-3000 actually pay that?)
- Conversion rate by service interest (which services are easiest to sell)

---

## 7. Admin Notifications

When a lead completes the questionnaire, notify admins with a rich summary:

```
🆕 Новый квалифицированный лид!

👤 Alisher Karimov (@alisher_k)
🏢 Ресторан / Кафе
📋 SMM, Таргетированная реклама
📊 Есть маркетинг, нет результатов
💰 $1 000 — $3 000 / мес
📱 +998 90 123 4567
📊 Источник: meta_restaurant_audit
⭐ Score: 75

Открыть в CRM →
```

This gives your team everything they need to make a call within seconds.

---

## 8. Event Tracking

Track these events in the `events` table during the questionnaire:

| event_type                    | event_data                                      |
|-------------------------------|--------------------------------------------------|
| `questionnaire_started`        | `{step: 1}`                                      |
| `questionnaire_q1_answered`    | `{business_type: "restaurant"}`                  |
| `questionnaire_q2_answered`    | `{services: ["smm", "targeting"]}`               |
| `questionnaire_q3_answered`    | `{current_marketing: "has_no_results"}`          |
| `questionnaire_q4_answered`    | `{budget_range: "1000-3000"}`                    |
| `questionnaire_q5_answered`    | `{phone_shared: true}` or `{phone_skipped: true}`|
| `questionnaire_completed`      | `{total_time_seconds: 45}`                       |
| `questionnaire_abandoned`      | `{abandoned_at_step: 3}`                         |

This data feeds the CRM analytics: "Where in the questionnaire are we losing people?"

---

## 9. Questionnaire Funnel Analytics (CRM)

New section in CRM dashboard: "Воронка анкеты"

```
Started questionnaire:     100 leads  (100%)
Q1 Business type answered:  92 leads  (92%)  — 8% drop
Q2 Service interest:        85 leads  (85%)  — 7% drop
Q3 Marketing status:        82 leads  (82%)  — 3% drop
Q4 Budget range:            70 leads  (70%)  — 12% drop  ← biggest drop!
Q5 Phone shared:            55 leads  (55%)  — 15% drop
Completed:                  55 leads  (55%)
```

If Q4 (budget) has the biggest drop → consider making it optional or moving it later.
If Q5 (phone) has the biggest drop → that's normal, but test different copy.

This funnel is computed from the `events` table by counting each `questionnaire_qN_answered` event.

---

## 10. Graceful Degradation (Partial Questionnaire Handling)

### For leads who abandon mid-questionnaire:

**In AI chat:** If questionnaire is incomplete, the AI should naturally ask the missing questions during conversation. Add to system prompt:

```
If the user hasn't completed the questionnaire (some fields show "unknown"):
- Don't interrogate them
- Weave questions naturally into conversation
- Example: after discussing services, ask "Aytgancha, hozir marketing qilyapsizmi?"
- Example: after showing interest, ask "Taxminan qanday byudjet o'ylab qo'ygansiz?"
- Only ask one question per message, don't stack them
```

**In scheduled follow-ups (Phase 1 scheduler):** Add a job that checks for incomplete questionnaires older than 2 hours. Send a gentle nudge:

```
UZ: Salom! Anketani yakunlamadingiz. Sizga eng mos xizmatni taklif qilishimiz uchun bir necha savolga javob bering 🙏
RU: Привет! Вы не завершили анкету. Ответьте на пару вопросов, чтобы мы подобрали лучшее решение 🙏
```

With a button: "Davom etish / Продолжить" → resumes from last unanswered step.

---

## 11. Files to Create / Modify

| File | Action | What |
|------|--------|------|
| `database/migrations/003_questionnaire.sql` | CREATE | New columns on leads table |
| `bot/handlers/questionnaire.py` | CREATE | Full questionnaire flow handler |
| `bot/handlers/start.py` | MODIFY | After language selection → redirect to questionnaire if not completed |
| `bot/handlers/contact.py` | MODIFY | Handle phone share during Q5, call `complete_questionnaire()` |
| `bot/handlers/ai_chat.py` | MODIFY | Update `user_info` builder with questionnaire fields |
| `bot/main.py` | MODIFY | Register `questionnaire.router` after `start` but before others |
| `bot/texts.py` | MODIFY | Add all questionnaire strings (UZ + RU) |
| `bot/keyboards/questionnaire.py` | CREATE | All questionnaire keyboard layouts |
| `bot/services/db_service.py` | MODIFY | Add `update_questionnaire_field()` helper, update `recalculate_score()` |
| `bot/prompts/system_prompt.txt` | MODIFY | Add user context usage instructions |
| `CLAUDE.md` | MODIFY | Document questionnaire handler, router order, state management |

---

## 12. Build Rules (specific to questionnaire)

1. **All questionnaire callbacks use `q_` prefix** — easy to identify and route.

2. **Use `safe_edit()` for all button updates** — matches existing bot pattern.

3. **Q2 multi-select edits the same message** — don't send new messages per toggle.

4. **Never block access to main menu** — if lead sends /start or types a message mid-questionnaire, it works. Questionnaire can be resumed later.

5. **Router order is critical** — questionnaire router MUST be after start but before menu and ai_chat. Otherwise questionnaire callbacks will be caught by wrong handlers.

6. **ReplyKeyboard pattern for Q5** — follow the existing pattern from CLAUDE.md: ReplyKeyboard for phone share, then ReplyKeyboardRemove + InlineKeyboard for completion.

7. **Existing leads who already use the bot** — they already have `questionnaire_completed = FALSE` (new column default). On their next `/start`, they'll be prompted with the questionnaire. This is fine — they get a one-time "help us know you better" flow. Or you can set `questionnaire_completed = TRUE` for all existing leads via SQL if you don't want to retro-prompt them.

8. **Track everything** — every answer, every skip, every abandonment goes to the events table.

---

## 13. Verification Checklist

After building, test these scenarios:

- [ ] New lead from ad → language select → full questionnaire → phone shared → main menu
- [ ] New lead → language select → Q1 answered → Q2 answered → user sends random text → AI responds → user presses /start → resumes at Q3
- [ ] New lead → language select → completes questionnaire without phone → skip → main menu works
- [ ] New lead picks "Other" business type → types response → Q2 appears
- [ ] Q2 multi-select: tap SMM (✅ appears), tap Bot (✅ appears), tap SMM again (✅ removed), tap Done → saves ["bot"]
- [ ] Existing lead presses /start → questionnaire already completed → goes straight to main menu
- [ ] Admin runs /leads → sees business type, budget, services on each lead
- [ ] AI chat references lead's business type and budget in responses
- [ ] CRM shows questionnaire data on lead cards
- [ ] CRM filters by business type and budget work
