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
```

`booking_status` is denormalized for quick CRM filtering ("show me everyone with a session this week"). The `bookings` table is the source of truth; `leads.booking_status` mirrors the most recent booking's status.

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

### 6.3 Copy reframe (drop "audit" packaging)

In `OB_T` dictionary and slide labels:

| Old | New |
|---|---|
| `ob_tagline: "От первого объявления до закрытой сделки — одна система."` | (keep) |
| `done_sub: "Спасибо. Партнёр свяжется в течение 24 часов..."` | `"Спасибо. Контекст получен. Выберите удобное время для бесплатной стратегической сессии — на встрече разберём бизнес и подготовим аудит вместе с вами."` |
| Done-screen CTA: (close button) | Add: "Выбрать время" → opens schedule tab |
| Hero subtitle / about page mentions of "audit" as deliverable | Reframe to "стратегическая сессия" |

### 6.4 Existing contact paths in TWA

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

### 7.3 What stays as-is

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
