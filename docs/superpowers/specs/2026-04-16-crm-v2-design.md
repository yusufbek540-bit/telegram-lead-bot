# CRM v2 Design Spec
Date: 2026-04-16
Project: MQSD Telegram Lead Bot + CRM

---

## Context

Live system for MQSD marketing agency (Tashkent, Uzbekistan). Two deployed components:
- **Bot** — aiogram 3.x polling, Python, Supabase backend
- **CRM** — React single-file app on Vercel at `https://crm-mqsd.vercel.app`

This spec covers extending both with productivity, AI, and analytics features across 7 phases.

---

## Decisions from Clarifying Questions

| Question | Answer |
|---|---|
| Team size | 3–5 members |
| Monthly lead volume | <100 |
| OpenAI budget | <$10/month → AI jobs every 8h, active leads only (last 24h) |
| External integrations | None — Supabase + Telegram only |
| Currency | UZS + USD |
| Alert recipients | Assigned member first, fall back to all ADMIN_IDS |
| CRM auth | Telegram WebApp `initData` — zero login friction |
| Rejection reasons | Editable by admins in Settings page |

---

## Architecture Principles

1. **No rebuilds** — extend existing bot and CRM files, don't replace them.
2. **Idempotent migrations** — every SQL file uses `IF NOT EXISTS`. Safe to re-run.
3. **Singleton reuse** — all jobs use `db` from `db_service.py` and `ai_service` singleton. Never instantiate new clients per job.
4. **Scheduler safety** — every job wrapped in try/except. Failures log ERROR and continue; never crash the scheduler.
5. **Config-driven** — all thresholds, intervals, and timezone in `bot/config.py`.
6. **Router order preserved** — new bot handlers registered before `ai_chat` router.
7. **Source never overwritten** — `leads.source` only set on first visit or real deep link.
8. **All Supabase selects explicit** — every field used in CRM UI must be in `.select()`.
9. **Admin text Russian, user text UZ+RU** via `t()` helper.

---

## CRM Authentication (Telegram WebApp initData)

The CRM opens exclusively via the `/crm` bot command using `WebAppInfo`. Telegram injects `window.Telegram.WebApp.initDataUnsafe.user` automatically.

**Flow:**
1. CRM loads → reads `initDataUnsafe.user.id`
2. Queries `team_members` table for matching `telegram_id`
3. Also accepts if `telegram_id` is in hardcoded `ADMIN_IDS` list in CRM config
4. If neither → show "Access denied" screen with instructions to contact admin
5. No password screen, no token storage — re-verified on every load

**Security note:** `initDataUnsafe` is not cryptographically verified client-side (that requires a backend). For an internal admin tool opened only via Telegram WebApp, this is acceptable. The attack surface is limited to people who already have the bot open.

---

## Phase Order

| Phase | Name | New DB migrations? |
|---|---|---|
| 0 | Scheduler infrastructure | No |
| 1 | Team productivity | Yes — `002_phase1.sql` |
| 2 | Ask AI widget | No |
| 3 | Revenue & conversion | Yes — `003_phase3.sql` |
| 4 | Automation | Yes — `004_phase4.sql` |
| 5 | Analytics & reporting | Yes — `005_phase5.sql` |
| 6 | Advanced | Yes — `006_phase6.sql` |

---

## Phase 0 — Scheduler Infrastructure

**Goal:** Extend the existing `scheduler_service.py` with timezone config, configurable intervals, a heartbeat job, and a `/jobs` debug command.

`APScheduler 3.10.4` already installed. `AsyncIOScheduler` already in `scheduler_service.py`. `create_scheduler()` already called from `main.py`.

**Changes:**

### `bot/config.py`
Add:
```python
SCHEDULER_TIMEZONE: str = "Asia/Tashkent"
JOB_INTERVALS: dict = {
    "followup_check_hours": 1,
    "stale_detection_hour": 9,       # daily at 9 AM Tashkent
    "ai_batch_hours": 8,             # sentiment + tagging
    "proposal_expiry_hours": 6,
    "campaign_dispatch_minutes": 5,
    "heartbeat_minutes": 30,
}
```

### `bot/services/scheduler_service.py`
- Pass `timezone=config.SCHEDULER_TIMEZONE` to `AsyncIOScheduler()`
- Use `config.JOB_INTERVALS` for existing `run_followups` interval
- Add heartbeat job: logs `"scheduler heartbeat"` every 30 min
- All jobs wrapped in try/except with structured logging

### `bot/handlers/admin.py`
Add `/jobs` command (admin-only):
```
/jobs output example:
🕐 Scheduled Jobs:
• run_followups — next run in 45m 12s
• heartbeat — next run in 8m 03s
```

**Verification:** Restart bot → `/jobs` shows heartbeat → wait 30 min → check logs for "scheduler heartbeat".

---

## Phase 1 — Core Team Productivity

### DB migration: `database/migrations/002_phase1.sql`

```sql
-- Response time tracking
ALTER TABLE leads ADD COLUMN IF NOT EXISTS first_contact_at TIMESTAMPTZ;
ALTER TABLE leads ADD COLUMN IF NOT EXISTS last_activity_at TIMESTAMPTZ;

-- Follow-up scheduling
ALTER TABLE leads ADD COLUMN IF NOT EXISTS next_followup_at TIMESTAMPTZ;
ALTER TABLE leads ADD COLUMN IF NOT EXISTS followup_note TEXT;

CREATE TABLE IF NOT EXISTS followup_reminders (
    id BIGSERIAL PRIMARY KEY,
    telegram_id BIGINT REFERENCES leads(telegram_id),
    scheduled_for TIMESTAMPTZ NOT NULL,
    note TEXT,
    completed BOOLEAN DEFAULT FALSE,
    created_by TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Assignment (column added early so Phase 1 notifications can use it;
-- full team_members table and routing logic come in Phase 4)
ALTER TABLE leads ADD COLUMN IF NOT EXISTS assigned_to TEXT;

-- Stale lead config (stored in leads, thresholds in config.py)
-- No new columns needed — uses last_activity_at + status
```

### Bot services

**`bot/services/response_tracker.py`**
- `record_first_contact(telegram_id)` — sets `first_contact_at` if NULL
- Called when admin changes lead status away from `"new"`

**`bot/services/followups.py`**
- Scheduled job every 1h (uses existing interval)
- Queries `followup_reminders` where `scheduled_for <= now` and `completed = false`
- Sends Telegram notification to assigned member (or all admins)
- Notification format: lead name, score, note, inline "Open in CRM" button (WebAppInfo)

**`bot/services/stale_detector.py`**
- Daily job at 9 AM Tashkent time
- Thresholds in `config.py`:
  ```python
  STALE_THRESHOLDS = {"new": 1, "contacted": 3, "qualified": 7, "proposal_sent": 5}  # days
  ```
- Flags stale leads by writing `stale_flagged` event to `events` table

### CRM changes

- **Today's Priorities widget** (top of dashboard, first thing visible):
  - 🔴 New leads with no team contact
  - 🟡 Overdue follow-up reminders
  - 🟢 Hot leads (score > 50) without phone
  - 🔵 Follow-ups scheduled for today
- **Lead card badges:** response time badge (green <15m, yellow 15–60m, red >60m) or "Waiting Xh Ym"
- **Follow-up UI:** date+time picker + note field on lead detail; overdue shown in red
- **Stale lead indicator:** red border on cards flagged as stale
- **Score breakdown:** hover/click score → modal showing point-by-point breakdown (mirrors `recalculate_score()` logic)

---

## Phase 2 — Ask AI Widget

No DB migrations needed. Uses existing `leads`, `conversations`, `events` tables.

### Bot side: `/ask` command

- Admin-only handler in `bot/handlers/admin.py`
- Usage: `/ask <natural language question>`
- Calls `ai_service` with a CRM system prompt + OpenAI function calling
- Available tools (implemented as `db` queries):
  - `query_leads(filters)` — filter by status, source, score, phone, date range
  - `query_conversations(telegram_id or name)` — fetch chat history for a lead
  - `get_analytics(metric, period)` — aggregate queries (count, avg score, conversion rate)
  - `find_lead_by_name(name)` — fuzzy name search
- Returns plain-language answer as bot message
- If answer is long → split into multiple messages

### CRM side: Chat panel widget

- Slide-out panel (right side of CRM, toggle button in header)
- Chat interface: message input + scrollable history (session only, not persisted)
- Calls OpenAI `gpt-4o-mini` directly from browser
- Same function-calling tools as bot side, implemented as Supabase JS queries
- OpenAI key stored in CRM `CONFIG` object (acceptable for internal admin-only tool)
- System prompt includes current date, agency name, summary of DB schema
- Example queries handled:
  - "Which leads from meta haven't been contacted?"
  - "What did Jasur say in his last conversation?"
  - "How many leads converted this month?"
  - "Who are my top 5 leads by score?"
  - "Show leads with no phone who have chatted more than 3 times"

### Cost estimate
~50 questions/month at <100 leads → ~$1–2/month additional.

---

## Phase 3 — Revenue & Conversion

### DB migration: `database/migrations/003_phase3.sql`

```sql
-- Deal value
ALTER TABLE leads ADD COLUMN IF NOT EXISTS estimated_value NUMERIC;
ALTER TABLE leads ADD COLUMN IF NOT EXISTS actual_value NUMERIC;
ALTER TABLE leads ADD COLUMN IF NOT EXISTS currency TEXT DEFAULT 'UZS';

-- Proposals
CREATE TABLE IF NOT EXISTS proposals (
    id BIGSERIAL PRIMARY KEY,
    telegram_id BIGINT REFERENCES leads(telegram_id),
    amount NUMERIC,
    currency TEXT DEFAULT 'UZS',
    services JSONB,
    sent_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ,
    status TEXT DEFAULT 'pending', -- pending/accepted/rejected/expired
    document_url TEXT,
    notes TEXT,
    created_by TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS proposals_lead_idx ON proposals(telegram_id, sent_at DESC);

-- Rejection reasons (editable)
CREATE TABLE IF NOT EXISTS rejection_reasons (
    id BIGSERIAL PRIMARY KEY,
    code TEXT UNIQUE NOT NULL,
    label_ru TEXT NOT NULL,
    label_uz TEXT NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
-- Pre-populate
INSERT INTO rejection_reasons (code, label_ru, label_uz) VALUES
  ('budget_too_low', 'Бюджет слишком мал', 'Byudjet kam'),
  ('wrong_service', 'Не та услуга', 'Xizmat mos emas'),
  ('no_response', 'Нет ответа', 'Javob yo''q'),
  ('chose_competitor', 'Выбрал конкурента', 'Raqobatchi tanladi'),
  ('not_a_fit', 'Не подходим', 'Mos emasmiz'),
  ('timing_not_right', 'Не время', 'Vaqti emas'),
  ('other', 'Другое', 'Boshqa')
ON CONFLICT (code) DO NOTHING;

ALTER TABLE leads ADD COLUMN IF NOT EXISTS rejection_reason TEXT;

-- Ad campaigns (ROI tracking)
CREATE TABLE IF NOT EXISTS ad_campaigns (
    id BIGSERIAL PRIMARY KEY,
    source_key TEXT UNIQUE NOT NULL,
    campaign_name TEXT,
    platform TEXT, -- meta/google/telegram_ads/organic
    spend_amount NUMERIC DEFAULT 0,
    currency TEXT DEFAULT 'UZS',
    start_date DATE,
    end_date DATE,
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

### Bot side
- Scheduled job (every 6h): auto-expire proposals where `expires_at < now` and status = `pending`
- Alert 3 days before expiry → notify assigned member or admins

### CRM changes
- **Deal value fields** on lead detail (UZS/USD toggle)
- **Pipeline view** shows total potential revenue per stage
- **"Create Proposal" button** when status = `"qualified"`
- **Proposal history** on lead detail
- **Rejection reason dropdown** (required when setting status to `"lost"`) — pulls from `rejection_reasons` table
- **Settings page:** manage rejection reasons (add/toggle active/rename)
- **Sources ROI page:** table — campaign | spend | leads | CPL | phone rate | converted | revenue | ROI%
- **"Why we lose leads" chart** — bar chart of rejection reasons

---

## Phase 4 — Automation

### DB migration: `database/migrations/004_phase4.sql`

```sql
CREATE TABLE IF NOT EXISTS team_members (
    id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    telegram_id BIGINT UNIQUE,
    specialization JSONB DEFAULT '[]',
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS lead_tags (
    id BIGSERIAL PRIMARY KEY,
    telegram_id BIGINT REFERENCES leads(telegram_id),
    tag TEXT NOT NULL,
    confidence NUMERIC,
    source TEXT DEFAULT 'manual', -- manual/ai/behavior
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS lead_tags_lead_idx ON lead_tags(telegram_id);

-- assigned_to added in Phase 1 migration
ALTER TABLE leads ADD COLUMN IF NOT EXISTS sentiment TEXT; -- positive/neutral/negative
ALTER TABLE leads ADD COLUMN IF NOT EXISTS sentiment_updated_at TIMESTAMPTZ;
ALTER TABLE leads ADD COLUMN IF NOT EXISTS key_signals JSONB;
```

### Bot services

**`bot/services/routing.py`**
- Called on new lead creation in `handlers/start.py`
- Strategies: `round_robin` (default), `by_language`, `by_score`
- Notifies assigned member via Telegram

**`bot/services/tagger.py`**
- Behavioral tags: instant on button clicks (services → "interested_services", portfolio → "viewed_portfolio")
- AI tags: batch every 8h, last 24h active leads only → gpt-4o-mini → service interest + business type

**`bot/services/sentiment.py`**
- Batch every 8h, last 24h active leads only
- One API call per lead analyzes last 10 messages
- Detects buying signals, objections, dissatisfaction

### CRM changes
- **Settings page:** manage team members and their specializations
- **Sentiment badge** 🟢🟡🔴 on lead cards
- **Tag chips** on lead cards, filterable in leads table
- **Alert:** "Negative sentiment detected" in Today's Priorities widget

---

## Phase 5 — Analytics & Reporting

### DB migration: `database/migrations/005_phase5.sql`

```sql
ALTER TABLE leads ADD COLUMN IF NOT EXISTS original_source TEXT;
ALTER TABLE leads ADD COLUMN IF NOT EXISTS touchpoints JSONB DEFAULT '[]';
```

### Bot side
- Modify `handlers/start.py`: set `original_source` on first visit only; append to `touchpoints` on every `/start` with a deep link

### CRM changes
- **Activity heatmap** — 3 separate heatmaps (first message, phone share, conversion) by hour × day of week
- **Team performance dashboard** — per-member: active leads, avg response time, closed this month, revenue, conversion rate
- **Attribution chain** on lead detail — journey timeline: "First via meta_bot → re-engaged via meta_fomo → converted"
- **Attribution toggle** on ROI dashboard: first-touch / last-touch / multi-touch

---

## Phase 6 — Advanced

### DB migration: `database/migrations/006_phase6.sql`

```sql
CREATE TABLE IF NOT EXISTS campaigns (
    id BIGSERIAL PRIMARY KEY,
    name TEXT,
    message_template_uz TEXT,
    message_template_ru TEXT,
    target_filters JSONB,
    scheduled_for TIMESTAMPTZ,
    status TEXT DEFAULT 'draft', -- draft/scheduled/sent
    sent_count INT DEFAULT 0,
    created_by TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS campaign_deliveries (
    id BIGSERIAL PRIMARY KEY,
    campaign_id BIGINT REFERENCES campaigns(id),
    telegram_id BIGINT,
    sent_at TIMESTAMPTZ,
    delivered BOOLEAN,
    failed_reason TEXT
);

ALTER TABLE leads ADD COLUMN IF NOT EXISTS duplicate_of BIGINT REFERENCES leads(telegram_id);
CREATE INDEX IF NOT EXISTS leads_phone_idx ON leads(phone);
```

### Bot services
**`bot/services/broadcaster.py`**
- Rate-limited: 25 msg/sec max (`asyncio.sleep(0.04)` between sends)
- Catches `TelegramForbiddenError` (blocked) → marks delivery failed
- Catches 429 → sleeps `retry_after` seconds
- Scheduled job: when `scheduled_for <= now` and status = `scheduled` → dispatch

### CRM changes
- **Campaign builder:** filter recipients, UZ+RU message templates, schedule picker, preview count before sending
- **Delivery dashboard:** sent / failed / replied / converted
- **Duplicate detection:** flagged on phone share → Duplicates section in dashboard with merge UI

---

## File Checklist (all phases)

```
database/migrations/
  002_phase1.sql
  003_phase3.sql
  004_phase4.sql
  005_phase5.sql
  006_phase6.sql

bot/config.py                        (updated: timezone, intervals, thresholds)
bot/services/scheduler_service.py    (updated: timezone, heartbeat, interval from config)
bot/handlers/admin.py                (updated: /jobs, /ask commands)
bot/services/response_tracker.py     (new)
bot/services/followups.py            (new — replaces inline logic in scheduler_service)
bot/services/stale_detector.py       (new)
bot/services/routing.py              (new)
bot/services/tagger.py               (new)
bot/services/sentiment.py            (new)
bot/services/broadcaster.py          (new)

crm/index.html                       (updated: all CRM phases)
CLAUDE.md                            (updated after each phase)
```

---

## Non-Goals

- No mobile app
- No Google Sheets / HubSpot integration
- No multi-language CRM UI (Russian only)
- No RLS on Supabase (team is small, anon key access is acceptable)
- No backend API server — CRM stays static, queries Supabase directly
