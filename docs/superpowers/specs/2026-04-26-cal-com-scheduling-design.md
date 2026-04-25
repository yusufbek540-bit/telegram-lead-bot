# Cal.com Self-Serve Scheduling — Design Spec

**Date:** 2026-04-26
**Status:** Approved, ready for implementation plan
**Branch:** `feat/cal-scheduling`

---

## 1. Goal

Replace every "request a callback / talk to a manager" flow in the bot ecosystem with a single self-serve scheduling path: user picks a slot for a free strategic session via a Cal.com calendar embedded inside the TWA. The audit is delivered live during the session, not as a deliverable after the questionnaire.

## 2. Positioning Pivot

The questionnaire has been built around a "Free Audit" framing — answer 5 Q's, get an audit. We are pivoting to:

- **Questionnaire** = lightweight business intake to prep for the strategy session
- **Strategy session** = where the audit + brief is delivered live (~30 min)
- "Free Audit" stops being a post-questionnaire deliverable and becomes the value prop *of the session itself*

The 5-question flow stays mechanically — vertical, ad spend, channels, CRM, top problem are decent intake regardless. Only the packaging changes.

## 3. Architecture

### 3.1 Components

- **TWA** (`twa/index.html`) — adds a `Schedule` section containing Cal.com inline iframe (`@calcom/embed-snippet`). Pre-fills name and passes `telegram_id` and `lang` as Cal.com booking metadata.
- **Cal.com** — already configured at `cal.com/mqsd-agency/strategy`. We add a webhook pointing at our Vercel function for `BOOKING_CREATED`, `BOOKING_RESCHEDULED`, `BOOKING_CANCELLED`.
- **Vercel serverless function** — new `twa/api/cal-webhook.js`. On webhook fire: HMAC-verifies signature, writes booking to Supabase, sends Telegram messages to user + admins via Bot API.
- **Supabase** — new `bookings` table + two new columns on `leads`.
- **Bot** — replaces all callback / contact CTAs with "Записаться на сессию" → opens TWA `?tab=schedule`.

### 3.2 Why webhook on Vercel, not bot

The bot runs aiogram polling on Railway with no public HTTP. Vercel functions are already the pattern for HTTP endpoints in this codebase (`api/admin-tg.js`, `api/live-chat.js`). The webhook function writes Supabase + uses Telegram Bot API to notify — no bot code change needed for webhook handling.

### 3.3 Data flow

```
User completes questionnaire → "Pick a time" CTA → TWA #schedule tab
  → Cal.com iframe (with telegram_id, lang in metadata)
  → User picks slot → Cal.com finalizes booking
  → Cal.com fires webhook → Vercel /api/cal-webhook
    → Verify HMAC signature
    → Upsert into bookings table
    → Update leads.booking_status='scheduled', leads.next_session_at
    → Send Telegram confirmation to user
    → Send Telegram alert to ADMIN_IDS
```

## 4. Data Model

### 4.1 New table: `bookings`

```sql
-- database/migrations/016_bookings.sql
create table if not exists bookings (
  id              bigserial primary key,
  telegram_id     bigint references leads(telegram_id) on delete cascade,
  cal_booking_id  text unique not null,           -- Cal.com booking UID
  cal_booking_uid text,                            -- short uid for reschedule URLs
  scheduled_at    timestamptz not null,
  ends_at         timestamptz,
  status          text not null default 'scheduled', -- scheduled | rescheduled | cancelled
  attendee_name   text,
  attendee_email  text,
  reschedule_url  text,
  cancel_url      text,
  raw_payload     jsonb,
  created_at      timestamptz default now(),
  updated_at      timestamptz default now()
);

create index if not exists bookings_telegram_id_idx on bookings(telegram_id);
create index if not exists bookings_status_idx on bookings(status);
create index if not exists bookings_scheduled_at_idx on bookings(scheduled_at);
```

### 4.2 New columns on `leads`

```sql
alter table leads add column if not exists booking_status text;       -- null | scheduled | cancelled | completed
alter table leads add column if not exists next_session_at timestamptz;
alter table leads add column if not exists website text;              -- intake: business website (optional)
alter table leads add column if not exists social_handle text;        -- intake: any social platform handle (optional, free text)
```

`booking_status` is denormalized for quick CRM filtering ("show me everyone with a session this week"). The `bookings` table is the source of truth; `leads.booking_status` mirrors the most recent booking's status.

### 4.3 Semantic shift: `business_name` column

The `business_name` column was being repurposed in the previous refactor to hold "top problem" free text. We are reverting it to its original semantic — the actual name of the business. The questionnaire's Q5 changes correspondingly (see §6.3 and §7.4).

No data migration required. Existing rows where `business_name` holds top-problem text will be left as-is; the field will become correct from the next questionnaire submission onward. CRM admins can spot-clean outlier rows manually if needed.

## 5. Cal.com Configuration

Done by the human in the Cal.com dashboard (UI only, no code):

- Event: `cal.com/mqsd-agency/strategy` (already exists)
- Add webhook → URL `https://twa-jet.vercel.app/api/cal-webhook`
- Triggers (only these three):
  - `BOOKING_CREATED` (Бронирование создано)
  - `BOOKING_RESCHEDULED` (Бронирование изменено)
  - `BOOKING_CANCELLED` (Бронирование отменено)
- Secret: generate random 32-char string, save same value to Vercel env as `CAL_WEBHOOK_SECRET`
- Custom Payload Template: OFF (default JSON)
- Optional: restrict booking page language to RU

## 6. TWA Changes

### 6.1 New Schedule section

Add a new section/tab to `twa/index.html`:

```html
<section id="schedule" class="tab-section" hidden>
  <h2 data-ob="schedule_title">Бесплатная стратегическая сессия</h2>
  <p data-ob="schedule_sub">Выберите удобное время — на встрече разберём бизнес и подготовим аудит вместе с вами. ~30 минут.</p>
  <div id="cal-embed"></div>
</section>
```

JS:
```js
// On schedule tab show:
import("https://app.cal.com/embed/embed.js").then(...);
Cal("init", "strategy", {origin: "https://cal.com"});
Cal.ns.strategy("inline", {
  elementOrSelector: "#cal-embed",
  config: {
    layout: "month_view",
    name: lead.first_name || "",
    metadata: {
      telegram_id: String(tgUser.id),
      lang: obState.lang
    }
  },
  calLink: "mqsd-agency/strategy"
});
```

### 6.2 Tab routing

Existing TWA already has tab navigation. Add `?tab=schedule` URL param handling so the bot can deep-link directly to this tab.

### 6.3 Q5 intake fields (replaces top-problem text)

Slide 5 of the TWA questionnaire changes from a single text input ("Опишите коротко вашу главную проблему") to three fields:

| Field | Required | Persists to | Notes |
|---|---|---|---|
| Business name | **yes** | `leads.business_name` | "Next" disabled until ≥2 chars |
| Website | no | `leads.website` | If present, light validation (must contain `.`) |
| Social handle | no | `leads.social_handle` | Free text — accepts `@username`, `t.me/...`, full URL, etc. |

Slide footer: "Next" enabled when business name is filled. "Skip" still skips to slide 6 (phone).

OB_T copy updates:
- `q5_title` → `"Расскажите о бизнесе"`
- `q5_sub` → `"Это поможет нам подготовиться к встрече"`
- New labels: `q5_biz_label`, `q5_biz_placeholder`, `q5_web_label`, `q5_web_placeholder`, `q5_social_label`, `q5_social_placeholder`

`obSendData()` payload gains `website` and `social_handle` fields. The TWA handler in `bot/handlers/twa.py` writes these directly to the new `leads` columns (no normalization needed — they are free text).

### 6.4 Copy reframe (drop "audit" packaging)

In `OB_T` dictionary and slide labels:

| Old | New |
|---|---|
| `ob_tagline: "От первого объявления до закрытой сделки — одна система."` | (keep) |
| `done_sub: "Спасибо. Партнёр свяжется в течение 24 часов..."` | `"Спасибо. Контекст получен. Выберите удобное время для бесплатной стратегической сессии — на встрече разберём бизнес и подготовим аудит вместе с вами."` |
| Done-screen CTA: (close button) | Add: "Выбрать время" → opens schedule tab |
| Hero subtitle / about page mentions of "audit" as deliverable | Reframe to "стратегическая сессия" |

### 6.5 Brand alignment — full TWA static copy rewrite

The TWA still carries the legacy "AI marketing for everyone" copy across hero, services, about, and footer. This task brings every static surface in line with the new MQSD positioning.

**Hard rules applied everywhere:**
- Zero mentions of "AI", "AI-powered", "AI-кейсы", "GPT", or any model self-id
- No "для всех бизнесов" / "со всеми работаем" framing
- Three named verticals only: real-estate developers, private clinics, education/coaching
- Formal RU вы, no emoji theatre, "Bепло, по делу" tone
- Service ladder: Free Strategy Session → System Build → Self-Drive vs Co-Pilot

**Sections to rewrite in `twa/index.html`:**

1. **Hero** — three-layer stack:
   - Hook: `"Performance-маркетинг, который окупается с первого месяца."`
   - Promise: `"Строим систему за дни. Запускаем — приводит лиды. Управляем — закрываем сделки."`
   - Proof: `"От рекламы до продажи — одна команда отвечает за выручку."`
   - CTA: "Записаться на стратегическую сессию"

2. **Services / "Что делаем"** — replaced entirely. Detailed in §6.6 below.

3. **About / "О нас"** — strategic sales-system partner identity:
   - Lead: `"Мы не агентство. Мы внешний performance-департамент — отвечаем за выручку, не за охваты."`
   - Body covers: ownership of full funnel (content → ads → leads → sales), вертикальная специализация, KPI-привязанные обязательства.

4. **Vertical chips / industry section** — show only the three active verticals with one-liners for each. Drop the 12-vertical legacy chip strip.

5. **Footer / contact** — replace any "позвоните / напишите менеджеру" with single CTA block leading to schedule tab.

UZ static text stays as-is (deprioritized); RU is the source of truth.

### 6.6 Services section

A dedicated services section with four offerings. The Free Audit is positioned as a scarcity-limited offer (10 founding-client slots) and is the anchor of the section. The other three follow the brief's ladder with brief overviews and pricing logic — **no self-service checkout, no quote calculator** (per brief: "pricing is a sales conversation").

**Section header:**
- Title: `"Услуги"`
- Subtitle: `"От аудита до полного управления воронкой — выбираете уровень включённости."`

#### 6.6.1 Service 1 — Free Audit (scarcity-limited)

Anchored at the top of the section, visually distinct from the others (e.g. different background tint, "ограничено" badge).

**Card content:**
- Badge: `"ОГРАНИЧЕННОЕ ПРЕДЛОЖЕНИЕ"`
- Title: `"Бесплатный аудит + стратегическая сессия"`
- Sub: `"30 минут со старшим стратегом. Разбираем вашу воронку, показываем точки потерь, согласовываем KPI."`
- Scarcity indicator (visual progress bar):
  - Counter text: `"6 из 10 мест занято"`
  - Sub: `"Осталось 4 места до конца месяца"`
  - Bar: 60% filled, accent color
- Includes list:
  - Аудит текущих рекламных каналов и расходов
  - Анализ воронки от трафика до сделки
  - Рекомендации по 3 быстрым улучшениям
  - Бриф системы под ваш бизнес (если решите строить)
- CTA: `"Забронировать аудит"` → opens TWA `?tab=schedule`
- Fine print: `"Аудит бесплатен. Никаких обязательств. Только для бизнесов из недвижимости, медицины и образования."`

**Implementation note for the counter:**
- For launch: hardcoded `6/10` in HTML. Can be edited manually as bookings come in.
- Optional follow-up (out of scope for this plan): wire to `bookings` table — count `status='scheduled'` in current month, cap display at 10.

When 10/10 is reached, replace CTA with: `"Все места на этот месяц заняты — оставьте контакт, мы откроем следующую партию."` and route to a waitlist flow (also out of scope).

#### 6.6.2 Service 2 — System Build

**Card content:**
- Title: `"Построение системы"`
- Sub: `"Полная воронка от рекламы до CRM — за 4–8 недель."`
- What's inside (concise list):
  - Контент-движок и продакшн (видео, креативы, посты)
  - Рекламная инфраструктура (Meta / Google / Telegram Ads)
  - Лендинг или Telegram-бот для захвата лидов
  - CRM-сцепка и автоматизация
  - Аналитика и дашборды
- Pricing logic: `"$4 000 – $12 000"` + `"Финальная цена зависит от объёма контента, сложности воронки и количества каналов. Точную стоимость согласуем после стратегической сессии."`
- CTA: `"Обсудить на сессии"` → schedule tab (no direct buy)

#### 6.6.3 Service 3 — Self-Drive

**Card content:**
- Title: `"Self-Drive"`
- Sub: `"Мы строим — ваша команда управляет."`
- For whom: `"Подходит, если у вас есть собственный маркетолог или менеджер, способный вести систему ежедневно."`
- What's included:
  - Передача системы под ключ
  - Документация и обучение команды (8 часов)
  - Месяц поддержки и консультаций
  - Шаблоны процессов, скриптов, отчётов
- Pricing logic: `"Включено в стоимость System Build. Дополнительная плата за обучение или продление поддержки — обсуждается."`
- CTA: `"Уточнить на сессии"` → schedule tab

#### 6.6.4 Service 4 — Co-Pilot (recommended)

Visually marked as "рекомендуем" / "best fit" since this is the highest-margin offer.

**Card content:**
- Badge: `"РЕКОМЕНДУЕМ"`
- Title: `"Co-Pilot"`
- Sub: `"Мы строим, мы и управляем — отвечаем за результат."`
- For whom: `"Подходит, если у вас нет внутренней команды или вы хотите снять с себя операционку и сфокусироваться на продажах."`
- What's included:
  - Всё из System Build + Self-Drive
  - Ежедневное управление трафиком и контентом
  - Лид-менеджмент и квалификация
  - Еженедельные отчёты и стратегические созвоны
  - Поддержка отдела продаж (скрипты, обучение, аналитика)
  - Постоянная оптимизация и масштабирование
- Pricing logic: `"$1 500 – $6 000 / мес + % от рекламного бюджета"` + `"Размер ретейнера зависит от объёма работ. Процент от рекламного бюджета — обычно 10–15%. Точную ставку согласуем после стратегической сессии."`
- CTA: `"Обсудить на сессии"` → schedule tab

**Note across all paid services:** No "купить", "добавить в корзину", "заказать" CTAs. Every CTA leads to schedule. Pricing is shown as a *range with logic*, not a fixed quote.

### 6.7 Methodology section (replaces cases / portfolio)

Cases / portfolio section in current TWA is removed and replaced with a **"Как мы работаем"** section that positions MQSD as performance marketing experts owning the entire sales funnel — content → ads → leads → sales. Detailed enough to substitute for the trust signals a cases section would normally carry.

**Section header:**
- Title: `"Как мы работаем"`
- Subtitle: `"Полный цикл performance-маркетинга — от первого касания до закрытой сделки. Одна команда отвечает за результат."`

**Four stages, each as a separate card/block:**

**Stage 1 — Стратегия и диагностика**
- Lede: `"30-минутная стратегическая сессия — бесплатно. Разбираем бизнес, аудируем воронку, согласовываем KPI."`
- Bullet points:
  - Аудит текущей воронки: где утекают лиды, где переплачиваете за трафик, где ломается продажа
  - Стратегия: сегмент, оффер, каналы, метрики
  - Бриф системы: что строим, сроки, KPI на 30 / 60 / 90 дней
- Deliverable: `"Документ-бриф + согласованный KPI"`

**Stage 2 — Построение системы**
- Lede: `"Дни, а не месяцы. Пока конкуренты согласовывают ТЗ, ваша система уже принимает лидов."`
- Bullet points:
  - **Контент-движок** — посты, рилсы, видео, рекламные креативы. Месячный план + продакшн.
  - **Рекламная инфраструктура** — Meta Ads, Google Ads, Telegram Ads. Аккаунты, пиксели, события, аудитории.
  - **Воронка захвата** — лендинг или Telegram-бот. Квалификация на входе.
  - **CRM-сцепка** — лиды сразу в вашу или нашу систему, с тегами и статусами.
  - **Автоматизация** — напоминания, follow-up'ы, сегментация, retargeting.
- Deliverable: `"Работающая система за 5–10 рабочих дней — готова принимать трафик."`

**Stage 3 — Запуск и трафик**
- Lede: `"С первого дня — данные. Не «посмотрим через месяц». Каждый день — измерение, корректировка, новые гипотезы."`
- Bullet points:
  - **Платный трафик** — ежедневное управление: ставки, бюджеты, креативы, аудитории
  - **Контент-производство** — еженедельный поток органики и рекламных креативов
  - **Еженедельные отчёты** — что сработало, что нет, куда идём дальше
  - **A/B-тесты** — креативы, оферы, лендинги, текст в боте
- Deliverable: `"Целевые лиды по согласованной цене, с предсказуемой динамикой."`

**Stage 4 — Конверсия и масштаб**
- Lede: `"Лиды без сделок — деньги в трубу. Мы не уходим, пока система не закрывает сделки."`
- Bullet points:
  - **Лид-менеджмент** — квалификация, скоринг, ранжирование. Менеджер получает только готовых клиентов.
  - **CRM-сопровождение** — статусы, follow-up'ы, выявление узких мест в продажах
  - **Поддержка отдела продаж** — скрипты, материалы, обучение менеджеров (Co-Pilot) или полное ведение (Full-Cycle)
  - **Оптимизация** — ежемесячный пересмотр стратегии на основе данных по сделкам, не только по лидам
  - **Масштабирование** — когда юнит-экономика подтверждена, увеличиваем бюджеты и каналы
- Deliverable: `"Предсказуемый поток оплаченных сделок и готовый к масштабированию pipeline."`

**Closing band (after the four stages):**
- `"Мы не агентство. Мы внешний performance-департамент — отвечаем за выручку, не за охваты."`
- CTA below: "Записаться на стратегическую сессию"

**Layout note:** keep the visual structure from the current cases section (card grid / vertical timeline / whatever exists), just swap content. Do not introduce a new visual language.

### 6.8 Existing contact paths in TWA

Any existing "Связаться / запросить звонок" buttons inside the TWA point to schedule tab.

## 7. Bot Changes

### 7.1 Copy reframe

`bot/handlers/start.py` audit nudge (lines 79-90):
- Old: `"Чтобы подготовить ваш бесплатный аудит, ответьте на 5 коротких вопросов..."` / button: `"Запросить бесплатный аудит"`
- New: `"Чтобы мы подготовились к стратегической сессии, ответьте на 5 коротких вопросов..."` / button: `"Пройти короткую анкету"`

`bot/texts.py`:
- `q_complete` (RU): replace `"партнёр свяжется в 24 часа"` with intake → schedule pivot
- `partner_handoff_received`: rewrite as schedule redirect

`bot/prompts/system_prompt.txt`:
- Ladder section: `"Free Audit → Build"` → `"Free Strategy Session (audit + brief delivered live) → Build"`
- Hard rules: keep "never mention AI", drop any wording that frames audit as a post-questionnaire deliverable

`bot/handlers/questionnaire.py`:
- `_notify_admins_qualified` header: `<b>Заявка на бесплатный аудит</b>` → `<b>Новая анкета — клиент готов к сессии</b>`
- Update the admin notification body to surface the new intake fields: business name, website (or "—"), social handle (or "—") — replacing the "Top problem" line

### 7.2 CTA rewiring

**Main menu** (`bot/keyboards/main_menu.py`):
- Remove "Заказать звонок" button
- Add "📅 Записаться на сессию" button → opens TWA via `WebAppInfo(url=f"{TWA_URL}?tab=schedule&lang={lang}")`

**`/contact` command** (`bot/handlers/start.py`):
- Replace phone-share CTA with `WebAppInfo` to schedule tab. If lead already has phone, still show schedule CTA (not "we already have your number").

**Questionnaire completion** (`bot/handlers/questionnaire.py:complete_questionnaire`):
- After phone share, send TWO messages (per CLAUDE.md note: ReplyKeyboard dismissal can't co-exist with an inline keyboard in one message):
  1. Completion ack with `t("q_complete", lang)` + `ReplyKeyboardRemove()` to clear the contact-share keyboard
  2. New message with the "Выбрать время" inline `WebAppInfo` button → TWA `?tab=schedule`
- The new `q_complete` text already pivots to the session pitch (see §7.1).

**Partner-handoff fallback** (`bot/handlers/ai_chat.py`):
- Currently catches all unmatched text and forwards to admins via `_notify_managers`, marks `live_chat=True`, persists message
- New: respond with `"Чтобы обсудить вашу задачу, выберите время для стратегической сессии — мы свяжемся точно в это время и обсудим бизнес."` + WebAppInfo button. Drop the `_notify_managers` call. Drop the `live_chat=True` write. Still persist user message to conversations table for CRM context.

**`/ask` admin command:** unchanged. Still uses `crm_ai.py`. Admin-only.

### 7.3 Bot questionnaire Q5 changes

`bot/handlers/questionnaire.py` step 5 currently expects a single free-text message ("top problem"). Change it to a three-step inline mini-flow within step 5:

- **5a:** prompt for business name → store text → continue
- **5b:** prompt for website with inline "Пропустить" button → store text or null → continue
- **5c:** prompt for social handle with inline "Пропустить" button → store text or null → advance to step 6 (phone)

Implementation pattern: keep `questionnaire_step=5` for all three sub-prompts; add a `questionnaire_substep` text column on `leads` (or use an existing unused field) to track 5a / 5b / 5c. Persist business name to `leads.business_name`, website to `leads.website`, social handle to `leads.social_handle`.

`bot/keyboards/questionnaire.py`:
- Remove `q5_skip_keyboard` (the old single skip-button for top-problem text)
- Add `q5b_skip_keyboard` and `q5c_skip_keyboard` (inline "Пропустить" for website + social)

`bot/texts.py` adds: `q5a_prompt`, `q5b_prompt`, `q5c_prompt`, `q5_biz_invalid` (for too-short input).

### 7.4 Score recalculation update

`bot/services/db_service.py:recalculate_score` currently scores `+10` if `business_name` (top-problem text) was provided. Change this to:
- `+5` if `business_name` is set (intake completion)
- `+5` if `website` is set (signal of an established business)

Drop the "top-problem text provided" rationale since the field no longer carries that meaning.

### 7.5 What stays as-is

- Phone-share at questionnaire step 6: still happens, still triggers admin "qualified lead" notification. Phone is collected before scheduling because (a) it's in-flow already, (b) it's a backup contact if user bails before booking.
- All admin commands (`/leads`, `/lead`, `/stats`, `/export`, `/ask`, `/jobs`, etc.)
- Live-chat messages from admin → user (admin → user direction unaffected)

## 8. Vercel Webhook Function

`twa/api/cal-webhook.js`:

```js
// Pseudocode shape
import crypto from "crypto";

export default async function handler(req, res) {
  if (req.method !== "POST") return res.status(405).end();

  // 1. Verify signature
  const signature = req.headers["x-cal-signature-256"];
  const secret = process.env.CAL_WEBHOOK_SECRET;
  const rawBody = JSON.stringify(req.body);
  const expected = crypto.createHmac("sha256", secret).update(rawBody).digest("hex");
  if (signature !== expected) return res.status(401).json({error: "invalid signature"});

  // 2. Parse event
  const { triggerEvent, payload } = req.body;
  const telegramId = parseInt(payload.metadata?.telegram_id || "0", 10);
  if (!telegramId) return res.status(200).json({ok: true, note: "no telegram_id"});

  // 3. Dispatch on event type
  const supabase = createClient(SUPABASE_URL, SUPABASE_SERVICE_KEY);
  const botToken = process.env.BOT_TOKEN;

  switch (triggerEvent) {
    case "BOOKING_CREATED":
      await upsertBooking(supabase, payload, telegramId, "scheduled");
      await updateLead(supabase, telegramId, "scheduled", payload.startTime);
      await sendTgMessage(botToken, telegramId, formatUserConfirmation(payload));
      await notifyAdmins(botToken, formatAdminAlert(payload, "created"));
      break;
    case "BOOKING_RESCHEDULED":
      await upsertBooking(supabase, payload, telegramId, "rescheduled");
      await updateLead(supabase, telegramId, "scheduled", payload.startTime);
      await sendTgMessage(botToken, telegramId, formatUserReschedule(payload));
      await notifyAdmins(botToken, formatAdminAlert(payload, "rescheduled"));
      break;
    case "BOOKING_CANCELLED":
      await markBookingCancelled(supabase, payload);
      await updateLead(supabase, telegramId, "cancelled", null);
      await sendTgMessage(botToken, telegramId, formatUserCancellation(payload));
      await notifyAdmins(botToken, formatAdminAlert(payload, "cancelled"));
      break;
  }

  return res.status(200).json({ok: true});
}
```

### 8.1 Required Vercel env vars (twa project)

- `CAL_WEBHOOK_SECRET` — HMAC secret matching Cal.com's webhook config
- `BOT_TOKEN` — Telegram Bot API token (already present for `admin-tg.js`)
- `SUPABASE_URL` — already present
- `SUPABASE_SERVICE_KEY` — service-role key. Anon key won't have insert/update permissions on `bookings` and `leads`. Add this if not already set.

### 8.2 Telegram message templates

**User confirmation (RU, `BOOKING_CREATED`):**
```
✓ Сессия назначена на {date} в {time} (Tashkent).

Что дальше:
• За 24 часа до встречи — напоминание
• За 1 час — ссылка на видеовстречу
• На сессии — разбор бизнеса + бесплатный аудит

Если планы изменятся: {reschedule_url}
```

**User reschedule (RU):**
```
✓ Сессия перенесена на {new_date} в {new_time}.
```

**User cancellation (RU):**
```
Сессия отменена. Хотите выбрать другое время? {schedule_link}
```

**Admin alert (RU):**
```
📅 [created|rescheduled|cancelled]
{name} (@{username}) — {date} {time}
Lead: /lead {telegram_id}
```

## 9. CRM Dashboard

Small additive change to `crm/index.html`:
- Add `booking_status` and `next_session_at` to the `leads` SELECT
- Add a "Scheduled this week" filter chip
- Show booking status badge on lead cards (none / scheduled / cancelled)
- New tab "Sessions" listing upcoming bookings (queries `bookings` table)

## 10. Out of Scope

- Reschedule/cancel UI inside TWA — Cal.com handles natively via reschedule_url / cancel_url
- SMS / email notifications — Cal.com sends those automatically
- Timezone picker — Cal.com auto-detects user TZ
- Round-robin between team members — single Cal.com event for now; can add later
- Polling fallback if webhooks fail — Cal.com webhook delivery is reliable; revisit if we see drops
- UZ language for booking page — Cal.com doesn't support; falls back to RU/EN. UZ remains deprioritized per existing direction.

## 11. Migration / Rollout

1. Apply DB migration `016_bookings.sql` in Supabase SQL Editor
2. Set Vercel env vars (`CAL_WEBHOOK_SECRET`, `SUPABASE_SERVICE_KEY`)
3. Deploy webhook function (`vercel --prod`)
4. Save Cal.com webhook config (URL + secret + 3 triggers)
5. Test booking end-to-end: pick slot → confirm Telegram messages + Supabase row land
6. Push bot copy + CTA changes (Railway auto-redeploys)
7. Deploy TWA with schedule section (Vercel)

## 12. Success Criteria

- Booking a slot in Cal.com via TWA results in: (a) row in `bookings` table, (b) Telegram confirmation to user, (c) Telegram alert to admins, (d) `leads.booking_status='scheduled'`
- Cancelling a booking in Cal.com flows through the same path with `status='cancelled'` and Telegram cancellation notice to both parties
- Main menu has no "request callback" / "talk to manager" button anywhere — only "Записаться на сессию"
- TWA hero / about / questionnaire all reframed: "audit" is no longer presented as a post-questionnaire deliverable; "strategy session" is the conversion event
