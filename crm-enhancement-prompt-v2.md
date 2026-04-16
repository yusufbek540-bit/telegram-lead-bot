# CRM Enhancement Implementation Prompt (v2 — adjusted to current state)

## Project State (as of now)

I have a LIVE Telegram lead capture system for MQSD, a marketing & AI agency in Tashkent, Uzbekistan. Everything below is already deployed and running — do NOT rebuild it.

### Deployed Components

- **Bot** — Python + aiogram 3.x, polling mode, running on my server
- **TWA** — single `index.html` on Vercel at `https://twa-jet.vercel.app`
  - Separate git repo inside `twa/` → `github.com/yusufbek540-bit/telegram-lead-twa`
  - Deploy: `cd twa && npx vercel --prod --yes`
- **CRM Dashboard** — React app on Vercel at `https://crm-mqsd.vercel.app`
  - Opens via `/crm` bot command (admin only) with `WebAppInfo`
  - Deploy: `cd crm && npx vercel --prod --yes`

### Tech Stack (actual, not theoretical)

- **Bot framework:** aiogram 3.x (Python)
- **AI:** OpenAI `AsyncOpenAI` with `gpt-4o-mini` (NOT Claude — this is important)
- **Database:** Supabase (anon key, no RLS yet)
- **Hosting:** Bot on server, TWA + CRM on Vercel (separate projects)
- **Language:** Bilingual Uzbek Latin (`uz`) + Russian (`ru`)

### Project Structure

```
bot/
  main.py              # router registration in strict order
  config.py            # Config singleton from env vars
  texts.py             # TEXTS dict + t() helper
  keyboards/main_menu.py
  services/
    db_service.py      # sync Supabase wrapped in async, singleton `db`
    ai_service.py      # AsyncOpenAI, accepts user_info string
  prompts/system_prompt.txt  # placeholders: {agency_name}, {lang}, {user_info}
  handlers/
    start.py
    admin.py           # /leads, /lead, /stats, /export, /crm
    contact.py
    twa.py
    menu.py
    ai_chat.py         # MUST be registered LAST
twa/
  index.html           # Vercel-deployed, own git repo
crm/                   # React app, deployed to Vercel separately
database/
  schema.sql
```

### Existing Database Tables

- **`leads`** — `telegram_id, first_name, last_name, username, phone, email, language_code, preferred_lang, source, status, lead_score, created_at, updated_at`
- **`conversations`** — `telegram_id, role, message, created_at` (all history permanent, `/reset` removed)
- **`events`** — `telegram_id, event_type, event_data JSONB, created_at`

### Environment Variables

`BOT_TOKEN`, `OPENAI_API_KEY`, `SUPABASE_URL`, `SUPABASE_KEY`, `TWA_URL`, `ADMIN_IDS`, `AGENCY_NAME`

---

## Critical Patterns (MUST respect when adding features)

1. **Router order in `main.py`** — start → admin → contact → twa → menu → ai_chat. Never register `ai_chat` before any other; it catches all `F.text`.

2. **`safe_edit()` in menu.py** — all inline button callbacks use it. Wraps `edit_text` and silently swallows `TelegramBadRequest` "message not modified". Keeps the chat to a single updating message. Use for any new menu-style feature.

3. **ReplyKeyboard dismissal** — sending a message with `InlineKeyboardMarkup` does NOT dismiss an active `ReplyKeyboard`. Pattern: send message with `ReplyKeyboardRemove()` first, then send the inline keyboard as a second message.

4. **AI user_info injection** — `ai_chat.py` builds a `user_info` string from the lead's DB record and passes it to `ai_service.get_response()`. The AI system prompt has a `{user_info}` placeholder. Any new AI-powered feature should follow this pattern — pass context via system prompt, not user messages.

5. **Deep link source tracking** — `leads.source` is only written on first /start OR when a real deep link is present. NEVER overwrite an existing source with `"organic"` on re-start. Critical for attribution.

6. **Admin text is always Russian** — all admin-facing commands, notifications, and CRM UI use Russian only. User-facing is bilingual UZ/RU.

7. **CRM Supabase selects** — always include every field used in UI logic in `.select()`. Missing fields cause silent fallback to defaults (common bug we've already hit).

8. **Single-instance polling** — only one `bot.main` process at a time. Double messages = duplicate instances. Always restart with `pkill -f "bot.main"; python3 -m bot.main`.

9. **Config-driven thresholds** — all timing values (stale lead days, response alerts, score rules) must go in `bot/config.py`, not hardcoded.

10. **Customization placeholders** — `[PRICE]`, `[X]`, `[...]` are real placeholders in `texts.py`, `system_prompt.txt`, `twa/index.html`. Don't overwrite them unless asked.

11. **Scheduled jobs use shared singletons** — any job in `bot/scheduler.py` that needs the database must use the singleton `db` from `services/db_service.py`. Never instantiate a new Supabase client per job. Same rule for `ai_service` — reuse the singleton.

12. **Scheduler must not crash the bot** — every job is wrapped in try/except. A failing job logs ERROR and continues. The scheduler never propagates exceptions to the main event loop.

---

## Goal

Extend the EXISTING CRM (deployed at `crm-mqsd.vercel.app`) with productivity, analytics, and automation features. Add bot-side services and scheduled jobs as needed. Do NOT rebuild the CRM from scratch.

---

## Features to Implement

### Phase 0 — Scheduler Infrastructure (MUST BE BUILT FIRST)

**Why this exists:** The bot currently only reacts to user input. Every scheduled feature in Phases 1-5 (follow-up reminders, stale detection, sentiment analysis, proposal expiry alerts, broadcast campaigns) needs a background process running jobs on a timer. Without this, those features cannot work — they would save data but never trigger any action.

**What to build:**

1. **Add APScheduler dependency**
   - Add `APScheduler>=3.10` to `requirements.txt`
   - Run `pip3 install -r requirements.txt`

2. **Create `bot/scheduler.py`** — centralized scheduler module
   - Use `AsyncIOScheduler` (not BackgroundScheduler — must share the bot's event loop)
   - Export a singleton `scheduler` instance
   - Export a `register_jobs(bot)` function where all future jobs are registered
   - Initially empty (no jobs yet — they're added as Phases 1-5 are built)
   - Include graceful shutdown handling

3. **Wire scheduler into `bot/main.py`**
   - Start scheduler BEFORE `dp.start_polling()`
   - Pass `bot` instance to jobs that need to send messages
   - Stop scheduler on shutdown (before closing bot session)
   - Proper order: register routers → register scheduled jobs → start scheduler → start polling

4. **Create `bot/handlers/admin.py` command `/jobs`**
   - Admin-only
   - Shows list of registered jobs with their next run time
   - Format: "`check_followups` — next run in 12m 34s"
   - Useful for debugging and confirming the scheduler is alive

5. **Add scheduler config to `bot/config.py`**
   - `SCHEDULER_TIMEZONE = "Asia/Tashkent"` (so daily jobs run at local time, not UTC)
   - All job intervals go here, not hardcoded in scheduler.py:
     ```python
     JOB_INTERVALS = {
         "followup_check_minutes": 15,
         "stale_detection_hour": 9,        # daily at 9 AM Tashkent time
         "sentiment_batch_hours": 2,
         "proposal_expiry_hours": 6,
         "campaign_dispatch_minutes": 5,
     }
     ```

6. **Logging**
   - Every scheduled job logs on start and end with execution time
   - Use the same logger as `main.py` for consistency
   - Log levels: INFO for normal runs, WARNING for empty runs (no leads matched), ERROR for exceptions
   - Catch exceptions in every job — a single failure must not crash the scheduler

7. **Test job (verification)**
   - Add one harmless test job: logs "scheduler heartbeat" every 30 minutes
   - Confirms scheduler is actually running in production
   - Can be removed once Phase 1 jobs are in place

**Deliverables for Phase 0:**
- `requirements.txt` updated
- `bot/scheduler.py` (new file)
- `bot/main.py` updated (scheduler wired in)
- `bot/handlers/admin.py` updated (add `/jobs` command)
- `bot/config.py` updated (timezone + intervals)
- `CLAUDE.md` updated with scheduler section:
  - Where it lives
  - How to add new jobs
  - How to debug with `/jobs` command
  - Warning: jobs that touch the database must use the singleton `db` from `services/db_service.py` — do NOT create a new Supabase client per job

**Verification before moving to Phase 1:**
- Restart bot, run `/jobs` as admin
- See "heartbeat" job listed with next run time
- Wait 30 min, check logs for "scheduler heartbeat" entry
- Only then begin Phase 1

---

### Phase 1 — Core Team Productivity

#### 1.1 Response Time Tracking

**DB migration:**
- Add `first_contact_at TIMESTAMPTZ` to `leads`
- Populate on first status change away from `"new"`
- Add view `response_times`: telegram_id, created_at, first_contact_at, minutes_to_contact

**Bot side:**
- `services/response_tracker.py` — updates `first_contact_at` when status transitions out of `new`
- Hook into admin status change command

**CRM side:**
- Lead card shows badge: "Contacted in 12 min" (green <15m, yellow 15-60m, red >60m) or "Waiting 2h 45m" for new leads
- Dashboard widget: avg response time this week vs last week (sparkline)
- Alert section: leads waiting > N minutes (config: `RESPONSE_ALERT_MINUTES`)

#### 1.2 Follow-up System

**DB migration:**
- Add `next_followup_at TIMESTAMPTZ`, `followup_note TEXT` to `leads`
- New table `followup_reminders`: id, telegram_id, scheduled_for, note, completed BOOLEAN, created_by, created_at

**Bot side:**
- `services/followups.py` with scheduled job running every 15 min
- When `scheduled_for <= now` and `completed = false` → send Telegram notification to assigned admin (or all admins if unassigned)
- Notification includes: lead name, score, original note, "Open in CRM" button

**CRM side:**
- "Schedule follow-up" button on each lead (date+time picker + note)
- Dashboard widget "Сегодня напомнить (N)" — today's follow-ups list at top
- Overdue follow-ups in red
- Quick actions: mark complete, reschedule +1 day, reschedule +3 days

#### 1.3 "Today's Priorities" Dashboard Widget (first thing visible on CRM open)

**CRM side only:**
Single widget at top of dashboard showing in priority order:
- 🔴 Новые без контакта (new leads with no team action)
- 🟡 Просроченные напоминания (overdue follow-ups)
- 🟢 Горячие без телефона (score > 50, no phone)
- 🔵 Напоминания на сегодня (scheduled for today)

Each item clickable → opens lead detail. Badge counts visible.

#### 1.4 Stale Lead Detection

**DB migration:**
- Add `last_activity_at TIMESTAMPTZ` to `leads` (triggered on any new message/event)
- Add trigger or application-level update
- Config in `bot/config.py`:
  ```python
  STALE_THRESHOLDS = {"new": 1, "contacted": 3, "qualified": 7, "proposal_sent": 5}  # days
  ```

**Bot side:**
- `services/stale_detector.py` — scheduled job runs daily
- Flags leads via event: `stale_flagged`

**CRM side:**
- Red border on stale lead cards
- Dashboard section "Требуют внимания" sorted by most stale first
- Dismiss/snooze button (N days)

#### 1.5 Lead Score Breakdown (Explainability)

**No DB change** — calculate on-the-fly from existing events + lead data.

**CRM side:**
- Hover/click on score number shows breakdown modal:
  - "Телефон поделён: +30"
  - "8 сообщений в чате: +15"
  - "Открыл TWA: +10"
  - "Заказал звонок: +25"
  - "Итого: 80"
- Breakdown logic lives in `crm/src/utils/scoreBreakdown.js` mirroring `db.recalculate_score()`

---

### Phase 2 — Revenue & Conversion

#### 2.1 Deal Value Tracking

**DB migration:**
- Add to `leads`: `estimated_value NUMERIC`, `actual_value NUMERIC`, `currency TEXT DEFAULT 'UZS'`

**CRM side:**
- "Оценка сделки" input field in lead detail (shows during qualification)
- Pipeline view: total potential revenue per stage (not just count)
- Dashboard widget: forecasted revenue this month

#### 2.2 Proposal Tracker

**DB migration:**
- New table `proposals`: id, telegram_id, amount, currency, services JSONB, sent_at, expires_at, status (pending/accepted/rejected/expired), document_url, notes, created_by
- Index on `(telegram_id, sent_at DESC)`

**Bot side:**
- Scheduled job: 3 days before expiry → notify admin
- Auto-mark expired when date passed

**CRM side:**
- "Создать КП" button appears when status = "qualified"
- Proposal history list on lead detail
- Dashboard widget: "КП в этом месяце: 12 отправлено, 4 приняты (33%)"

#### 2.3 Rejection Reason Analytics

**DB migration:**
- Add `rejection_reason TEXT` to `leads`
- New lookup table `rejection_reasons`: code, label_ru, label_uz, is_active
- Pre-populate: `budget_too_low`, `wrong_service`, `no_response`, `chose_competitor`, `not_a_fit`, `timing_not_right`, `other`

**CRM side:**
- When setting status to `"lost"` — REQUIRED dropdown of rejection reasons
- Optional free-text detail field
- Dashboard chart: "Почему теряем лидов" (bar chart of reasons)
- Trends: show if any reason is increasing month-over-month

#### 2.4 Source ROI Dashboard

**DB migration:**
- New table `ad_campaigns`: id, source_key (matches `?start=` param), campaign_name, platform (meta/google/telegram_ads/organic), spend_amount NUMERIC, start_date, end_date, notes
- Manually populated by admin

**CRM side:**
- New page "Источники" with table: campaign | spend | leads | CPL | phone shared | converted | revenue | ROI %
- Sortable columns, CSV export
- Trend chart: ROI per campaign over time
- Highlight profitable vs losing campaigns (green/red)

---

### Phase 3 — Automation

#### 3.1 Smart Lead Routing

**DB migration:**
- New table `team_members`: id, name, telegram_id, specialization JSONB (e.g., ["smm", "bot", "ai"]), is_active, created_at
- New table `routing_rules`: id, name, conditions JSONB, assignee_strategy TEXT, priority, is_active
- Add `assigned_to TEXT` to `leads`

**Bot side:**
- `services/routing.py` — called on new lead creation in `handlers/start.py`
- Strategies: `round_robin`, `specialist` (by detected tags), `by_language`, `by_score`, `manual`

**CRM side:**
- Settings page to manage team members and their specializations
- Rule builder UI: conditions → strategy mapping
- Manual reassignment on lead detail always available

#### 3.2 Auto-Tagging

**DB migration:**
- New table `lead_tags`: id, telegram_id, tag, confidence NUMERIC, source (manual/ai/behavior), created_at
- Multiple tags per lead

**Bot side:**
- `services/tagger.py`
  - Behavioral tagging: instant (button clicks map to tags)
  - AI tagging: scheduled batch every hour — sends lead conversations to OpenAI, gets back service interest + business type tags
  - Use `gpt-4o-mini` (already in use) to keep costs low

**CRM side:**
- Tag chips visible on lead cards
- Filter by tag in leads table
- Tag analytics: "Top запрашиваемые услуги в этом месяце"

#### 3.3 Conversation Sentiment Analysis

**DB migration:**
- Add to `leads`: `sentiment TEXT` (positive/neutral/negative), `sentiment_updated_at TIMESTAMPTZ`, `key_signals JSONB`

**Bot side:**
- `services/sentiment.py` — scheduled batch every 2 hours
- Uses `gpt-4o-mini` — one API call analyzes last 10 messages per lead
- Detects: buying signals (mentions budget/timeline/urgency), objections (comparing competitors), dissatisfaction
- Only run on leads that had activity in last 24h (cost control)

**CRM side:**
- Sentiment badge on lead cards: 🟢🟡🔴
- Key signals visible in lead detail
- Alert: "Negative sentiment detected on lead X"

---

### Phase 4 — Analytics & Reporting

#### 4.1 Activity Heatmap

**CRM side only** — query `conversations` + `events` grouped by hour × day of week.

Three separate heatmaps:
- When leads START chatting (new leads first message)
- When leads SHARE PHONE (conversion moment)
- When CONVERSIONS happen (status change to "converted")

Useful for scheduling team shifts.

#### 4.2 Team Performance Dashboard

**Requires:** team members table from Phase 3.1

**CRM side:**
- Per-team-member panel: active leads, response time avg, closed this month, revenue generated, conversion rate
- Leaderboard (toggleable)
- Monthly performance export

#### 4.3 Lead Source Attribution Chain

**DB migration:**
- Add `original_source TEXT` to `leads` (set once on first /start, never overwritten)
- Add `touchpoints JSONB` (array of `{source, timestamp}` entries — append each time user re-starts with a deep link)

**Bot side:**
- Modify `handlers/start.py` to:
  - Set `original_source` on first visit only
  - Append to `touchpoints` array on every /start with a deep link

**CRM side:**
- Lead detail shows journey timeline: "First seen via meta_bot_demo → re-engaged via meta_ai_fomo → converted"
- Attribution toggle: first-touch / last-touch / multi-touch (affects ROI dashboard numbers)

---

### Phase 5 — Advanced (only after Phases 1-4 are stable)

#### 5.1 Re-engagement Campaigns (Broadcast)

**DB migration:**
- New table `campaigns`: id, name, message_template_uz TEXT, message_template_ru TEXT, target_filters JSONB, scheduled_for, status (draft/scheduled/sent), sent_count, created_by, created_at
- New table `campaign_deliveries`: id, campaign_id, telegram_id, sent_at, delivered BOOLEAN, failed_reason

**Bot side:**
- `services/broadcaster.py`
- Rate-limited sending: 25 messages/sec max with `await asyncio.sleep(0.04)` between sends
- Catch `TelegramForbiddenError` (user blocked bot) → mark delivery failed, don't retry
- Catch 429 rate limit → sleep `retry_after` seconds
- Scheduled jobs: when `scheduled_for <= now` and status = scheduled → start broadcast

**CRM side:**
- Campaign builder UI:
  - Filter recipients: by status, tag, source, inactivity period, language
  - Message template editor (UZ + RU)
  - Schedule picker
  - Preview recipient count BEFORE sending
- Delivery dashboard: sent, failed, replied, converted

#### 5.2 Duplicate Lead Detection

**DB migration:**
- Add `duplicate_of BIGINT` to `leads` (self-reference)
- Index on `phone`

**Bot side:**
- On new lead creation OR phone share — check if phone already exists in another lead
- Flag both as potential duplicates

**CRM side:**
- Duplicates section in dashboard
- Merge UI: combines conversations + events + comments into primary lead, soft-deletes secondary

---

## Deliverables Expected

1. **`database/migrations/002_crm_phase1.sql`** (and subsequent 003, 004...) — each phase gets its own idempotent migration file
2. **Updated `bot/services/`** — new modules, one per feature
3. **Updated `bot/scheduler.py`** — centralized APScheduler for periodic jobs (follow-ups, stale detection, sentiment analysis, campaigns). If file doesn't exist, create it and wire into `main.py`.
4. **Updated `bot/handlers/admin.py`** — new commands where applicable
5. **Updated CRM** — React components added/modified in `crm/src/`
6. **Updated `bot/config.py`** — new configurable thresholds
7. **Updated `CLAUDE.md`** — document new patterns introduced

---

## Build Rules

- **Phase 0 first, always** — no scheduled feature works without the scheduler. Complete and verify Phase 0 before any other phase.
- **Idempotent migrations** — use `CREATE TABLE IF NOT EXISTS`, `ALTER TABLE ADD COLUMN IF NOT EXISTS`. Must be safe to re-run.
- **Don't break what works** — bot, TWA, existing CRM must keep running through the migration.
- **One phase at a time** — finish Phase 1 completely before starting Phase 2. Test in production before moving on.
- **Use `gpt-4o-mini`** for any AI features (matches current stack, cheap).
- **All new admin UI text in Russian** only.
- **All new user-facing bot text in UZ + RU** via `t()` helper in `texts.py`.
- **Use existing `safe_edit()`** for any new inline button flows.
- **Respect source-tracking rule** — never overwrite `leads.source` with `"organic"` on re-start.
- **Add every new field to CRM `.select()`** calls that touch those tables.

---

## Clarifying Questions (answer before starting)

1. How many team members will use the CRM? (affects team_members seeding)
2. Expected monthly lead volume? (affects pagination, caching, scheduled job frequency)
3. What's your monthly OpenAI budget? (affects sentiment + tagging batch frequency)
4. Any external integration needed? (Google Sheets export, WhatsApp, HubSpot sync)
5. Multi-currency or UZS only?
6. Should stale/followup alerts be sent to assigned admin only, or all admins?
7. How do you want to authenticate the CRM beyond current setup? (keep as-is for now, or add per-user login?)
8. Should rejection reasons be editable by admins in Settings, or hardcoded?

---

## Start Command

**When ready, say: "Start Phase 0"** and I will build the scheduler infrastructure first:
- `requirements.txt` (add APScheduler)
- `bot/scheduler.py` (new — centralized job runner)
- `bot/main.py` updates (wire scheduler into lifecycle)
- `bot/config.py` updates (timezone + job intervals)
- `bot/handlers/admin.py` updates (add `/jobs` debug command)
- Test heartbeat job for verification
- Updated `CLAUDE.md`

After Phase 0 is verified working (heartbeat visible in `/jobs` output), say **"Start Phase 1"** and I will build:
- `database/migrations/002_crm_phase1.sql`
- `bot/services/response_tracker.py`
- `bot/services/followups.py`
- `bot/services/stale_detector.py`
- Register all Phase 1 jobs in `bot/scheduler.py`
- CRM dashboard updates (Today's Priorities, response time badges, follow-up UI, stale flagging, score breakdown)
- Updated `CLAUDE.md`
