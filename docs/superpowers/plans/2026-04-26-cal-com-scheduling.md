# Cal.com Self-Serve Scheduling — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace every callback / talk-to-manager flow in the bot ecosystem with Cal.com self-serve scheduling, embedded inline in the TWA. Deliver brand-aligned TWA copy, restructured services section with scarcity-limited Free Audit, 4-stage methodology section, and rewired bot CTAs. Update questionnaire Q5 to collect business name (required) + website + social handle.

**Architecture:** TWA hosts a Cal.com inline iframe in a `Schedule` tab. Cal.com fires webhooks to a new Vercel serverless function (`twa/api/cal-webhook.js`) which verifies HMAC, persists bookings to Supabase, and notifies user + admins via Telegram Bot API. Bot copy and CTAs across `start`, `texts`, `questionnaire`, `ai_chat`, `keyboards/main_menu` repoint at the schedule tab. Questionnaire Q5 splits into 3 sub-prompts (5a/5b/5c). Out of scope: reschedule/cancel UI in TWA, SMS/email, timezone picker, round-robin.

**Tech Stack:** aiogram 3.x (bot, polling on Railway), Vercel serverless (Node.js ESM), Supabase Postgres, Cal.com (booking SaaS), vanilla JS in static HTML for TWA, plain SQL migrations.

**Spec reference:** `docs/superpowers/specs/2026-04-26-cal-com-scheduling-design.md`

---

## File Structure

**Create:**
- `database/migrations/019_bookings_and_intake.sql` — bookings table + 4 lead columns
- `twa/api/cal-webhook.js` — Cal.com webhook receiver
- `bot/handlers/tests/__init__.py` — test package marker (if missing)
- `bot/handlers/tests/test_recalculate_score.py` — score logic test
- `bot/services/tests/__init__.py` — test package marker (if missing)

**Modify:**
- `bot/texts.py` — q_complete, partner_handoff_received, q5a/b/c prompts, admin notification labels
- `bot/handlers/start.py` — audit nudge copy + button label, /contact redirect to schedule
- `bot/handlers/questionnaire.py` — Q5 sub-flow (5a/5b/5c), admin notification body, two-message completion pattern
- `bot/handlers/ai_chat.py` — fallback redirects to schedule (no manager handoff)
- `bot/handlers/twa.py` — write website + social_handle from TWA payload
- `bot/keyboards/main_menu.py` — replace callback button with schedule WebApp button
- `bot/keyboards/questionnaire.py` — replace q5_skip_keyboard with q5b_skip + q5c_skip
- `bot/services/db_service.py` — recalculate_score: drop top-problem +10, add business_name +5 + website +5
- `bot/prompts/system_prompt.txt` — ladder reframe (free strategy session, audit delivered live)
- `twa/index.html` — schedule tab, slide 5 intake fields, full hero/services/methodology rewrite, OB_T dictionary
- `crm/index.html` — surface booking_status, next_session_at; new Sessions tab

**Test:**
- `bot/services/tests/test_score_intake.py` — recalculate_score with new fields
- `bot/handlers/tests/test_questionnaire_q5_split.py` — Q5 sub-flow state machine

---

## Task 1: DB migration — bookings table + intake columns

**Files:**
- Create: `database/migrations/019_bookings_and_intake.sql`

**Why this task first:** Every downstream task (webhook, TWA, bot Q5) needs these columns to exist. Apply in Supabase SQL Editor before deploying anything else.

- [ ] **Step 1: Write the migration SQL**

Create `database/migrations/019_bookings_and_intake.sql`:

```sql
-- 019_bookings_and_intake.sql
-- Cal.com bookings table + intake field columns on leads.

create table if not exists bookings (
  id              bigserial primary key,
  telegram_id     bigint references leads(telegram_id) on delete cascade,
  cal_booking_id  text unique not null,
  cal_booking_uid text,
  scheduled_at    timestamptz not null,
  ends_at         timestamptz,
  status          text not null default 'scheduled',
  attendee_name   text,
  attendee_email  text,
  reschedule_url  text,
  cancel_url      text,
  raw_payload     jsonb,
  created_at      timestamptz default now(),
  updated_at      timestamptz default now()
);

create index if not exists bookings_telegram_id_idx on bookings(telegram_id);
create index if not exists bookings_status_idx       on bookings(status);
create index if not exists bookings_scheduled_at_idx on bookings(scheduled_at);

alter table leads add column if not exists booking_status   text;
alter table leads add column if not exists next_session_at  timestamptz;
alter table leads add column if not exists website          text;
alter table leads add column if not exists social_handle    text;
```

- [ ] **Step 2: Apply in Supabase**

Open Supabase project → SQL Editor → paste the file contents → Run. Verify: `select column_name from information_schema.columns where table_name='leads' and column_name in ('booking_status','next_session_at','website','social_handle');` returns 4 rows. Verify `select count(*) from bookings;` returns 0 without error.

- [ ] **Step 3: Commit**

```bash
git add database/migrations/019_bookings_and_intake.sql
git commit -m "feat(db): bookings table + intake columns (website, social_handle, booking_status, next_session_at)"
```

---

## Task 2: Vercel webhook function

**Files:**
- Create: `twa/api/cal-webhook.js`

**Why now:** Set up the webhook receiver before flipping the Cal.com webhook live so Cal.com's test ping succeeds on save.

- [ ] **Step 1: Write the webhook handler**

Create `twa/api/cal-webhook.js`:

```js
// Cal.com webhook receiver. Triggered on BOOKING_CREATED / BOOKING_RESCHEDULED
// / BOOKING_CANCELLED. Verifies HMAC signature, persists to Supabase bookings
// table, updates leads.booking_status + next_session_at, and notifies the
// user + admins via Telegram Bot API.
//
// Required Vercel env vars:
//   CAL_WEBHOOK_SECRET     - matches the secret saved in Cal.com webhook config
//   BOT_TOKEN              - Telegram bot token (already present)
//   ADMIN_IDS              - comma-separated Telegram admin IDs
//   SUPABASE_URL           - Supabase project URL
//   SUPABASE_SERVICE_KEY   - service-role key (NOT anon — needs insert/update on bookings/leads)

import crypto from 'node:crypto';

const TZ = 'Asia/Tashkent';

function verifySignature(rawBody, signatureHeader, secret) {
    if (!signatureHeader || !secret) return false;
    const expected = crypto.createHmac('sha256', secret).update(rawBody).digest('hex');
    try {
        return crypto.timingSafeEqual(Buffer.from(signatureHeader, 'hex'), Buffer.from(expected, 'hex'));
    } catch {
        return false;
    }
}

function fmtDateTime(iso) {
    const d = new Date(iso);
    const date = d.toLocaleDateString('ru-RU', { day: '2-digit', month: 'long', timeZone: TZ });
    const time = d.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit', timeZone: TZ });
    return { date, time };
}

async function supabaseRequest(path, opts = {}) {
    const url = `${process.env.SUPABASE_URL}/rest/v1/${path}`;
    const res = await fetch(url, {
        ...opts,
        headers: {
            apikey: process.env.SUPABASE_SERVICE_KEY,
            Authorization: `Bearer ${process.env.SUPABASE_SERVICE_KEY}`,
            'Content-Type': 'application/json',
            Prefer: 'return=representation',
            ...(opts.headers || {}),
        },
    });
    if (!res.ok) {
        const txt = await res.text();
        throw new Error(`Supabase ${res.status}: ${txt}`);
    }
    return res.status === 204 ? null : res.json();
}

async function tgSendMessage(chatId, text) {
    const url = `https://api.telegram.org/bot${process.env.BOT_TOKEN}/sendMessage`;
    const res = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ chat_id: chatId, text, parse_mode: 'HTML' }),
    });
    return res.ok;
}

async function notifyAdmins(text) {
    const ids = (process.env.ADMIN_IDS || '').split(',').map(s => s.trim()).filter(Boolean);
    await Promise.all(ids.map(id => tgSendMessage(id, text)));
}

export default async function handler(req, res) {
    if (req.method !== 'POST') return res.status(405).end();

    const rawBody = typeof req.body === 'string' ? req.body : JSON.stringify(req.body);
    const signature = req.headers['x-cal-signature-256'];
    if (!verifySignature(rawBody, signature, process.env.CAL_WEBHOOK_SECRET)) {
        return res.status(401).json({ error: 'invalid signature' });
    }

    let body;
    try {
        body = typeof req.body === 'string' ? JSON.parse(req.body) : req.body;
    } catch {
        return res.status(400).json({ error: 'invalid json' });
    }

    const trigger = body.triggerEvent;
    const payload = body.payload || {};
    const meta = payload.metadata || {};
    const telegramId = parseInt(meta.telegram_id || '0', 10);

    if (!telegramId) {
        return res.status(200).json({ ok: true, note: 'no telegram_id in metadata' });
    }

    const calBookingId = String(payload.uid || payload.bookingId || payload.id || '');
    const startTime = payload.startTime || payload.start || null;
    const endTime = payload.endTime || payload.end || null;
    const attendee = (payload.attendees && payload.attendees[0]) || {};
    const rescheduleUrl = payload.rescheduleUrl || payload.rescheduleLink || null;
    const cancelUrl = payload.cancelUrl || payload.cancelLink || null;

    let nextStatus;
    let userMessage;
    let adminLabel;

    if (trigger === 'BOOKING_CREATED') {
        nextStatus = 'scheduled';
        if (startTime) {
            const { date, time } = fmtDateTime(startTime);
            userMessage = `✓ Сессия назначена на <b>${date}</b> в <b>${time}</b> (Tashkent).\n\nЧто дальше:\n• За 24 часа — напоминание\n• За 1 час — ссылка на встречу\n• На сессии — разбор бизнеса и бесплатный аудит` +
                (rescheduleUrl ? `\n\nИзменить время: ${rescheduleUrl}` : '');
        } else {
            userMessage = '✓ Сессия назначена. Подробности придут отдельным письмом.';
        }
        adminLabel = '📅 Новая запись';
    } else if (trigger === 'BOOKING_RESCHEDULED') {
        nextStatus = 'scheduled';
        if (startTime) {
            const { date, time } = fmtDateTime(startTime);
            userMessage = `✓ Сессия перенесена на <b>${date}</b> в <b>${time}</b> (Tashkent).`;
        } else {
            userMessage = '✓ Сессия перенесена. Подробности придут отдельным письмом.';
        }
        adminLabel = '📅 Перенос';
    } else if (trigger === 'BOOKING_CANCELLED') {
        nextStatus = 'cancelled';
        userMessage = 'Сессия отменена. Если планы изменятся — выберите другое время в нашем боте.';
        adminLabel = '📅 Отмена';
    } else {
        return res.status(200).json({ ok: true, note: `unhandled trigger ${trigger}` });
    }

    // Upsert booking row
    await supabaseRequest('bookings', {
        method: 'POST',
        headers: { Prefer: 'resolution=merge-duplicates,return=representation' },
        body: JSON.stringify({
            telegram_id: telegramId,
            cal_booking_id: calBookingId,
            cal_booking_uid: payload.uid || null,
            scheduled_at: startTime,
            ends_at: endTime,
            status: nextStatus,
            attendee_name: attendee.name || null,
            attendee_email: attendee.email || null,
            reschedule_url: rescheduleUrl,
            cancel_url: cancelUrl,
            raw_payload: body,
            updated_at: new Date().toISOString(),
        }),
    });

    // Update lead
    const leadPatch = {
        booking_status: nextStatus,
        next_session_at: nextStatus === 'cancelled' ? null : startTime,
    };
    await supabaseRequest(`leads?telegram_id=eq.${telegramId}`, {
        method: 'PATCH',
        body: JSON.stringify(leadPatch),
    });

    // Notify user + admins
    await tgSendMessage(telegramId, userMessage);
    const adminBody = `<b>${adminLabel}</b>\n${attendee.name || '—'} (@${meta.username || '—'})\n` +
        (startTime ? `${fmtDateTime(startTime).date} ${fmtDateTime(startTime).time}\n` : '') +
        `Lead: /lead ${telegramId}`;
    await notifyAdmins(adminBody);

    return res.status(200).json({ ok: true });
}
```

- [ ] **Step 2: Add Vercel env vars**

In Vercel `twa` project → Settings → Environment Variables, add:
- `CAL_WEBHOOK_SECRET` = (32+ char random string, generate via `openssl rand -hex 32`)
- `SUPABASE_SERVICE_KEY` = service-role key from Supabase → Project Settings → API → service_role
- `SUPABASE_URL` = Supabase project URL (if not already present)
- Confirm `BOT_TOKEN` and `ADMIN_IDS` already present (used by `admin-tg.js`)

- [ ] **Step 3: Deploy and smoke-test**

```bash
cd twa
npx vercel --prod --yes
```

Test signature rejection:
```bash
curl -X POST https://twa-jet.vercel.app/api/cal-webhook \
  -H 'Content-Type: application/json' \
  -d '{"triggerEvent":"BOOKING_CREATED","payload":{"metadata":{"telegram_id":"123"}}}'
```
Expected: HTTP 401 with `{"error":"invalid signature"}` — confirms HMAC gate works.

- [ ] **Step 4: Configure Cal.com webhook**

In Cal.com → Settings → Developer → Webhooks → Add:
- URL: `https://twa-jet.vercel.app/api/cal-webhook`
- Triggers: `BOOKING_CREATED`, `BOOKING_RESCHEDULED`, `BOOKING_CANCELLED`
- Secret: paste the same value used in `CAL_WEBHOOK_SECRET`
- Save. (Cal.com's save-time test ping should now return 200 since we're past signature verification — actually it will 200 because no telegram_id, with note.)

- [ ] **Step 5: Commit**

```bash
git add twa/api/cal-webhook.js
git commit -m "feat(twa): Cal.com webhook receiver — HMAC verify, Supabase upsert, Telegram notifications"
```

---

## Task 3: TWA Schedule section + tab routing

**Files:**
- Modify: `twa/index.html`

- [ ] **Step 1: Add Schedule section markup**

Locate the existing tab/section structure (search for `class="tab-section"` or main app section nodes near the bottom of the body) and insert a new section after the existing tabs:

```html
<section id="tab-schedule" class="tab-section" hidden>
  <div class="schedule-header">
    <h2 data-ob="schedule_title">Бесплатная стратегическая сессия</h2>
    <p data-ob="schedule_sub">Выберите удобное время — на встрече разберём бизнес и подготовим аудит вместе с вами. ~30 минут.</p>
  </div>
  <div id="cal-embed"></div>
</section>
```

- [ ] **Step 2: Add Cal.com embed script + init**

Inside the existing `<script>` block (or a new one before `</body>`):

```js
// Cal.com inline embed — loads only when the schedule tab is shown.
let calEmbedLoaded = false;
function loadCalEmbed() {
    if (calEmbedLoaded) return;
    calEmbedLoaded = true;
    (function (C, A, L) {
        const p = function (a, ar) { a.q.push(ar); };
        const d = C.document;
        C.Cal = C.Cal || function () {
            const cal = C.Cal; const ar = arguments;
            if (!cal.loaded) { cal.ns = {}; cal.q = cal.q || []; d.head.appendChild(d.createElement('script')).src = A; cal.loaded = true; }
            if (ar[0] === L) {
                const api = function () { p(api, arguments); };
                const namespace = ar[1]; api.q = api.q || [];
                if (typeof namespace === 'string') { cal.ns[namespace] = cal.ns[namespace] || api; p(cal.ns[namespace], ar); p(cal, ['initNamespace', namespace]); }
                else p(cal, ar); return;
            }
            p(cal, ar);
        };
    })(window, 'https://app.cal.com/embed/embed.js', 'init');

    const lead = window.__LEAD__ || {};
    const tg = window.Telegram && window.Telegram.WebApp;
    const tgUser = tg && tg.initDataUnsafe && tg.initDataUnsafe.user || {};

    Cal('init', 'strategy', { origin: 'https://cal.com' });
    Cal.ns.strategy('inline', {
        elementOrSelector: '#cal-embed',
        config: {
            layout: 'month_view',
            name: lead.first_name || tgUser.first_name || '',
            metadata: {
                telegram_id: String(tgUser.id || lead.telegram_id || ''),
                lang: (window.obState && window.obState.lang) || 'ru',
                username: tgUser.username || '',
            },
        },
        calLink: 'mqsd-agency/strategy',
    });
}
```

- [ ] **Step 3: Wire URL hash deep-link**

Locate the existing tab-switching function (search `tab-section` or `showTab`). Add `?tab=schedule` handling:

```js
function applyUrlTab() {
    const params = new URLSearchParams(window.location.search);
    const tab = params.get('tab');
    if (tab === 'schedule') {
        showTab('schedule');
        loadCalEmbed();
    }
}

// Modify the existing showTab(name) — when name === 'schedule', call loadCalEmbed()
// at the end. If showTab does not exist, find the function that toggles
// .tab-section[hidden] and add the loadCalEmbed() call there.

// On DOMContentLoaded after the main app shows:
window.addEventListener('DOMContentLoaded', () => {
    // ... existing init ...
    applyUrlTab();
});
```

- [ ] **Step 4: Manual smoke test**

Local-preview:
```bash
cd twa && python3 -m http.server 8000
```
Open `http://localhost:8000/index.html?tab=schedule` directly in browser (note: Cal.com embed may not load fully outside Telegram WebApp context — verify the section renders, the `#cal-embed` div is present, and no JS console errors).

Then deploy:
```bash
npx vercel --prod --yes
```

Open the bot, complete questionnaire (or use existing main menu) → manually navigate to `https://twa-jet.vercel.app/?tab=schedule` via Telegram WebApp → confirm Cal.com calendar renders inline.

- [ ] **Step 5: Commit**

```bash
git add twa/index.html
git commit -m "feat(twa): inline Cal.com schedule tab with deep-link support"
```

---

## Task 4: TWA Q5 intake fields (replaces top-problem text)

**Files:**
- Modify: `twa/index.html`
- Modify: `bot/handlers/twa.py`

- [ ] **Step 1: Replace slide 5 markup**

Find the existing slide-5 block (search for `id="ob-biz-name-input"` or the top-problem prompt) and replace with:

```html
<section class="ob-slide" data-slide="5" hidden>
  <h2 data-ob="q5_title">Расскажите о бизнесе</h2>
  <p data-ob="q5_sub">Это поможет нам подготовиться к встрече</p>

  <div class="ob-input-group">
    <label data-ob="q5_biz_label">Название бизнеса <span class="ob-req">*</span></label>
    <input type="text" id="ob-biz-name-input" data-ob-placeholder="q5_biz_placeholder" maxlength="100" />
  </div>

  <div class="ob-input-group">
    <label data-ob="q5_web_label">Сайт (если есть)</label>
    <input type="url" id="ob-website-input" data-ob-placeholder="q5_web_placeholder" maxlength="200" />
  </div>

  <div class="ob-input-group">
    <label data-ob="q5_social_label">Соцсети — любой профиль</label>
    <input type="text" id="ob-social-input" data-ob-placeholder="q5_social_placeholder" maxlength="200" />
  </div>
</section>
```

- [ ] **Step 2: Update OB_T copy keys**

In the `OB_T` dictionary, replace the old top-problem keys with:

```js
// Inside OB_T.ru:
q5_title: 'Расскажите о бизнесе',
q5_sub: 'Это поможет нам подготовиться к встрече',
q5_biz_label: 'Название бизнеса',
q5_biz_placeholder: 'Например: «Клиника N» или «Школа X»',
q5_web_label: 'Сайт (если есть)',
q5_web_placeholder: 'https://...',
q5_social_label: 'Соцсети — любой профиль',
q5_social_placeholder: '@instagram или t.me/handle',

// Mirror in OB_T.uz with literal RU text for now (UZ deprioritized):
q5_title: 'Бизнес ҳақида айтиб беринг',
q5_sub: 'Бу учрашувга тайёрланишга ёрдам беради',
q5_biz_label: 'Бизнес номи',
q5_biz_placeholder: 'Масалан: «Клиника N»',
q5_web_label: 'Сайт (агар бор бўлса)',
q5_web_placeholder: 'https://...',
q5_social_label: 'Ижтимоий тармоқлар — ҳар қандай профил',
q5_social_placeholder: '@instagram',
```

Also update existing `done_sub`:

```js
// OB_T.ru.done_sub:
done_sub: 'Спасибо. Контекст получен. Выберите удобное время для бесплатной стратегической сессии — на встрече разберём бизнес и подготовим аудит вместе с вами.',
```

- [ ] **Step 3: Update obState + obSendData**

In `obState.answers`:

```js
const obState = {
    slide: 1,
    lang: 'ru',
    answers: {
        business_type: null,
        service_interest: [],
        current_marketing: null,
        budget_range: null,
        phone: '',
        business_name: '',
        website: '',
        social_handle: '',
        contact_shared: false,
    },
};
```

In `obNext()` for slide === 5, replace existing single-input read with:

```js
if (slide === 5) {
    const biz = document.getElementById('ob-biz-name-input').value.trim();
    const web = document.getElementById('ob-website-input').value.trim();
    const soc = document.getElementById('ob-social-input').value.trim();
    if (biz.length < 2) return; // safety; obUpdateFooter should already disable
    obState.answers.business_name = biz;
    obState.answers.website = web || '';
    obState.answers.social_handle = soc || '';
    obGoToSlide(6);
}
```

In `obSendData()` payload, add the two new fields:

```js
const payload = {
    action: 'questionnaire_complete',
    lang: obState.lang,
    business_type: obState.answers.business_type || '',
    service_interest: obState.answers.service_interest,
    current_marketing: obState.answers.current_marketing || '',
    budget_range: obState.answers.budget_range || '',
    phone: obState.answers.phone || '',
    business_name: obState.answers.business_name || '',
    website: obState.answers.website || '',
    social_handle: obState.answers.social_handle || '',
    contact_shared: !!obState.answers.contact_shared,
};
```

- [ ] **Step 4: Wire next-button enable to business name input**

In `obUpdateFooter()` slide===5 branch, replace `bizVal` reference to read from the same biz input id (already does — confirm threshold remains `< 2`):

```js
} else if (slide === 5) {
    nextBtn.textContent = t.next;
    nextBtn.style.display = 'block';
    const bizVal = document.getElementById('ob-biz-name-input').value.trim();
    nextBtn.disabled = bizVal.length < 2;
    skipBtn.style.display = 'block';
    skipBtn.textContent = t.skip;
}
```

In `showOnboarding()` add `input` listeners for all three inputs:

```js
['ob-biz-name-input', 'ob-website-input', 'ob-social-input'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.addEventListener('input', () => { if (obState.slide === 5) obUpdateFooter(); });
});
```

- [ ] **Step 5: Persist new fields in `bot/handlers/twa.py`**

In `handle_web_app_data` `questionnaire_complete` branch, add:

```python
if data.get("website"):
    updates["website"] = data["website"][:200]
if data.get("social_handle"):
    updates["social_handle"] = data["social_handle"][:200]
```

Insert these alongside the existing `if data.get("phone"): ...` and `if data.get("business_name"): ...` block.

- [ ] **Step 6: Syntax check + deploy**

```bash
python3 -m py_compile bot/handlers/twa.py
cd twa && npx vercel --prod --yes && cd ..
```

- [ ] **Step 7: Commit**

```bash
git add twa/index.html bot/handlers/twa.py
git commit -m "feat: Q5 intake fields — business name (req), website, social handle"
```

---

## Task 5: TWA brand alignment — hero / about / verticals / footer

**Files:**
- Modify: `twa/index.html`

**Scope:** Rewrite static copy across hero, about, verticals strip, and footer. Drop all AI mentions. Apply three-layer hook + open-to-all-with-priority-verticals positioning. Visual structure stays intact.

- [ ] **Step 1: Rewrite hero**

Locate the hero section (search for class names like `hero`, `intro`, or the topmost h1/h2 outside onboarding). Replace headline + sub + CTA:

```html
<section class="hero">
  <h1>Performance-маркетинг, который окупается с первого месяца.</h1>
  <p class="hero-promise">Строим систему за дни. Запускаем — приводит лиды. Управляем — закрываем сделки.</p>
  <p class="hero-proof">От рекламы до продажи — одна команда отвечает за выручку.</p>
  <button class="hero-cta" onclick="showTab('schedule')">Записаться на стратегическую сессию</button>
</section>
```

- [ ] **Step 2: Rewrite About / "О нас"**

Find the about block. Replace with:

```html
<section class="about">
  <h2>О нас</h2>
  <p class="about-lead">Мы не агентство. Мы внешний performance-департамент — отвечаем за выручку, не за охваты.</p>
  <p>Берём на себя весь цикл: контент, реклама, захват лидов, CRM, поддержка отдела продаж. Приоритетная экспертиза — недвижимость, частная медицина, образование. Открыты к другим нишам — обсудим, подходит ли подход вашему бизнесу, на стратегической сессии.</p>
  <p>Каждое обязательство привязано к KPI. Если система не выходит на согласованные показатели — мы не пропадаем, а разбираемся почему.</p>
</section>
```

- [ ] **Step 3: Rewrite verticals strip**

Find the existing vertical chips/strip (search for "ниш" or industry chip class). Replace with three priority verticals + open-to-others closer:

```html
<section class="verticals">
  <h2>Приоритетные ниши</h2>
  <div class="vertical-cards">
    <div class="vertical-card">
      <h3>Недвижимость</h3>
      <p>Девелоперы и агентства. Воронки под живые объекты, отделы продаж и сезонный трафик.</p>
    </div>
    <div class="vertical-card">
      <h3>Частная медицина</h3>
      <p>Клиники и кабинеты. Качественный поток первичных пациентов, корректная квалификация на входе.</p>
    </div>
    <div class="vertical-card">
      <h3>Образование</h3>
      <p>Школы, курсы, коучинг. Запуски, потоковые наборы, удержание родителей и студентов.</p>
    </div>
  </div>
  <p class="verticals-note">Работаем и с другими нишами — обсудим, подходит ли подход вашему бизнесу, на стратегической сессии.</p>
</section>
```

- [ ] **Step 4: Sweep remaining AI mentions**

```bash
grep -nE "AI|ИИ|GPT|нейросет" twa/index.html
```

For each match, rewrite the surrounding sentence to remove the AI reference. Acceptable replacements: drop the word, replace with "автоматизация" if technical context, or rewrite the entire sentence around outcome (lead, sale, system) instead of technology.

After the sweep, re-run grep — expected: zero matches.

- [ ] **Step 5: Footer / CTA banners**

Locate any "Связаться с менеджером" / "Заказать звонок" / "Позвоните нам" banner or footer block. Replace each with:

```html
<div class="cta-banner">
  <p>Готовы обсудить? Запишитесь на бесплатную стратегическую сессию — 30 минут со старшим стратегом.</p>
  <button onclick="showTab('schedule')">Выбрать время</button>
</div>
```

- [ ] **Step 6: Manual smoke test**

```bash
cd twa && npx vercel --prod --yes
```

Open `https://twa-jet.vercel.app` in browser. Verify: no "AI" anywhere on the page (Cmd-F → "AI" → 0 matches), hero shows new copy, about leads with "Мы не агентство…", verticals strip shows 3 cards + "работаем и с другими нишами" closer.

- [ ] **Step 7: Commit**

```bash
git add twa/index.html
git commit -m "feat(twa): brand alignment — drop AI mentions, three-layer hero, performance-department about, priority-verticals strip"
```

---

## Task 6: TWA Services section — Free Audit scarcity + ladder

**Files:**
- Modify: `twa/index.html`

- [ ] **Step 1: Replace existing services markup**

Find the services section (search for "услуги" / "Services" / service tile class). Replace with:

```html
<section class="services">
  <h2>Услуги</h2>
  <p class="services-sub">От аудита до полного управления воронкой — выбираете уровень включённости.</p>

  <!-- Service 1 — Free Audit (scarcity) -->
  <div class="service-card service-card--featured">
    <div class="service-badge service-badge--limited">ОГРАНИЧЕННОЕ ПРЕДЛОЖЕНИЕ</div>
    <h3>Бесплатный аудит + стратегическая сессия</h3>
    <p class="service-sub">30 минут со старшим стратегом. Разбираем вашу воронку, показываем точки потерь, согласовываем KPI.</p>

    <div class="scarcity">
      <div class="scarcity-counter"><span id="scarcity-filled">6</span> из <span id="scarcity-total">10</span> мест занято</div>
      <div class="scarcity-bar"><div class="scarcity-bar-fill" id="scarcity-bar-fill" style="width:60%"></div></div>
      <div class="scarcity-sub">Осталось <span id="scarcity-remaining">4</span> места до конца месяца</div>
    </div>

    <ul class="service-includes">
      <li>Аудит текущих рекламных каналов и расходов</li>
      <li>Анализ воронки от трафика до сделки</li>
      <li>Рекомендации по 3 быстрым улучшениям</li>
      <li>Бриф системы под ваш бизнес (если решите строить)</li>
    </ul>

    <button class="service-cta service-cta--primary" onclick="showTab('schedule')">Забронировать аудит</button>
    <p class="service-finepoint">Аудит бесплатен. Никаких обязательств. Приоритетно — недвижимость, частная медицина, образование. Открыты и к другим нишам, обсудим на сессии.</p>
  </div>

  <!-- Service 2 — System Build -->
  <div class="service-card">
    <h3>Построение системы</h3>
    <p class="service-sub">Полная воронка от рекламы до CRM — за 4–8 недель.</p>
    <ul class="service-includes">
      <li>Контент-движок и продакшн (видео, креативы, посты)</li>
      <li>Рекламная инфраструктура (Meta / Google / Telegram Ads)</li>
      <li>Лендинг или Telegram-бот для захвата лидов</li>
      <li>CRM-сцепка и автоматизация</li>
      <li>Аналитика и дашборды</li>
    </ul>
    <div class="service-pricing">
      <div class="service-price">$4 000 – $12 000</div>
      <div class="service-price-logic">Финальная цена зависит от объёма контента, сложности воронки и количества каналов. Точную стоимость согласуем после стратегической сессии.</div>
    </div>
    <button class="service-cta" onclick="showTab('schedule')">Обсудить на сессии</button>
  </div>

  <!-- Service 3 — Self-Drive -->
  <div class="service-card">
    <h3>Self-Drive</h3>
    <p class="service-sub">Мы строим — ваша команда управляет.</p>
    <p class="service-for-whom">Подходит, если у вас есть собственный маркетолог или менеджер, способный вести систему ежедневно.</p>
    <ul class="service-includes">
      <li>Передача системы под ключ</li>
      <li>Документация и обучение команды (8 часов)</li>
      <li>Месяц поддержки и консультаций</li>
      <li>Шаблоны процессов, скриптов, отчётов</li>
    </ul>
    <div class="service-pricing">
      <div class="service-price-logic">Включено в стоимость System Build. Дополнительная плата за продление поддержки или расширенное обучение — обсуждается.</div>
    </div>
    <button class="service-cta" onclick="showTab('schedule')">Уточнить на сессии</button>
  </div>

  <!-- Service 4 — Co-Pilot -->
  <div class="service-card service-card--recommended">
    <div class="service-badge">РЕКОМЕНДУЕМ</div>
    <h3>Co-Pilot</h3>
    <p class="service-sub">Мы строим, мы и управляем — отвечаем за результат.</p>
    <p class="service-for-whom">Подходит, если у вас нет внутренней команды или вы хотите снять с себя операционку и сфокусироваться на продажах.</p>
    <ul class="service-includes">
      <li>Всё из System Build + Self-Drive</li>
      <li>Ежедневное управление трафиком и контентом</li>
      <li>Лид-менеджмент и квалификация</li>
      <li>Еженедельные отчёты и стратегические созвоны</li>
      <li>Поддержка отдела продаж (скрипты, обучение, аналитика)</li>
      <li>Постоянная оптимизация и масштабирование</li>
    </ul>
    <div class="service-pricing">
      <div class="service-price">$1 500 – $6 000 / мес + % от рекламного бюджета</div>
      <div class="service-price-logic">Размер ретейнера зависит от объёма работ. Процент от рекламного бюджета — обычно 10–15%. Точную ставку согласуем после стратегической сессии.</div>
    </div>
    <button class="service-cta service-cta--primary" onclick="showTab('schedule')">Обсудить на сессии</button>
  </div>
</section>
```

- [ ] **Step 2: Add minimal styles for the new structure**

Inside the existing `<style>` block, add (without changing global tokens):

```css
.services { padding: 32px 16px; }
.services-sub { color: var(--muted, #888); margin-bottom: 24px; }
.service-card { background: var(--card-bg, #1a1a1a); border-radius: 16px; padding: 24px; margin-bottom: 16px; }
.service-card--featured { background: linear-gradient(135deg, var(--accent-soft, #2a1f3d) 0%, var(--card-bg, #1a1a1a) 100%); border: 1px solid var(--accent, #7c5cff); }
.service-card--recommended { border: 1px solid var(--accent, #7c5cff); }
.service-badge { display: inline-block; padding: 4px 10px; border-radius: 999px; font-size: 11px; font-weight: 700; letter-spacing: 0.5px; background: var(--accent, #7c5cff); color: white; margin-bottom: 12px; }
.service-badge--limited { background: #d44; }
.service-sub { color: var(--muted, #aaa); margin-bottom: 12px; }
.service-for-whom { font-style: italic; color: var(--muted, #888); margin-bottom: 12px; font-size: 14px; }
.service-includes { list-style: none; padding: 0; margin: 16px 0; }
.service-includes li { padding: 6px 0 6px 24px; position: relative; font-size: 14px; }
.service-includes li::before { content: '✓'; position: absolute; left: 0; color: var(--accent, #7c5cff); font-weight: 700; }
.service-pricing { padding: 12px 0; border-top: 1px solid rgba(255,255,255,0.08); margin-top: 12px; }
.service-price { font-size: 22px; font-weight: 700; margin-bottom: 4px; }
.service-price-logic { font-size: 13px; color: var(--muted, #888); }
.service-cta { width: 100%; padding: 14px; border-radius: 12px; border: 1px solid var(--accent, #7c5cff); background: transparent; color: var(--accent, #7c5cff); font-weight: 600; cursor: pointer; margin-top: 12px; }
.service-cta--primary { background: var(--accent, #7c5cff); color: white; }
.service-finepoint { font-size: 12px; color: var(--muted, #888); margin-top: 12px; line-height: 1.5; }
.scarcity { background: rgba(255,255,255,0.04); border-radius: 12px; padding: 12px; margin: 16px 0; }
.scarcity-counter { font-weight: 700; margin-bottom: 8px; }
.scarcity-bar { height: 8px; background: rgba(255,255,255,0.08); border-radius: 4px; overflow: hidden; }
.scarcity-bar-fill { height: 100%; background: linear-gradient(90deg, #d44 0%, var(--accent, #7c5cff) 100%); transition: width 0.4s; }
.scarcity-sub { font-size: 13px; color: var(--muted, #888); margin-top: 8px; }
```

(Adjust CSS variables to match the existing design system if names differ. Inspect the current `:root` block in `twa/index.html` and reuse its variable names — fall back to the literals shown above only if no equivalent exists.)

- [ ] **Step 3: Manual verification**

Deploy and check:
```bash
cd twa && npx vercel --prod --yes
```

Open in browser: confirm 4 cards render, Free Audit shows "6 из 10 мест занято" + 60% bar + "Осталось 4 места" + restricted-niches fine print, Co-Pilot has "РЕКОМЕНДУЕМ" badge, all CTAs visible.

- [ ] **Step 4: Commit**

```bash
git add twa/index.html
git commit -m "feat(twa): services section — Free Audit (6/10 scarcity) + System Build / Self-Drive / Co-Pilot ladder with pricing logic"
```

---

## Task 7: TWA Methodology section — 4-stage "Как мы работаем"

**Files:**
- Modify: `twa/index.html`

- [ ] **Step 1: Locate and remove old cases/portfolio section**

Find the cases / portfolio / projects block (search for "кейс" / "портфолио" / "проекты" / `class="cases"`). Delete the entire block (markup + any styles unique to it).

- [ ] **Step 2: Insert methodology section in its place**

```html
<section class="methodology">
  <h2>Как мы работаем</h2>
  <p class="methodology-sub">Полный цикл performance-маркетинга — от первого касания до закрытой сделки. Одна команда отвечает за результат.</p>

  <!-- Stage 1 -->
  <div class="stage">
    <div class="stage-num">01</div>
    <h3>Стратегия и диагностика</h3>
    <p class="stage-lede">30-минутная стратегическая сессия — бесплатно. Разбираем бизнес, аудируем воронку, согласовываем KPI.</p>
    <ul class="stage-bullets">
      <li>Аудит текущей воронки: где утекают лиды, где переплачиваете за трафик, где ломается продажа</li>
      <li>Стратегия: сегмент, оффер, каналы, метрики</li>
      <li>Бриф системы: что строим, сроки, KPI на 30 / 60 / 90 дней</li>
    </ul>
    <div class="stage-deliverable"><strong>Результат:</strong> документ-бриф + согласованный KPI</div>
  </div>

  <!-- Stage 2 -->
  <div class="stage">
    <div class="stage-num">02</div>
    <h3>Построение системы</h3>
    <p class="stage-lede">Дни, а не месяцы. Пока конкуренты согласовывают ТЗ, ваша система уже принимает лидов.</p>
    <ul class="stage-bullets">
      <li><strong>Контент-движок</strong> — посты, рилсы, видео, рекламные креативы. Месячный план + продакшн.</li>
      <li><strong>Рекламная инфраструктура</strong> — Meta Ads, Google Ads, Telegram Ads. Аккаунты, пиксели, события, аудитории.</li>
      <li><strong>Воронка захвата</strong> — лендинг или Telegram-бот. Квалификация на входе.</li>
      <li><strong>CRM-сцепка</strong> — лиды сразу в вашу или нашу систему, с тегами и статусами.</li>
      <li><strong>Автоматизация</strong> — напоминания, follow-up'ы, сегментация, retargeting.</li>
    </ul>
    <div class="stage-deliverable"><strong>Результат:</strong> работающая система за 5–10 рабочих дней — готова принимать трафик.</div>
  </div>

  <!-- Stage 3 -->
  <div class="stage">
    <div class="stage-num">03</div>
    <h3>Запуск и трафик</h3>
    <p class="stage-lede">С первого дня — данные. Не «посмотрим через месяц». Каждый день — измерение, корректировка, новые гипотезы.</p>
    <ul class="stage-bullets">
      <li><strong>Платный трафик</strong> — ежедневное управление: ставки, бюджеты, креативы, аудитории</li>
      <li><strong>Контент-производство</strong> — еженедельный поток органики и рекламных креативов</li>
      <li><strong>Еженедельные отчёты</strong> — что сработало, что нет, куда идём дальше</li>
      <li><strong>A/B-тесты</strong> — креативы, оферы, лендинги, текст в боте</li>
    </ul>
    <div class="stage-deliverable"><strong>Результат:</strong> целевые лиды по согласованной цене, с предсказуемой динамикой.</div>
  </div>

  <!-- Stage 4 -->
  <div class="stage">
    <div class="stage-num">04</div>
    <h3>Конверсия и масштаб</h3>
    <p class="stage-lede">Лиды без сделок — деньги в трубу. Мы не уходим, пока система не закрывает сделки.</p>
    <ul class="stage-bullets">
      <li><strong>Лид-менеджмент</strong> — квалификация, скоринг, ранжирование. Менеджер получает только готовых клиентов.</li>
      <li><strong>CRM-сопровождение</strong> — статусы, follow-up'ы, выявление узких мест в продажах</li>
      <li><strong>Поддержка отдела продаж</strong> — скрипты, материалы, обучение менеджеров (Co-Pilot) или полное ведение (Full-Cycle)</li>
      <li><strong>Оптимизация</strong> — ежемесячный пересмотр стратегии на основе данных по сделкам, не только по лидам</li>
      <li><strong>Масштабирование</strong> — когда юнит-экономика подтверждена, увеличиваем бюджеты и каналы</li>
    </ul>
    <div class="stage-deliverable"><strong>Результат:</strong> предсказуемый поток оплаченных сделок и готовый к масштабированию pipeline.</div>
  </div>

  <div class="methodology-closer">
    <p>Мы не агентство. Мы внешний performance-департамент — отвечаем за выручку, не за охваты.</p>
    <button onclick="showTab('schedule')">Записаться на стратегическую сессию</button>
  </div>
</section>
```

- [ ] **Step 3: Add styles**

```css
.methodology { padding: 32px 16px; }
.methodology-sub { color: var(--muted, #aaa); margin-bottom: 32px; }
.stage { background: var(--card-bg, #1a1a1a); border-radius: 16px; padding: 24px; margin-bottom: 16px; position: relative; }
.stage-num { position: absolute; top: 16px; right: 16px; font-size: 36px; font-weight: 800; color: var(--accent, #7c5cff); opacity: 0.4; }
.stage h3 { margin-top: 0; padding-right: 60px; }
.stage-lede { color: var(--muted, #aaa); font-style: italic; margin-bottom: 16px; }
.stage-bullets { list-style: none; padding: 0; }
.stage-bullets li { padding: 8px 0 8px 24px; position: relative; font-size: 14px; line-height: 1.6; }
.stage-bullets li::before { content: '→'; position: absolute; left: 0; color: var(--accent, #7c5cff); font-weight: 700; }
.stage-deliverable { margin-top: 16px; padding: 12px; background: rgba(124, 92, 255, 0.08); border-radius: 8px; font-size: 14px; }
.methodology-closer { text-align: center; padding: 32px 16px; margin-top: 24px; }
.methodology-closer p { font-size: 18px; font-weight: 600; margin-bottom: 16px; }
.methodology-closer button { padding: 14px 28px; border-radius: 12px; background: var(--accent, #7c5cff); color: white; border: none; font-weight: 600; cursor: pointer; }
```

(Adjust to match existing design tokens.)

- [ ] **Step 4: Verify and deploy**

```bash
cd twa && npx vercel --prod --yes
```

Open in browser: 4 stages render in order, deliverable line shows on each, "Записаться на стратегическую сессию" button at the bottom routes to schedule tab.

- [ ] **Step 5: Commit**

```bash
git add twa/index.html
git commit -m "feat(twa): replace cases section with 4-stage methodology — full funnel ownership positioning"
```

---

## Task 8: Bot copy reframe — texts, system prompt, audit nudge

**Files:**
- Modify: `bot/texts.py`
- Modify: `bot/handlers/start.py`
- Modify: `bot/prompts/system_prompt.txt`

- [ ] **Step 1: Update `bot/texts.py`**

Find the `q_complete` key under `ru` and replace with:

```python
"q_complete": (
    "Спасибо. Контекст получен.\n\n"
    "Выберите удобное время для бесплатной стратегической сессии — "
    "на встрече разберём бизнес и подготовим аудит вместе с вами."
),
```

Find the `partner_handoff_received` key and replace with:

```python
"partner_handoff_received": (
    "Чтобы обсудить вашу задачу, выберите время для бесплатной "
    "стратегической сессии — мы свяжемся точно в это время и "
    "разберём бизнес."
),
```

Add new keys for Q5 sub-prompts (under `ru`):

```python
"q5a_prompt": "Как называется ваш бизнес? Введите название одним сообщением.",
"q5_biz_invalid": "Слишком коротко. Введите название бизнеса (минимум 2 символа).",
"q5b_prompt": "Есть ли у бизнеса сайт? Пришлите ссылку, или нажмите «Пропустить».",
"q5c_prompt": "Соцсети — любой профиль. Пришлите ссылку или @username, или нажмите «Пропустить».",
"q_skip_btn": "Пропустить",
```

Mirror under `uz` with literal RU text or rough UZ (UZ deprioritized — RU primary).

- [ ] **Step 2: Update `bot/handlers/start.py`**

Find the audit nudge block (around lines 79-99). Replace:

```python
if not q_done:
    if lang == "ru":
        twa_msg = (
            "Чтобы мы подготовились к встрече, ответьте "
            "на 5 коротких вопросов — около минуты."
        )
        btn_text = "Пройти короткую анкету"
    else:
        twa_msg = (
            "Учрашувга тайёрланишимиз учун 5 та қисқа саволга "
            "жавоб беринг — тахминан 1 дақиқа."
        )
        btn_text = "Қисқа сўровномани ўтиш"
```

For `cmd_contact`, replace the body so phone-share is replaced by schedule CTA:

```python
@router.message(Command("contact"))
async def cmd_contact(message: Message):
    lead = await db.get_lead(message.from_user.id)
    lang = lead.get("preferred_lang", config.DEFAULT_LANG) if lead else config.DEFAULT_LANG
    if lang == "ru":
        text = (
            "Чтобы обсудить ваш бизнес — выберите время для бесплатной "
            "стратегической сессии (~30 минут). Откройте календарь ниже."
        )
        btn = "Выбрать время"
    else:
        text = (
            "Бизнесингиз ҳақида гаплашиш учун — бепул стратегик сессия (~30 дақиқа) "
            "учун қулай вақтни танланг."
        )
        btn = "Вақтни танлаш"
    await message.answer(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(
                text=btn,
                web_app=WebAppInfo(url=f"{config.TWA_URL}?tab=schedule&lang={lang}"),
            )
        ]]),
    )
```

- [ ] **Step 3: Rewrite `bot/prompts/system_prompt.txt` ladder**

Open the file. Find the ladder section (likely contains "Free Audit → Build" or similar). Replace ladder block with:

```
SERVICE LADDER (always present in this order):
1. Free Strategy Session (~30 min, includes live audit + brief) — Cal.com self-serve booking inside the bot's TWA
2. System Build ($4K-$12K, 4-8 weeks)
3. Choice after build: Self-Drive (client team operates) OR Co-Pilot ($1.5K-$6K/mo + 10-15% of ad spend, we operate)

HARD RULES:
- Never mention "AI", "GPT", "neural network", or any model self-id
- Audit is delivered LIVE during the strategy session — never as a post-questionnaire deliverable
- Priority verticals: real-estate developers, private clinics, education/coaching. Open to other niches; that decision happens on the strategy session — never refuse a vertical in chat
- Pricing is a sales conversation. State ranges only when explicitly asked. Never quote a fixed number
- Formal RU вы. No emoji theatre.
```

Keep the rest of the file (positioning blurb, tone, examples) intact unless those sections also reference AI or audit-as-deliverable — sweep and rewrite those.

- [ ] **Step 4: Syntax check**

```bash
python3 -m py_compile bot/texts.py bot/handlers/start.py
```

- [ ] **Step 5: Commit**

```bash
git add bot/texts.py bot/handlers/start.py bot/prompts/system_prompt.txt
git commit -m "feat(bot): reframe copy — drop audit-as-deliverable, schedule-first CTAs, /contact opens calendar"
```

---

## Task 9: Bot questionnaire Q5 split (5a/5b/5c) + scoring

**Files:**
- Modify: `bot/handlers/questionnaire.py`
- Modify: `bot/keyboards/questionnaire.py`
- Modify: `bot/services/db_service.py`
- Create: `bot/services/tests/__init__.py` (if missing)
- Create: `bot/services/tests/test_score_intake.py`

- [ ] **Step 1: Write the failing score test**

Create `bot/services/tests/test_score_intake.py`:

```python
"""Unit tests for score recalculation against the new intake fields."""

import pytest

# We test the *scoring logic*, not the DB write. Extract a pure function
# `compute_score(lead, user_msg_count, event_types)` from db_service for
# testability. If not yet extracted, this test will fail at import time.

from bot.services.db_service import compute_score


def test_score_business_name_only():
    lead = {"phone": None, "email": None, "business_name": "Foo Clinic", "website": None}
    score = compute_score(lead, user_msg_count=0, event_types=set())
    # +5 business_name, no other signals
    assert score == 5


def test_score_business_name_and_website():
    lead = {"phone": None, "email": None, "business_name": "Foo Clinic", "website": "https://foo.com"}
    score = compute_score(lead, user_msg_count=0, event_types=set())
    assert score == 10


def test_score_no_intake_no_score():
    lead = {"phone": None, "email": None, "business_name": None, "website": None}
    score = compute_score(lead, user_msg_count=0, event_types=set())
    assert score == 0


def test_score_phone_plus_intake():
    lead = {"phone": "+998900000000", "email": None, "business_name": "Foo", "website": "https://foo.com"}
    score = compute_score(lead, user_msg_count=0, event_types=set())
    # 30 (phone) + 5 (business_name) + 5 (website)
    assert score == 40
```

Also create `bot/services/tests/__init__.py` (empty) if it doesn't exist.

- [ ] **Step 2: Run test to verify fails**

```bash
python3 -m pytest bot/services/tests/test_score_intake.py -v
```
Expected: ImportError on `compute_score` — confirms test fails before implementation.

- [ ] **Step 3: Extract `compute_score` from `recalculate_score`**

In `bot/services/db_service.py`, refactor `recalculate_score` to delegate to a pure function:

```python
def compute_score(lead: dict, user_msg_count: int, event_types: set) -> int:
    """Pure scoring function — no DB access, fully testable."""
    score = 0

    if lead.get("phone"):
        score += 30
    if lead.get("email"):
        score += 20

    if user_msg_count >= 10:
        score += 20
    elif user_msg_count >= 5:
        score += 15
    elif user_msg_count >= 2:
        score += 5

    if "twa_open" in event_types:
        score += 10
    if "callback_request" in event_types:
        score += 25
    if "projects" in event_types:
        score += 10
    if "services" in event_types:
        score += 5

    if lead.get("questionnaire_completed"):
        score += 15

    spend = lead.get("budget_range") or ""
    if spend == "q_spend_10k_plus":
        score += 25
    elif spend == "q_spend_3k_10k":
        score += 20
    elif spend == "q_spend_1k_3k":
        score += 10
    elif spend == "q_spend_lt1k":
        score += 5

    vertical = lead.get("business_type") or ""
    if vertical in ("q_v_realestate", "q_v_clinic", "q_v_education"):
        score += 10

    channels = lead.get("service_interest") or []
    if len(channels) >= 3:
        score += 10
    elif len(channels) >= 2:
        score += 5

    crm = lead.get("current_marketing") or ""
    if crm == "q_crm_yes":
        score += 10
    elif crm == "q_crm_sheet":
        score += 5

    # Intake fields (replaces old "top problem text" +10)
    if (lead.get("business_name") or "").strip():
        score += 5
    if (lead.get("website") or "").strip():
        score += 5

    return score


# Update the existing async DatabaseService.recalculate_score to use compute_score:
async def recalculate_score(self, telegram_id: int) -> int:
    lead = await self.get_lead(telegram_id)
    if not lead:
        return 0
    convos = await self.get_conversation(telegram_id, limit=100)
    user_msgs = [c for c in convos if c["role"] == "user"]
    events_result = (
        self.client.table("events")
        .select("event_type")
        .eq("telegram_id", telegram_id)
        .execute()
    )
    event_types = {e["event_type"] for e in events_result.data}
    score = compute_score(lead, len(user_msgs), event_types)
    await self.update_lead(telegram_id, lead_score=score)
    return score
```

- [ ] **Step 4: Run tests to verify pass**

```bash
python3 -m pytest bot/services/tests/test_score_intake.py -v
```
Expected: 4/4 pass.

- [ ] **Step 5: Update questionnaire keyboards**

In `bot/keyboards/questionnaire.py` remove `q5_skip_keyboard` (single skip button) and add two replacements:

```python
def q5b_skip_keyboard() -> InlineKeyboardMarkup:
    """Inline 'skip' for the optional website prompt (Q5b)."""
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="Пропустить", callback_data="q5b_skip"),
    ]])


def q5c_skip_keyboard() -> InlineKeyboardMarkup:
    """Inline 'skip' for the optional social handle prompt (Q5c)."""
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="Пропустить", callback_data="q5c_skip"),
    ]])
```

- [ ] **Step 6: Update questionnaire handler — Q5 sub-flow**

In `bot/handlers/questionnaire.py`:

Add a small in-memory state dict at module level (questionnaire is short-lived, so process-local state is acceptable; if running multi-instance the state can be ephemeral — falling through to step 6 cleanly):

```python
# Module-level: track the Q5 sub-step per user. Resets on questionnaire restart.
_q5_substep: dict[int, str] = {}  # telegram_id -> 'awaiting_biz' | 'awaiting_web' | 'awaiting_social'
```

Replace the existing step==5 text handler. Locate where the bot currently handles step==5 (free text top-problem), and replace its logic with:

```python
async def _handle_q5_text(message: Message, lang: str):
    tid = message.from_user.id
    sub = _q5_substep.get(tid, "awaiting_biz")
    text = (message.text or "").strip()

    if sub == "awaiting_biz":
        if len(text) < 2:
            await message.answer(t("q5_biz_invalid", lang))
            return
        await db.update_lead(tid, business_name=text[:100])
        _q5_substep[tid] = "awaiting_web"
        await message.answer(t("q5b_prompt", lang), reply_markup=q5b_skip_keyboard())
        return

    if sub == "awaiting_web":
        await db.update_lead(tid, website=text[:200])
        _q5_substep[tid] = "awaiting_social"
        await message.answer(t("q5c_prompt", lang), reply_markup=q5c_skip_keyboard())
        return

    if sub == "awaiting_social":
        await db.update_lead(tid, social_handle=text[:200])
        _q5_substep.pop(tid, None)
        await db.update_lead(tid, questionnaire_step=6)
        # advance to phone share — call existing helper that prompts Q6
        await _send_q6_phone_prompt(message, lang)
        return
```

Add callback handlers for the skip buttons:

```python
@router.callback_query(F.data == "q5b_skip")
async def q5b_skip_cb(cb: CallbackQuery):
    lang = await _get_lang(cb.from_user.id)
    _q5_substep[cb.from_user.id] = "awaiting_social"
    await cb.message.edit_text(t("q5c_prompt", lang), reply_markup=q5c_skip_keyboard())
    await cb.answer()


@router.callback_query(F.data == "q5c_skip")
async def q5c_skip_cb(cb: CallbackQuery):
    tid = cb.from_user.id
    lang = await _get_lang(tid)
    _q5_substep.pop(tid, None)
    await db.update_lead(tid, questionnaire_step=6)
    await cb.message.edit_text(t("q5_done_advance_to_phone", lang) if False else "Спасибо. Последний шаг ниже.")
    await _send_q6_phone_prompt(cb.message, lang)
    await cb.answer()
```

When step transitions FROM 4→5 (after CRM is answered), reset substep and send Q5a:

```python
# In the existing q4 handler that advances to step 5:
_q5_substep[tid] = "awaiting_biz"
await db.update_lead(tid, questionnaire_step=5)
await message.answer(t("q5a_prompt", lang))  # no reply markup — plain text
```

(`_send_q6_phone_prompt` and `_get_lang` are existing helpers; if they don't exist, locate the equivalent code that currently sends the phone prompt and the lang fetcher — wire those instead.)

- [ ] **Step 7: Update admin notification body**

In `_notify_admins_qualified` find the section that currently prints "Top problem". Replace with:

```python
biz = lead.get("business_name") or "—"
web = lead.get("website") or "—"
social = lead.get("social_handle") or "—"
# ... in the body string:
f"\n<b>Бизнес:</b> {biz}"
f"\n<b>Сайт:</b> {web}"
f"\n<b>Соцсети:</b> {social}"
```

- [ ] **Step 8: Run all tests**

```bash
python3 -m pytest bot/services/tests/ -v
python3 -m py_compile bot/handlers/questionnaire.py bot/keyboards/questionnaire.py bot/services/db_service.py
```

- [ ] **Step 9: Commit**

```bash
git add bot/handlers/questionnaire.py bot/keyboards/questionnaire.py bot/services/db_service.py bot/services/tests/
git commit -m "feat(bot): Q5 split (5a biz / 5b web / 5c social) + score on intake fields, drop top-problem +10"
```

---

## Task 10: Bot CTA rewiring — main menu, complete_questionnaire, ai_chat fallback

**Files:**
- Modify: `bot/keyboards/main_menu.py`
- Modify: `bot/handlers/questionnaire.py`
- Modify: `bot/handlers/ai_chat.py`

- [ ] **Step 1: Replace main menu callback button**

In `bot/keyboards/main_menu.py` find the existing "Заказать звонок" / contact button definition. Replace it with a WebApp button to the schedule tab:

```python
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from bot.config import config


def main_menu_keyboard(lang: str) -> InlineKeyboardMarkup:
    schedule_label = "📅 Записаться на сессию" if lang == "ru" else "📅 Сессияга ёзилиш"
    schedule_url = f"{config.TWA_URL}?tab=schedule&lang={lang}"

    rows = [
        [InlineKeyboardButton(text=schedule_label, web_app=WebAppInfo(url=schedule_url))],
        # ... keep the other existing buttons (services, faq, about, app/portfolio) ...
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)
```

(Preserve existing structure of the rest of the menu — only replace the callback button.)

- [ ] **Step 2: Update `complete_questionnaire` to use two-message pattern**

In `bot/handlers/questionnaire.py` find `complete_questionnaire`. Update to send (1) ack + ReplyKeyboardRemove, (2) inline schedule CTA:

```python
from aiogram.types import (
    Message,
    ReplyKeyboardRemove,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    WebAppInfo,
)


async def complete_questionnaire(message: Message, lang: str):
    # ... existing logic that finalizes the lead, fires admin notification, etc ...
    await db.update_lead(message.from_user.id, questionnaire_completed=True, questionnaire_step=7)

    # 1) Completion ack — clears the contact-share ReplyKeyboard
    await message.answer(t("q_complete", lang), reply_markup=ReplyKeyboardRemove())

    # 2) Schedule CTA — inline button can't co-exist with ReplyKeyboardRemove in same message
    schedule_label = "Выбрать время" if lang == "ru" else "Вақтни танлаш"
    await message.answer(
        "👇" if lang == "ru" else "👇",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(
                text=schedule_label,
                web_app=WebAppInfo(url=f"{config.TWA_URL}?tab=schedule&lang={lang}"),
            )
        ]]),
    )

    # ... existing main_menu welcome (or remove if redundant with schedule CTA) ...
```

If the existing function also sends the main_menu welcome, keep that as a third message after the schedule CTA. Test the order in Telegram — schedule CTA should land between completion ack and main menu.

- [ ] **Step 3: Rewrite ai_chat.py fallback**

In `bot/handlers/ai_chat.py` replace the catch-all handler body. Currently it forwards to `_notify_managers` and persists `live_chat=True`. New behavior: respond with redirect text + WebApp button, drop the manager handoff. Still persist user message to conversations table for CRM context.

```python
from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo

from bot.config import config
from bot.texts import t
from bot.services.db_service import db


router = Router()


@router.message(F.text)
async def fallback_to_schedule(message: Message):
    user_id = message.from_user.id
    lead = await db.get_lead(user_id)
    lang = lead.get("preferred_lang", config.DEFAULT_LANG) if lead else config.DEFAULT_LANG

    # Persist for CRM context (no manager forward)
    await db.save_message(user_id, "user", message.text, source="bot_text")

    schedule_label = "Выбрать время" if lang == "ru" else "Вақтни танлаш"
    await message.answer(
        t("partner_handoff_received", lang),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(
                text=schedule_label,
                web_app=WebAppInfo(url=f"{config.TWA_URL}?tab=schedule&lang={lang}"),
            )
        ]]),
    )
```

(Preserve any imports / route ordering that's required by `bot/main.py` — this router must remain registered LAST per CLAUDE.md.)

- [ ] **Step 4: Syntax check**

```bash
python3 -m py_compile \
    bot/keyboards/main_menu.py \
    bot/handlers/questionnaire.py \
    bot/handlers/ai_chat.py
```

- [ ] **Step 5: Commit**

```bash
git add bot/keyboards/main_menu.py bot/handlers/questionnaire.py bot/handlers/ai_chat.py
git commit -m "feat(bot): rewire all CTAs to schedule tab — main menu, questionnaire complete, ai_chat fallback"
```

---

## Task 11: CRM dashboard — surface bookings + intake

**Files:**
- Modify: `crm/index.html`

- [ ] **Step 1: Extend leads SELECT**

Find the Supabase fetch call that loads leads (search for `.from('leads').select(`). Add `booking_status, next_session_at, website, social_handle` to the field list. Per CLAUDE.md note, include every field used in UI logic in the SELECT.

```js
const { data: leads } = await supabase
    .from('leads')
    .select('telegram_id, first_name, last_name, username, phone, lead_score, source, business_type, budget_range, service_interest, current_marketing, business_name, website, social_handle, booking_status, next_session_at, questionnaire_completed, created_at, last_activity_at')
    .order('created_at', { ascending: false });
```

- [ ] **Step 2: Add booking-status badge to lead card**

Find the lead-card render function. Add a badge near lead name:

```js
function bookingBadge(lead) {
    if (lead.booking_status === 'scheduled') {
        const when = lead.next_session_at
            ? new Date(lead.next_session_at).toLocaleString('ru-RU', { dateStyle: 'short', timeStyle: 'short' })
            : '';
        return `<span class="badge badge--scheduled" title="${when}">📅 ${when}</span>`;
    }
    if (lead.booking_status === 'cancelled') {
        return `<span class="badge badge--cancelled">отменено</span>`;
    }
    return '';
}
```

Insert `${bookingBadge(lead)}` next to the lead name in the card template.

- [ ] **Step 3: Add "Scheduled this week" filter**

Find the existing filter chips block. Add:

```js
const filterChips = [
    // ... existing chips ...
    { id: 'this_week', label: '📅 Сессии на неделе', test: lead => {
        if (lead.booking_status !== 'scheduled' || !lead.next_session_at) return false;
        const when = new Date(lead.next_session_at);
        const now = new Date();
        const weekFromNow = new Date(now.getTime() + 7 * 24 * 60 * 60 * 1000);
        return when >= now && when <= weekFromNow;
    }},
];
```

- [ ] **Step 4: Add Sessions tab**

Add a new top-level tab "Sessions" that queries the `bookings` table and shows upcoming + past sessions in two groups:

```js
async function loadSessions() {
    const nowIso = new Date().toISOString();
    const { data } = await supabase
        .from('bookings')
        .select('id, telegram_id, scheduled_at, ends_at, status, attendee_name, attendee_email')
        .order('scheduled_at', { ascending: true });
    if (!data) return;
    const upcoming = data.filter(b => b.status === 'scheduled' && b.scheduled_at >= nowIso);
    const past = data.filter(b => b.scheduled_at < nowIso);
    renderSessions(upcoming, past);
}

function renderSessions(upcoming, past) {
    const container = document.querySelector('#sessions-content');
    container.innerHTML = '';
    container.appendChild(renderSessionGroup('Предстоящие', upcoming));
    container.appendChild(renderSessionGroup('Прошедшие', past));
}

function renderSessionGroup(title, list) {
    const wrap = document.createElement('div');
    wrap.innerHTML = `<h3>${title} (${list.length})</h3>`;
    if (!list.length) {
        wrap.innerHTML += '<p class="muted">Нет записей.</p>';
        return wrap;
    }
    list.forEach(b => {
        const when = new Date(b.scheduled_at).toLocaleString('ru-RU');
        const row = document.createElement('div');
        row.className = 'session-row';
        row.innerHTML = `
            <div class="session-when">${when}</div>
            <div class="session-name">${b.attendee_name || '—'}</div>
            <div class="session-status">${b.status}</div>
            <a href="#lead-${b.telegram_id}">→ лид</a>
        `;
        wrap.appendChild(row);
    });
    return wrap;
}
```

Add tab switcher entry + `<div id="sessions-content"></div>` in the markup.

- [ ] **Step 5: Show intake fields in lead detail**

In the lead detail view, surface `business_name`, `website`, `social_handle`:

```js
function renderLeadDetail(lead) {
    return `
        <!-- ... existing fields ... -->
        <div class="lead-row"><span class="lead-label">Бизнес</span> ${lead.business_name || '—'}</div>
        <div class="lead-row"><span class="lead-label">Сайт</span> ${lead.website ? `<a href="${lead.website}" target="_blank" rel="noreferrer">${lead.website}</a>` : '—'}</div>
        <div class="lead-row"><span class="lead-label">Соцсети</span> ${lead.social_handle || '—'}</div>
    `;
}
```

- [ ] **Step 6: Deploy CRM**

```bash
cd crm && npx vercel --prod --yes
```

Open the CRM in browser, log in as admin, verify: lead cards show booking badge for scheduled leads, "Сессии на неделе" filter works, Sessions tab lists upcoming/past, lead detail shows website/social fields.

- [ ] **Step 7: Commit**

```bash
git add crm/index.html
git commit -m "feat(crm): surface bookings (badge, week filter, sessions tab) + intake fields (website, social)"
```

---

## Final Steps

- [ ] **End-to-end smoke test**

1. Open the bot fresh (`/start`) → questionnaire opens TWA → fill 5 audit Q's including business name + skip web/social → share phone
2. Confirm: completion ack lands in Telegram, "Выбрать время" inline button appears as separate message
3. Tap "Выбрать время" → TWA opens directly to schedule tab → Cal.com calendar renders inline
4. Pick a slot → submit booking
5. Within ~5s: Telegram message "✓ Сессия назначена на ..." arrives in bot chat
6. Admin chats receive "📅 Новая запись ..." notification
7. Supabase: `bookings` row exists with correct telegram_id, scheduled_at, status='scheduled'
8. Supabase: `leads.booking_status = 'scheduled'`, `leads.next_session_at` populated
9. CRM dashboard: lead card shows booking badge, Sessions tab shows the booking
10. Cancel the booking via Cal.com email → confirm cancellation Telegram messages arrive + Supabase row updates to `cancelled`

- [ ] **Final code review**

Run `superpowers:requesting-code-review` (or use the code-reviewer agent if working in subagent-driven mode) on the entire branch diff before merging.

- [ ] **Finish branch**

Use `superpowers:finishing-a-development-branch`. After all tests + smoke pass, the recommended flow is **Option 2: Push and create a Pull Request** so the changes are reviewable end-to-end before merging into main (this is a substantial multi-surface change). Railway redeploys bot from main; Vercel redeploys TWA + CRM from main.

---

## Rollout Order Recap

The tasks are written in dependency order — execute strictly top-to-bottom. The DB migration (Task 1) MUST be applied before any code referencing the new columns ships. The webhook function (Task 2) MUST be live before Cal.com's webhook is saved with that URL.
