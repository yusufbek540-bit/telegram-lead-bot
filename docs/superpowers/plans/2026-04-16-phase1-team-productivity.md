# Phase 1 — Team Productivity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add response time tracking, follow-up reminders, stale lead detection, and CRM productivity widgets so the team can prioritize leads and never miss a follow-up.

**Architecture:** DB migration adds new columns and the `followup_reminders` table. Three new bot services handle tracking and notifications. CRM gains a Today's Priorities widget on Dashboard, response time badges, improved follow-up UI, stale lead indicators, and a score breakdown modal — all computed from existing Supabase data. Scheduler wires two new jobs (reminders every 1h, stale detection daily at 09:00 Tashkent).

**Tech Stack:** Python 3.9, aiogram 3.x, APScheduler 3.10.4, Supabase (anon key, direct from browser), React (via CDN Babel), single-file CRM at `crm/index.html`

---

## File Map

| File | Change |
|---|---|
| `database/migrations/002_phase1.sql` | Create — new columns + `followup_reminders` table |
| `bot/services/db_service.py` | Modify — update `last_activity_at` on `save_message()` |
| `bot/services/response_tracker.py` | Create — `record_first_contact()` |
| `bot/services/followups.py` | Create — `check_followup_reminders()` scheduled job |
| `bot/services/stale_detector.py` | Create — `detect_stale_leads()` daily job |
| `bot/services/scheduler_service.py` | Modify — register two new jobs |
| `crm/index.html` | Modify — Today's Priorities, response time badge, follow-up UI, stale indicator, score breakdown |

---

### Task 1: DB Migration

**Files:**
- Create: `database/migrations/002_phase1.sql`

- [ ] **Step 1: Create the migration file**

Create `/Users/yusufbek/Desktop/telegram-lead-bot/database/migrations/002_phase1.sql` with this exact content:

```sql
-- ============================================================
-- Phase 1 — Team Productivity Migration
-- Safe to re-run (all statements are idempotent)
-- Run in Supabase SQL Editor: https://supabase.com/dashboard
-- ============================================================

-- Response time tracking
ALTER TABLE leads ADD COLUMN IF NOT EXISTS first_contact_at TIMESTAMPTZ;
ALTER TABLE leads ADD COLUMN IF NOT EXISTS last_activity_at TIMESTAMPTZ;

-- Follow-up scheduling (quick field on lead)
ALTER TABLE leads ADD COLUMN IF NOT EXISTS next_followup_at TIMESTAMPTZ;
ALTER TABLE leads ADD COLUMN IF NOT EXISTS followup_note TEXT;

-- Assignment (full routing in Phase 4; column added now so Phase 1 notifications work)
ALTER TABLE leads ADD COLUMN IF NOT EXISTS assigned_to TEXT;

-- Structured follow-up reminders table (set by CRM team members)
CREATE TABLE IF NOT EXISTS followup_reminders (
    id          BIGSERIAL PRIMARY KEY,
    telegram_id BIGINT REFERENCES leads(telegram_id) ON DELETE CASCADE,
    scheduled_for TIMESTAMPTZ NOT NULL,
    note        TEXT,
    completed   BOOLEAN DEFAULT FALSE,
    created_by  TEXT,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS followup_reminders_scheduled_idx
    ON followup_reminders(scheduled_for)
    WHERE completed = FALSE;
```

- [ ] **Step 2: Run in Supabase SQL Editor**

1. Open your Supabase project dashboard
2. Go to SQL Editor
3. Paste the content of `database/migrations/002_phase1.sql`
4. Click Run
5. Verify: no errors, all statements show "Success"

Confirm the new columns exist by running:
```sql
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name = 'leads'
  AND column_name IN ('first_contact_at', 'last_activity_at', 'next_followup_at', 'followup_note', 'assigned_to');
```
Expected: 5 rows returned.

Also confirm the table:
```sql
SELECT table_name FROM information_schema.tables WHERE table_name = 'followup_reminders';
```
Expected: 1 row returned.

---

### Task 2: Update `db_service.py` — track `last_activity_at`

**Files:**
- Modify: `bot/services/db_service.py`

`last_activity_at` must be updated every time a user sends a message. This powers both stale detection and the CRM's "Last Activity" display.

- [ ] **Step 1: Read the current `save_message` method**

Read `bot/services/db_service.py` lines 210–222 to confirm current content.

- [ ] **Step 2: Add `last_activity_at` update to `save_message`**

Find this exact block in `bot/services/db_service.py`:

```python
    async def save_message(self, telegram_id: int, role: str, message: str):
        """Save a conversation message."""
        self.client.table("conversations").insert(
            {
                "telegram_id": telegram_id,
                "role": role,
                "message": message,
            }
        ).execute()
```

Replace with:

```python
    async def save_message(self, telegram_id: int, role: str, message: str):
        """Save a conversation message and update lead's last_activity_at."""
        self.client.table("conversations").insert(
            {
                "telegram_id": telegram_id,
                "role": role,
                "message": message,
            }
        ).execute()
        # Update last_activity_at on every user message for stale detection
        if role == "user":
            self.client.table("leads").update(
                {"last_activity_at": datetime.now(timezone.utc).isoformat()}
            ).eq("telegram_id", telegram_id).execute()
```

- [ ] **Step 3: Confirm `datetime` and `timezone` are imported**

Check the top of `bot/services/db_service.py` for:
```python
from datetime import datetime, timezone
```
This import already exists (line 2). If it doesn't, add it.

- [ ] **Step 4: Verify bot starts cleanly**

```bash
cd /Users/yusufbek/Desktop/telegram-lead-bot
python3 -c "from bot.services.db_service import db; print('OK')"
```
Expected: `OK`

---

### Task 3: Create `bot/services/response_tracker.py`

**Files:**
- Create: `bot/services/response_tracker.py`

Records the first time a team member contacts a lead (changes status away from "new"). Called from both the CRM (via Supabase direct update + `first_contact_at`) and future bot commands.

- [ ] **Step 1: Create the file**

Create `/Users/yusufbek/Desktop/telegram-lead-bot/bot/services/response_tracker.py`:

```python
"""
Response tracker — records when a lead is first contacted by the team.

Call record_first_contact(telegram_id) whenever a lead's status changes
away from "new" for the first time (e.g., when team marks them "contacted").

This populates leads.first_contact_at, which powers the response time
badge in the CRM (green/yellow/red based on how fast the team responded).
"""

import logging
from datetime import datetime, timezone

from bot.services.db_service import db

logger = logging.getLogger(__name__)


async def record_first_contact(telegram_id: int) -> None:
    """Set first_contact_at on a lead if it hasn't been set yet.

    Safe to call multiple times — only writes on the first call.
    """
    lead = await db.get_lead(telegram_id)
    if not lead:
        logger.warning(f"record_first_contact: lead {telegram_id} not found")
        return
    if lead.get("first_contact_at"):
        return  # Already recorded
    await db.update_lead(
        telegram_id,
        first_contact_at=datetime.now(timezone.utc).isoformat(),
    )
    logger.info(f"record_first_contact: recorded for {telegram_id}")
```

- [ ] **Step 2: Verify import**

```bash
cd /Users/yusufbek/Desktop/telegram-lead-bot
python3 -c "from bot.services.response_tracker import record_first_contact; print('OK')"
```
Expected: `OK`

---

### Task 4: Create `bot/services/followups.py` + register job

**Files:**
- Create: `bot/services/followups.py`
- Modify: `bot/services/scheduler_service.py`

This job checks the `followup_reminders` table every hour and sends Telegram notifications to the assigned team member (or all admins if unassigned).

- [ ] **Step 1: Create `bot/services/followups.py`**

Create `/Users/yusufbek/Desktop/telegram-lead-bot/bot/services/followups.py`:

```python
"""
Follow-up reminders — notifies team members about scheduled lead follow-ups.

Runs every hour. Checks followup_reminders for entries where:
  - scheduled_for <= now
  - completed = False

Sends a Telegram message to the assigned team member, or all admins if
the lead is unassigned. Marks the reminder as completed after sending.

This is for TEAM reminders set manually in the CRM, not the automated
user-facing follow-up messages in scheduler_service.py.
"""

import logging
import time
from datetime import datetime, timezone

from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo

from bot.config import config
from bot.services.db_service import db

logger = logging.getLogger(__name__)

CRM_URL = "https://crm-mqsd.vercel.app"


async def _get_recipient_ids(lead: dict) -> list[int]:
    """Return Telegram IDs to notify: assigned member first, fall back to all admins."""
    if lead.get("assigned_to"):
        member = await db.get_team_member_by_name(lead["assigned_to"])
        if member and member.get("telegram_id"):
            return [int(member["telegram_id"])]
    return list(config.ADMIN_IDS)


async def check_followup_reminders(bot: Bot) -> None:
    """Hourly job: send notifications for due follow-up reminders."""
    start = time.monotonic()
    logger.info("check_followup_reminders: starting")
    try:
        now_iso = datetime.now(timezone.utc).isoformat()

        # Fetch overdue, incomplete reminders
        result = (
            db.client.table("followup_reminders")
            .select("id, telegram_id, note, scheduled_for")
            .lte("scheduled_for", now_iso)
            .eq("completed", False)
            .execute()
        )
        reminders = result.data or []

        if not reminders:
            logger.info("check_followup_reminders: no due reminders")
            return

        for reminder in reminders:
            tid = reminder["telegram_id"]
            lead = await db.get_lead(tid)
            if not lead:
                continue

            name = f"{lead.get('first_name') or ''} {lead.get('last_name') or ''}".strip() or "—"
            score = lead.get("lead_score", 0)
            note = reminder.get("note") or "—"

            text = (
                f"⏰ <b>Напоминание о лиде</b>\n\n"
                f"👤 {name}\n"
                f"⭐ Баллы: {score}\n"
                f"📝 Заметка: {note}"
            )
            keyboard = InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(
                    text="📊 Открыть CRM",
                    web_app=WebAppInfo(url=CRM_URL),
                )
            ]])

            recipient_ids = await _get_recipient_ids(lead)
            for admin_id in recipient_ids:
                try:
                    await bot.send_message(admin_id, text, parse_mode="HTML", reply_markup=keyboard)
                except Exception as e:
                    logger.warning(f"check_followup_reminders: failed to notify {admin_id} — {e}")

            # Mark reminder as completed
            db.client.table("followup_reminders").update(
                {"completed": True}
            ).eq("id", reminder["id"]).execute()

        elapsed = time.monotonic() - start
        logger.info(f"check_followup_reminders: processed {len(reminders)} reminders in {elapsed:.2f}s")

    except Exception as e:
        logger.error(f"check_followup_reminders: failed — {e}", exc_info=True)
```

- [ ] **Step 2: Register job in `bot/services/scheduler_service.py`**

Open `bot/services/scheduler_service.py`. Find the `create_scheduler` function. It currently has `run_followups` and `heartbeat` jobs.

Add the import at the top of the file (after the existing imports):

```python
from bot.services.followups import check_followup_reminders
```

Then inside `create_scheduler()`, before the `return scheduler` line, add:

```python
    scheduler.add_job(
        check_followup_reminders,
        trigger="interval",
        hours=config.JOB_INTERVALS["followup_check_hours"],
        args=[bot],
        id="check_followup_reminders",
        replace_existing=True,
    )
```

- [ ] **Step 3: Verify syntax**

```bash
cd /Users/yusufbek/Desktop/telegram-lead-bot
python3 -c "from bot.services.scheduler_service import create_scheduler; print('OK')"
```
Expected: `OK`

- [ ] **Step 4: Restart bot and confirm job appears**

```bash
pkill -f "bot.main"; sleep 1 && python3 -m bot.main > /tmp/bot_p1.log 2>&1 &
sleep 4 && cat /tmp/bot_p1.log
```

Expected log lines:
```
Added job "run_followups" to job store "default"
Added job "check_followup_reminders" to job store "default"
Added job "heartbeat" to job store "default"
```

Send `/jobs` as admin — confirm `check_followup_reminders` appears.

Kill the bot: `pkill -f "bot.main"`

---

### Task 5: Create `bot/services/stale_detector.py` + register daily job

**Files:**
- Create: `bot/services/stale_detector.py`
- Modify: `bot/services/scheduler_service.py`

Daily job at 09:00 Tashkent time. For each lead in an active status, checks if `last_activity_at` exceeds the threshold for that status. If stale and not yet flagged today, writes a `stale_flagged` event and notifies the assigned member/admins.

- [ ] **Step 1: Create `bot/services/stale_detector.py`**

Create `/Users/yusufbek/Desktop/telegram-lead-bot/bot/services/stale_detector.py`:

```python
"""
Stale lead detector — daily job at 09:00 Tashkent time.

A lead is stale when last_activity_at is older than the threshold
for its current status (from config.STALE_THRESHOLDS, in days).

For each newly-stale lead:
  1. Writes a 'stale_flagged' event to the events table
  2. Notifies the assigned team member (or all admins if unassigned)

Deduplication: skips leads that already have a 'stale_flagged' event
from the past 24 hours to avoid re-notifying on the same stale state.
"""

import logging
import time
from datetime import datetime, timedelta, timezone

from aiogram import Bot

from bot.config import config
from bot.services.db_service import db

logger = logging.getLogger(__name__)

# Statuses where staleness matters (terminal statuses excluded)
ACTIVE_STATUSES = {"new", "contacted", "qualified", "proposal_sent"}


async def _get_recipient_ids(lead: dict) -> list[int]:
    """Return Telegram IDs to notify: assigned member first, fall back to all admins."""
    if lead.get("assigned_to"):
        member = await db.get_team_member_by_name(lead["assigned_to"])
        if member and member.get("telegram_id"):
            return [int(member["telegram_id"])]
    return list(config.ADMIN_IDS)


async def _already_flagged_today(telegram_id: int) -> bool:
    """True if a stale_flagged event was written for this lead in the past 24h."""
    since = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    result = (
        db.client.table("events")
        .select("id")
        .eq("telegram_id", telegram_id)
        .eq("event_type", "stale_flagged")
        .gte("created_at", since)
        .limit(1)
        .execute()
    )
    return bool(result.data)


async def detect_stale_leads(bot: Bot) -> None:
    """Daily job: flag leads that haven't had activity within their status threshold."""
    start = time.monotonic()
    logger.info("detect_stale_leads: starting")
    try:
        now = datetime.now(timezone.utc)
        # Fetch all active leads that have a last_activity_at value
        result = (
            db.client.table("leads")
            .select("telegram_id, first_name, last_name, status, last_activity_at, lead_score, assigned_to")
            .in_("status", list(ACTIVE_STATUSES))
            .not_.is_("last_activity_at", "null")
            .execute()
        )
        leads = result.data or []
        flagged = 0

        for lead in leads:
            status = lead.get("status", "new")
            threshold_days = config.STALE_THRESHOLDS.get(status)
            if not threshold_days:
                continue

            last_activity = datetime.fromisoformat(lead["last_activity_at"].replace("Z", "+00:00"))
            days_since = (now - last_activity).total_seconds() / 86400

            if days_since <= threshold_days:
                continue  # Not stale yet

            tid = lead["telegram_id"]
            if await _already_flagged_today(tid):
                continue  # Already notified today

            # Flag it
            await db.track_event(tid, "stale_flagged", {
                "days_since_activity": round(days_since, 1),
                "status": status,
                "threshold_days": threshold_days,
            })
            flagged += 1

            name = f"{lead.get('first_name') or ''} {lead.get('last_name') or ''}".strip() or "—"
            score = lead.get("lead_score", 0)
            text = (
                f"⚠️ <b>Застывший лид</b>\n\n"
                f"👤 {name}\n"
                f"📊 Статус: {status}\n"
                f"⭐ Баллы: {score}\n"
                f"📅 Нет активности: {round(days_since, 1)} дн."
            )
            recipient_ids = await _get_recipient_ids(lead)
            for admin_id in recipient_ids:
                try:
                    await bot.send_message(admin_id, text, parse_mode="HTML")
                except Exception as e:
                    logger.warning(f"detect_stale_leads: failed to notify {admin_id} — {e}")

        elapsed = time.monotonic() - start
        logger.info(f"detect_stale_leads: flagged {flagged} leads in {elapsed:.2f}s")

    except Exception as e:
        logger.error(f"detect_stale_leads: failed — {e}", exc_info=True)
```

- [ ] **Step 2: Register daily job in `bot/services/scheduler_service.py`**

Add import at top of `scheduler_service.py` (after the `check_followup_reminders` import you added in Task 4):

```python
from bot.services.stale_detector import detect_stale_leads
```

Inside `create_scheduler()`, before `return scheduler`, add:

```python
    scheduler.add_job(
        detect_stale_leads,
        trigger="cron",
        hour=config.JOB_INTERVALS["stale_detection_hour"],
        minute=0,
        args=[bot],
        id="detect_stale_leads",
        replace_existing=True,
    )
```

- [ ] **Step 3: Verify syntax**

```bash
cd /Users/yusufbek/Desktop/telegram-lead-bot
python3 -c "from bot.services.scheduler_service import create_scheduler; print('OK')"
```
Expected: `OK`

- [ ] **Step 4: Restart bot and confirm all 4 jobs**

```bash
pkill -f "bot.main"; sleep 1 && python3 -m bot.main > /tmp/bot_p1b.log 2>&1 &
sleep 4 && cat /tmp/bot_p1b.log
pkill -f "bot.main"
```

Expected: 4 jobs in startup log — `run_followups`, `check_followup_reminders`, `detect_stale_leads`, `heartbeat`.
Send `/jobs` as admin to confirm all 4 appear with countdown times.

---

### Task 6: CRM — Helper functions + Today's Priorities widget

**Files:**
- Modify: `crm/index.html`

Add two helper functions and a Today's Priorities widget at the top of the Dashboard. This requires two separate edits to the file.

**Edit A: Add helper functions**

- [ ] **Step 1: Add `isStale`, `responseTimeBadge`, and `computeScoreBreakdown` helpers**

Find this exact block in `crm/index.html` (around line 697):

```javascript
    function scoreColor(score) {
      if (score == null) return '#94a3b8';
      if (score > 50) return '#22c55e';
      if (score >= 20) return '#eab308';
      return '#ef4444';
    }
```

Replace with:

```javascript
    function scoreColor(score) {
      if (score == null) return '#94a3b8';
      if (score > 50) return '#22c55e';
      if (score >= 20) return '#eab308';
      return '#ef4444';
    }

    // Stale thresholds mirror config.STALE_THRESHOLDS (days per status)
    const STALE_THRESHOLDS_DAYS = { new: 1, contacted: 3, qualified: 7, proposal_sent: 5 };
    function isStale(lead) {
      if (!lead.last_activity_at) return false;
      const threshold = STALE_THRESHOLDS_DAYS[lead.status];
      if (!threshold) return false;
      const daysSince = (Date.now() - new Date(lead.last_activity_at)) / 86400000;
      return daysSince > threshold;
    }

    function responseTimeBadge(lead) {
      if (lead.first_contact_at) {
        const mins = Math.round((new Date(lead.first_contact_at) - new Date(lead.created_at)) / 60000);
        if (mins < 15) return { text: `✅ ${mins}m`, color: '#22c55e', title: 'Contacted quickly' };
        if (mins < 60) return { text: `🟡 ${mins}m`, color: '#eab308', title: 'Contacted in time' };
        const h = Math.floor(mins / 60), m = mins % 60;
        return { text: `🔴 ${h}h${m}m`, color: '#ef4444', title: 'Slow response' };
      }
      if (lead.status !== 'new') return null;
      const mins = Math.round((Date.now() - new Date(lead.created_at)) / 60000);
      if (mins < 60) return { text: `⏳ ${mins}m`, color: '#eab308', title: 'Waiting for contact' };
      const h = Math.floor(mins / 60), m = mins % 60;
      return { text: `🔴 ${h}h${m}m`, color: '#ef4444', title: 'Waiting too long' };
    }

    function computeScoreBreakdown(lead, events, convos) {
      const items = [];
      let total = 0;
      const add = (label, pts) => { items.push({ label, pts }); total += pts; };
      if (lead.phone) add('Телефон поделён', 30);
      if (lead.email) add('Email поделён', 20);
      const userMsgs = (convos || []).filter(m => m.role === 'user').length;
      if (userMsgs >= 10) add(`${userMsgs} сообщений в чате`, 20);
      else if (userMsgs >= 5) add(`${userMsgs} сообщений в чате`, 15);
      else if (userMsgs >= 2) add(`${userMsgs} сообщений в чате`, 5);
      const evTypes = new Set((events || []).map(e => e.event_type));
      if (evTypes.has('twa_open')) add('Открыл портфолио', 10);
      if (evTypes.has('callback_request')) add('Запросил звонок', 25);
      if (evTypes.has('projects')) add('Просмотрел проекты', 10);
      if (evTypes.has('services')) add('Просмотрел услуги', 5);
      return { items, total };
    }
```

**Edit B: Add Today's Priorities widget to Dashboard**

- [ ] **Step 2: Add `priorities` state and fetch logic to `Dashboard`**

Find this exact line in the `Dashboard` function (around line 749):

```javascript
      const [activity, setActivity] = useState([]);
```

Replace with:

```javascript
      const [activity, setActivity] = useState([]);
      const [priorities, setPriorities] = useState({ newUncontacted: [], overdueFollowups: [], hotNoPhone: [], todayFollowups: [] });
```

- [ ] **Step 3: Add priorities fetch inside `Dashboard.load()`**

Find this exact block inside the `load` callback (the last `} catch` before `setLoading(false)`):

```javascript
        } catch (e) {
          console.error(e);
          showToast('Failed to load dashboard: ' + e.message, 'error');
        } finally {
          setLoading(false);
        }
```

Replace with:

```javascript
          // Priorities widget data
          const todayStart = new Date(); todayStart.setHours(0, 0, 0, 0);
          const todayEnd = new Date(); todayEnd.setHours(23, 59, 59, 999);
          const nowIso = new Date().toISOString();
          const { data: reminders } = await supabase
            .from('followup_reminders')
            .select('id, telegram_id, note, scheduled_for')
            .eq('completed', false);
          const overdue = (reminders || []).filter(r => new Date(r.scheduled_for) < new Date() );
          const todayRem = (reminders || []).filter(r => {
            const d = new Date(r.scheduled_for);
            return d >= todayStart && d <= todayEnd;
          });
          // Enrich reminders with lead names
          const remTids = [...new Set([...overdue, ...todayRem].map(r => r.telegram_id))];
          let remLeadMap = {};
          if (remTids.length > 0) {
            const { data: remLeads } = await supabase.from('leads').select('telegram_id, first_name, last_name').in('telegram_id', remTids);
            (remLeads || []).forEach(l => { remLeadMap[l.telegram_id] = `${l.first_name || ''} ${l.last_name || ''}`.trim() || '—'; });
          }
          const enrichReminder = r => ({ ...r, leadName: remLeadMap[r.telegram_id] || '—' });
          setPriorities({
            newUncontacted: leads.filter(l => l.status === 'new' && !l.first_contact_at),
            overdueFollowups: overdue.map(enrichReminder),
            hotNoPhone: leads.filter(l => (l.lead_score || 0) > 50 && !l.phone),
            todayFollowups: todayRem.map(enrichReminder),
          });
        } catch (e) {
          console.error(e);
          showToast('Failed to load dashboard: ' + e.message, 'error');
        } finally {
          setLoading(false);
        }
```

- [ ] **Step 4: Render Today's Priorities widget above stats row**

Find this exact line in the Dashboard's return JSX:

```javascript
          <div className="stats-row">
```

Replace with:

```javascript
          {(priorities.newUncontacted.length > 0 || priorities.overdueFollowups.length > 0 || priorities.hotNoPhone.length > 0 || priorities.todayFollowups.length > 0) && (
            <div className="card" style={{ marginBottom: 16 }}>
              <h3 style={{ marginBottom: 12 }}>🎯 Сегодня в приоритете</h3>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 16 }}>
                {priorities.newUncontacted.length > 0 && (
                  <div style={{ minWidth: 160 }}>
                    <div style={{ fontWeight: 600, color: '#ef4444', marginBottom: 6 }}>🔴 Новые без контакта ({priorities.newUncontacted.length})</div>
                    {priorities.newUncontacted.slice(0, 5).map(l => (
                      <div key={l.id} style={{ fontSize: 13, color: '#475569', padding: '2px 0' }}>
                        {`${l.first_name || ''} ${l.last_name || ''}`.trim() || l.username || '—'}
                      </div>
                    ))}
                    {priorities.newUncontacted.length > 5 && <div style={{ fontSize: 12, color: '#94a3b8' }}>+{priorities.newUncontacted.length - 5} ещё</div>}
                  </div>
                )}
                {priorities.overdueFollowups.length > 0 && (
                  <div style={{ minWidth: 160 }}>
                    <div style={{ fontWeight: 600, color: '#eab308', marginBottom: 6 }}>🟡 Просроченные ({priorities.overdueFollowups.length})</div>
                    {priorities.overdueFollowups.slice(0, 5).map(r => (
                      <div key={r.id} style={{ fontSize: 13, color: '#475569', padding: '2px 0' }}>
                        {r.leadName} — {r.note || '—'}
                      </div>
                    ))}
                  </div>
                )}
                {priorities.hotNoPhone.length > 0 && (
                  <div style={{ minWidth: 160 }}>
                    <div style={{ fontWeight: 600, color: '#22c55e', marginBottom: 6 }}>🟢 Горячие без телефона ({priorities.hotNoPhone.length})</div>
                    {priorities.hotNoPhone.slice(0, 5).map(l => (
                      <div key={l.id} style={{ fontSize: 13, color: '#475569', padding: '2px 0' }}>
                        {`${l.first_name || ''} ${l.last_name || ''}`.trim() || l.username || '—'} ⚡{l.lead_score}
                      </div>
                    ))}
                  </div>
                )}
                {priorities.todayFollowups.length > 0 && (
                  <div style={{ minWidth: 160 }}>
                    <div style={{ fontWeight: 600, color: '#3b82f6', marginBottom: 6 }}>🔵 Сегодня ({priorities.todayFollowups.length})</div>
                    {priorities.todayFollowups.slice(0, 5).map(r => (
                      <div key={r.id} style={{ fontSize: 13, color: '#475569', padding: '2px 0' }}>
                        {r.leadName} — {r.note || '—'}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          )}
          <div className="stats-row">
```

Also update the Dashboard's `load()` fetch to include `first_contact_at` in the leads select (needed for `newUncontacted` filter). Find:

```javascript
          const { data: leads, error: le } = await supabase.from('leads').select('id, status, phone, created_at, lead_score, first_name, last_name, telegram_id, source');
```

Replace with:

```javascript
          const { data: leads, error: le } = await supabase.from('leads').select('id, status, phone, created_at, lead_score, first_name, last_name, telegram_id, source, first_contact_at, last_activity_at');
```

---

### Task 7: CRM — LeadPanel improvements

**Files:**
- Modify: `crm/index.html`

Four changes to `LeadPanel`: (A) follow-up datetime+note UI, (B) `first_contact_at` recorded on status change, (C) response time badge, (D) score breakdown modal.

**Edit A: Add `followupNote` and `showScoreBreakdown` state + update `followup` init**

- [ ] **Step 1: Update LeadPanel state declarations**

Find this exact block in `LeadPanel` (around line 1068):

```javascript
      const [status, setStatus] = useState(lead.status || 'new');
      const [rejection, setRejection] = useState(lead.rejection_reason || '');
      const [assigned, setAssigned] = useState(lead.assigned_to || '');
      const [followup, setFollowup] = useState(lead.next_followup_at ? lead.next_followup_at.slice(0, 10) : '');
      const [saving, setSaving] = useState(false);
```

Replace with:

```javascript
      const [status, setStatus] = useState(lead.status || 'new');
      const [rejection, setRejection] = useState(lead.rejection_reason || '');
      const [assigned, setAssigned] = useState(lead.assigned_to || '');
      const [followup, setFollowup] = useState(lead.next_followup_at ? lead.next_followup_at.slice(0, 16) : '');
      const [followupNote, setFollowupNote] = useState(lead.followup_note || '');
      const [saving, setSaving] = useState(false);
      const [showScoreBreakdown, setShowScoreBreakdown] = useState(false);
```

**Edit B: Update `save()` to include `followup_note` and `first_contact_at`**

- [ ] **Step 2: Update the `updates` object inside `save()`**

Find this exact block inside `save()`:

```javascript
          const updates = {
            status,
            assigned_to: assigned || null,
            next_followup_at: followup || null,
            rejection_reason: status === 'lost' ? (rejection || null) : null,
            updated_at: new Date().toISOString(),
          };
```

Replace with:

```javascript
          const updates = {
            status,
            assigned_to: assigned || null,
            next_followup_at: followup || null,
            followup_note: followupNote || null,
            rejection_reason: status === 'lost' ? (rejection || null) : null,
            updated_at: new Date().toISOString(),
          };
          // Record first contact time when status moves away from 'new' for the first time
          if (lead.status === 'new' && status !== 'new' && !lead.first_contact_at) {
            updates.first_contact_at = new Date().toISOString();
          }
```

**Edit C: Add response time badge and score breakdown to Contact Info section**

- [ ] **Step 3: Update the Score and Created rows in Contact Info**

Find this exact block in the LeadPanel JSX:

```javascript
              <div className="field-row"><span className="label">Score</span><span style={{ color: scoreColor(lead.lead_score), fontWeight: 700 }}>{lead.lead_score ?? 0}</span></div>
              <div className="field-row"><span className="label">Created</span><span>{formatDate(lead.created_at)}</span></div>
```

Replace with:

```javascript
              <div className="field-row">
                <span className="label">Score</span>
                <span
                  style={{ color: scoreColor(lead.lead_score), fontWeight: 700, cursor: 'pointer', textDecoration: 'underline dotted' }}
                  title="Click for breakdown"
                  onClick={() => setShowScoreBreakdown(s => !s)}
                >{lead.lead_score ?? 0} ℹ️</span>
              </div>
              {showScoreBreakdown && (() => {
                const bd = computeScoreBreakdown(lead, events, convo);
                return (
                  <div style={{ background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: 8, padding: '10px 14px', fontSize: 13, marginBottom: 8 }}>
                    {bd.items.length === 0 && <div style={{ color: '#94a3b8' }}>Нет баллов пока</div>}
                    {bd.items.map((item, i) => (
                      <div key={i} style={{ display: 'flex', justifyContent: 'space-between', padding: '2px 0' }}>
                        <span>{item.label}</span><span style={{ fontWeight: 600, color: '#22c55e' }}>+{item.pts}</span>
                      </div>
                    ))}
                    <div style={{ borderTop: '1px solid #e2e8f0', marginTop: 6, paddingTop: 6, display: 'flex', justifyContent: 'space-between', fontWeight: 700 }}>
                      <span>Итого</span><span>{bd.total}</span>
                    </div>
                  </div>
                );
              })()}
              <div className="field-row"><span className="label">Created</span><span>{formatDate(lead.created_at)}</span></div>
              {(() => {
                const badge = responseTimeBadge(lead);
                if (!badge) return null;
                return (
                  <div className="field-row">
                    <span className="label">Response</span>
                    <span style={{ color: badge.color, fontWeight: 600, fontSize: 13 }} title={badge.title}>{badge.text}</span>
                  </div>
                );
              })()}
```

**Edit D: Upgrade follow-up field to datetime-local + add note textarea**

- [ ] **Step 4: Replace the follow-up date input with datetime + note**

Find this exact block in LeadPanel's "Status & Assignment" section:

```javascript
              <div className="form-group">
                <label>Next Follow-up</label>
                <input type="date" value={followup} onChange={e => setFollowup(e.target.value)} />
              </div>
```

Replace with:

```javascript
              <div className="form-group">
                <label>Next Follow-up</label>
                <input
                  type="datetime-local"
                  value={followup}
                  onChange={e => setFollowup(e.target.value)}
                  style={followup && new Date(followup) < new Date() ? { borderColor: '#ef4444', color: '#ef4444' } : {}}
                />
                {followup && new Date(followup) < new Date() && (
                  <div style={{ color: '#ef4444', fontSize: 12, marginTop: 4 }}>⚠️ Просрочено</div>
                )}
              </div>
              <div className="form-group">
                <label>Follow-up Note</label>
                <textarea
                  value={followupNote}
                  onChange={e => setFollowupNote(e.target.value)}
                  placeholder="What to discuss..."
                  rows="2"
                  style={{ width: '100%', padding: 8, border: '1px solid #e2e8f0', borderRadius: 6, fontFamily: 'inherit', fontSize: 14, resize: 'vertical' }}
                />
              </div>
```

---

### Task 8: CRM — Stale indicator + response time badge on table rows and Kanban cards

**Files:**
- Modify: `crm/index.html`

**Edit A: Stale border on LeadsTable rows**

- [ ] **Step 1: Add stale styling to table rows**

Find this exact line in LeadsTable's tbody:

```javascript
                  <tr key={l.id} onClick={() => onOpenLead(l)}>
```

Replace with:

```javascript
                  <tr key={l.id} onClick={() => onOpenLead(l)} style={isStale(l) ? { borderLeft: '3px solid #ef4444', background: '#fff5f5' } : {}}>
```

**Edit B: Response time badge in table Name column**

- [ ] **Step 2: Add badge next to name in table rows**

Find this exact line in the table body:

```javascript
                    <td>{[l.first_name, l.last_name].filter(Boolean).join(' ') || l.username || '—'}</td>
```

Replace with:

```javascript
                    <td>
                      {[l.first_name, l.last_name].filter(Boolean).join(' ') || l.username || '—'}
                      {(() => { const b = responseTimeBadge(l); return b ? <span style={{ marginLeft: 6, fontSize: 11, color: b.color }} title={b.title}>{b.text}</span> : null; })()}
                    </td>
```

**Edit C: Stale border on Kanban cards**

- [ ] **Step 3: Add stale styling to Kanban cards**

Find this exact block in the Kanban component:

```javascript
                    <div
                      key={l.id}
                      className="kanban-card"
                      draggable
                      onDragStart={e => handleDragStart(e, l)}
                      onClick={() => onOpenLead(l)}
                    >
```

Replace with:

```javascript
                    <div
                      key={l.id}
                      className="kanban-card"
                      draggable
                      onDragStart={e => handleDragStart(e, l)}
                      onClick={() => onOpenLead(l)}
                      style={isStale(l) ? { borderLeft: '3px solid #ef4444' } : {}}
                    >
```

---

### Task 9: Deploy CRM

**Files:**
- Deploy: `crm/` to Vercel

- [ ] **Step 1: Deploy**

```bash
cd /Users/yusufbek/Desktop/telegram-lead-bot/crm
npx vercel --prod --yes
```

Expected output includes:
```
Aliased: https://crm-mqsd.vercel.app
```

- [ ] **Step 2: Open CRM and verify**

Open `https://crm-mqsd.vercel.app` via `/crm` bot command.

Check each feature:
1. Dashboard shows "🎯 Сегодня в приоритете" widget (if any leads qualify)
2. Lead panel → Score shows `ℹ️` clickable breakdown
3. Lead panel → Follow-up field is now datetime-local with a note textarea
4. Lead panel → Overdue follow-up shows red border and "⚠️ Просрочено"
5. Lead panel → Contact Info shows "Response" row with time badge
6. LeadsTable rows → stale leads have red left border
7. Kanban cards → stale leads have red left border

- [ ] **Step 3: Restart bot (now has 4 jobs)**

```bash
pkill -f "bot.main"; python3 -m bot.main
```

Send `/jobs` as admin — confirm 4 jobs: `run_followups`, `check_followup_reminders`, `detect_stale_leads`, `heartbeat`.

- [ ] **Phase 1 complete ✅**
