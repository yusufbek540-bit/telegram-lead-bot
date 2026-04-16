# Phase 3 — Revenue & Conversion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add deal values, proposal tracking, DB-driven rejection reasons, Sources ROI page, and a "Why we lose" chart to the CRM.

**Architecture:** All revenue data lives in Supabase. The CRM browser reads it via the existing `supabase` JS client. A new bot job (`proposal_expiry.py`) sends 3-day-before-expiry alerts and marks overdue proposals expired. The `rejection_reasons` table replaces the hardcoded array in `index.html`.

**Tech Stack:** Supabase (PostgreSQL), React 18 UMD, Recharts 2.12.7, Python 3.9 aiogram 3.x + APScheduler, existing `db` singleton.

---

## File Map

| File | Action | Purpose |
|---|---|---|
| `database/migrations/003_phase3.sql` | Create | DB schema: deal_value, proposals, rejection_reasons, ad_campaigns |
| `bot/services/proposal_expiry.py` | Create | 6-hourly job: 3-day warning + expire overdue proposals |
| `bot/services/scheduler_service.py` | Modify | Register proposal_expiry job |
| `crm/index.html` | Modify | All CRM UI changes (7 distinct areas) |

---

## Task 1: Database Migration

**Files:**
- Create: `database/migrations/003_phase3.sql`

- [ ] **Step 1: Write the migration file**

```sql
-- ============================================================
-- Phase 3 — Revenue & Conversion Migration
-- Safe to re-run (all statements are idempotent)
-- Run in Supabase SQL Editor: https://supabase.com/dashboard
-- ============================================================

-- Deal value on leads
ALTER TABLE leads ADD COLUMN IF NOT EXISTS deal_value NUMERIC;
ALTER TABLE leads ADD COLUMN IF NOT EXISTS deal_currency TEXT DEFAULT 'UZS';

-- Proposals table
CREATE TABLE IF NOT EXISTS proposals (
    id            BIGSERIAL PRIMARY KEY,
    telegram_id   BIGINT REFERENCES leads(telegram_id) ON DELETE CASCADE,
    title         TEXT NOT NULL,
    amount        NUMERIC NOT NULL,
    currency      TEXT NOT NULL DEFAULT 'UZS',
    valid_until   DATE NOT NULL,
    status        TEXT NOT NULL DEFAULT 'sent',  -- sent | accepted | rejected | expired
    created_by    TEXT,
    created_at    TIMESTAMPTZ DEFAULT NOW(),
    updated_at    TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS proposals_telegram_idx ON proposals(telegram_id);
CREATE INDEX IF NOT EXISTS proposals_status_idx   ON proposals(status);

-- Rejection reasons table (DB-driven, replaces hardcoded JS array)
CREATE TABLE IF NOT EXISTS rejection_reasons (
    id         BIGSERIAL PRIMARY KEY,
    label      TEXT NOT NULL UNIQUE,
    sort_order INT  NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Pre-populate with existing hardcoded reasons (safe to re-run)
INSERT INTO rejection_reasons (label, sort_order) VALUES
  ('Budget',            1),
  ('Wrong service',     2),
  ('No response',       3),
  ('Chose competitor',  4),
  ('Not a fit',         5),
  ('Other',             6)
ON CONFLICT (label) DO NOTHING;

-- Ad campaigns for ROI tracking (Phase 3 foundation, full UI in Phase 5)
CREATE TABLE IF NOT EXISTS ad_campaigns (
    id         BIGSERIAL PRIMARY KEY,
    name       TEXT NOT NULL,
    source_key TEXT NOT NULL UNIQUE,  -- matches leads.source value
    budget     NUMERIC,
    currency   TEXT DEFAULT 'UZS',
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

- [ ] **Step 2: Run in Supabase SQL Editor**

Open https://supabase.com/dashboard → SQL Editor → paste the file → Run.
Expected: no errors, "Success. No rows returned."

- [ ] **Step 3: Verify tables exist**

In Supabase Table Editor confirm:
- `leads` has columns `deal_value` (numeric, nullable) and `deal_currency` (text, default 'UZS')
- `proposals` table with all columns
- `rejection_reasons` table with 6 pre-populated rows
- `ad_campaigns` table

- [ ] **Step 4: Commit**

```bash
cd /Users/yusufbek/Desktop/telegram-lead-bot
git add database/migrations/003_phase3.sql
git commit -m "feat: phase3 revenue migration — deal_value, proposals, rejection_reasons, ad_campaigns"
```

---

## Task 2: Bot — Proposal Expiry Job

**Files:**
- Create: `bot/services/proposal_expiry.py`
- Modify: `bot/services/scheduler_service.py` (lines 28–172)

- [ ] **Step 1: Create `bot/services/proposal_expiry.py`**

```python
"""
Proposal expiry job — runs every 6 hours.

Actions:
  1. Proposals expiring within 3 days → send one-time warning to admins.
  2. Proposals past valid_until with status='sent' → mark status='expired'.
"""

import logging
import time
from datetime import datetime, timezone, timedelta

from aiogram import Bot

from bot.config import config
from bot.services.db_service import db

logger = logging.getLogger(__name__)


async def check_proposal_expiry(bot: Bot):
    start = time.monotonic()
    logger.info("check_proposal_expiry: starting")
    try:
        now = datetime.now(timezone.utc)
        three_days = (now + timedelta(days=3)).date().isoformat()
        today = now.date().isoformat()

        # 1. Find proposals expiring within 3 days (not yet warned, status='sent')
        soon = db.client.table("proposals") \
            .select("id, telegram_id, title, amount, currency, valid_until, created_by") \
            .eq("status", "sent") \
            .lte("valid_until", three_days) \
            .gte("valid_until", today) \
            .execute()

        for p in (soon.data or []):
            # Check if we already sent a warning event for this proposal
            existing = db.client.table("events") \
                .select("id") \
                .eq("telegram_id", p["telegram_id"]) \
                .eq("event_type", f"proposal_expiry_warning_{p['id']}") \
                .execute()
            if existing.data:
                continue  # Already warned

            # Fetch lead name
            lead_res = db.client.table("leads") \
                .select("first_name, last_name, username") \
                .eq("telegram_id", p["telegram_id"]) \
                .limit(1).execute()
            lead = lead_res.data[0] if lead_res.data else {}
            lead_name = (
                f"{lead.get('first_name', '')} {lead.get('last_name', '')}".strip()
                or lead.get("username") or "Unknown"
            )

            amount_fmt = f"{p['amount']:,.0f} {p['currency']}"
            msg = (
                f"⏰ <b>Предложение истекает через 3 дня!</b>\n\n"
                f"Лид: <b>{lead_name}</b>\n"
                f"Тема: {p['title']}\n"
                f"Сумма: {amount_fmt}\n"
                f"Действует до: {p['valid_until']}\n"
                f"Создал: {p.get('created_by', '—')}"
            )
            for admin_id in config.ADMIN_IDS:
                try:
                    await bot.send_message(admin_id, msg, parse_mode="HTML")
                except Exception:
                    pass

            # Record warning so we don't send again
            db.client.table("events").insert({
                "telegram_id": p["telegram_id"],
                "event_type": f"proposal_expiry_warning_{p['id']}",
                "data": {"proposal_id": p["id"]},
            }).execute()

        # 2. Mark overdue proposals as expired
        expired = db.client.table("proposals") \
            .update({"status": "expired", "updated_at": now.isoformat()}) \
            .eq("status", "sent") \
            .lt("valid_until", today) \
            .execute()

        expired_count = len(expired.data or [])
        if expired_count:
            logger.info(f"check_proposal_expiry: marked {expired_count} proposals expired")

        elapsed = time.monotonic() - start
        logger.info(f"check_proposal_expiry: done in {elapsed:.2f}s")
    except Exception as e:
        logger.error(f"check_proposal_expiry: failed — {e}", exc_info=True)
```

- [ ] **Step 2: Register the job in `bot/services/scheduler_service.py`**

Add import at line 29 (after the stale_detector import):
```python
from bot.services.proposal_expiry import check_proposal_expiry
```

Add job registration inside `create_scheduler()` before `return scheduler` (after the detect_stale_leads block at line 170):
```python
    scheduler.add_job(
        check_proposal_expiry,
        trigger="interval",
        hours=config.JOB_INTERVALS["proposal_expiry_hours"],
        args=[bot],
        id="check_proposal_expiry",
        replace_existing=True,
    )
```

- [ ] **Step 3: Verify `config.py` already has the key**

`config.py` already has `"proposal_expiry_hours": 6` in `JOB_INTERVALS`. No change needed.

- [ ] **Step 4: Quick smoke test — restart bot and check /jobs**

```bash
pkill -f "bot.main"; python3 -m bot.main &
# In Telegram, send /jobs as admin
# Expected: "check_proposal_expiry" appears in the list with next run time
```

- [ ] **Step 5: Commit**

```bash
git add bot/services/proposal_expiry.py bot/services/scheduler_service.py
git commit -m "feat: proposal expiry job — 3-day warning + auto-expire"
```

---

## Task 3: CRM — Deal Value Fields on LeadPanel

**Files:**
- Modify: `crm/index.html` (LeadPanel component, around line 1319)

The `LeadPanel` component currently has state for `status`, `rejection`, `assigned`, `followup`, `followupNote`. Add `dealValue` and `dealCurrency` state, render two inputs in the Save section, and include them in the `updates` object on save.

- [ ] **Step 1: Add deal value state to LeadPanel**

Find the LeadPanel state block (around line 1320–1327). After `const [showScoreBreakdown, setShowScoreBreakdown] = useState(false);` add:

```jsx
      const [dealValue, setDealValue] = useState(lead.deal_value != null ? String(lead.deal_value) : '');
      const [dealCurrency, setDealCurrency] = useState(lead.deal_currency || 'UZS');
```

- [ ] **Step 2: Add deal_value/deal_currency to the save `updates` object**

Find the `updates` object inside `save()` (around line 1358). Add to it:

```jsx
            deal_value: dealValue !== '' ? parseFloat(dealValue) : null,
            deal_currency: dealCurrency,
```

- [ ] **Step 3: Render deal value inputs in the LeadPanel UI**

Find the section in LeadPanel's JSX that renders the followup inputs (around line 1490–1520). Add a deal value section above the Save button:

```jsx
              <div style={{ marginBottom: 12 }}>
                <label style={{ fontSize: 12, color: '#64748b', fontWeight: 600, display: 'block', marginBottom: 4 }}>
                  Deal Value
                </label>
                <div style={{ display: 'flex', gap: 8 }}>
                  <input
                    type="number"
                    min="0"
                    placeholder="e.g. 5000000"
                    value={dealValue}
                    onChange={e => setDealValue(e.target.value)}
                    style={{ flex: 1, padding: '6px 10px', border: '1px solid #e2e8f0', borderRadius: 6, fontSize: 13 }}
                  />
                  <select
                    value={dealCurrency}
                    onChange={e => setDealCurrency(e.target.value)}
                    style={{ padding: '6px 10px', border: '1px solid #e2e8f0', borderRadius: 6, fontSize: 13 }}
                  >
                    <option value="UZS">UZS</option>
                    <option value="USD">USD</option>
                  </select>
                </div>
              </div>
```

- [ ] **Step 4: Test in browser**

Open the CRM, click a lead, verify the Deal Value inputs appear. Enter a value, click Save, reload the page, reopen the lead — verify the value persists.

- [ ] **Step 5: Commit**

```bash
git add crm/index.html
git commit -m "feat: deal value fields on LeadPanel (UZS/USD)"
```

---

## Task 4: CRM — Proposals (Create + History)

**Files:**
- Modify: `crm/index.html` (LeadPanel component)

Add a "Proposals" section below the deal value inputs in LeadPanel. It shows existing proposals in a list and a "Create Proposal" button that expands a form. The form has: title, amount, currency, valid_until. On submit: insert into `proposals` table, refresh list.

- [ ] **Step 1: Add proposal state to LeadPanel**

After the `dealCurrency` state line, add:

```jsx
      const [proposals, setProposals] = useState([]);
      const [showProposalForm, setShowProposalForm] = useState(false);
      const [propTitle, setPropTitle] = useState('');
      const [propAmount, setPropAmount] = useState('');
      const [propCurrency, setPropCurrency] = useState('UZS');
      const [propValidUntil, setPropValidUntil] = useState('');
      const [savingProposal, setSavingProposal] = useState(false);
```

- [ ] **Step 2: Load proposals in `loadDetails()`**

Find the `loadDetails` function (around line 1336). Add proposals to the `Promise.all` array:

```jsx
      const loadDetails = useCallback(async () => {
        try {
          const [c, e, cm, h, pr] = await Promise.all([
            supabase.from('conversations').select('*').eq('telegram_id', lead.telegram_id).order('created_at', { ascending: true }),
            supabase.from('events').select('*').eq('telegram_id', lead.telegram_id).order('created_at', { ascending: false }),
            supabase.from('comments').select('*').eq('telegram_id', lead.telegram_id).order('is_pinned', { ascending: false }).order('created_at', { ascending: true }),
            supabase.from('status_history').select('*').eq('telegram_id', lead.telegram_id).order('created_at', { ascending: false }),
            supabase.from('proposals').select('*').eq('telegram_id', lead.telegram_id).order('created_at', { ascending: false }),
          ]);
          setConvo(c.data || []);
          setEvents(e.data || []);
          setComments(cm.data || []);
          setHistory(h.data || []);
          setProposals(pr.data || []);
        } catch (err) {
          showToast('Failed to load lead details', 'error');
        }
      }, [lead.telegram_id, showToast]);
```

- [ ] **Step 3: Add `createProposal` handler to LeadPanel**

After the `save` function, add:

```jsx
      const createProposal = async () => {
        if (!propTitle.trim()) { showToast('Title required', 'error'); return; }
        const amt = parseFloat(propAmount);
        if (!amt || amt <= 0) { showToast('Valid amount required', 'error'); return; }
        if (!propValidUntil) { showToast('Valid until date required', 'error'); return; }
        setSavingProposal(true);
        try {
          const { error } = await supabase.from('proposals').insert({
            telegram_id: lead.telegram_id,
            title: propTitle.trim(),
            amount: amt,
            currency: propCurrency,
            valid_until: propValidUntil,
            status: 'sent',
            created_by: getCrmUserName() || 'CRM',
          });
          if (error) throw error;
          setPropTitle(''); setPropAmount(''); setPropValidUntil('');
          setShowProposalForm(false);
          showToast('Proposal created', 'success');
          loadDetails();
        } catch (err) {
          showToast('Failed: ' + err.message, 'error');
        } finally {
          setSavingProposal(false);
        }
      };

      const updateProposalStatus = async (proposalId, newStatus) => {
        const { error } = await supabase.from('proposals')
          .update({ status: newStatus, updated_at: new Date().toISOString() })
          .eq('id', proposalId);
        if (error) { showToast('Update failed', 'error'); return; }
        showToast('Proposal updated', 'success');
        loadDetails();
      };
```

- [ ] **Step 4: Add Proposals section JSX to LeadPanel**

After the deal value inputs section (added in Task 3), add the proposals section:

```jsx
              {/* ── Proposals ── */}
              <div style={{ marginBottom: 16 }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
                  <label style={{ fontSize: 12, color: '#64748b', fontWeight: 600 }}>Proposals ({proposals.length})</label>
                  <button
                    className="btn btn-primary"
                    style={{ fontSize: 12, padding: '4px 10px' }}
                    onClick={() => setShowProposalForm(f => !f)}
                  >
                    {showProposalForm ? 'Cancel' : '+ Create'}
                  </button>
                </div>

                {showProposalForm && (
                  <div style={{ background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: 8, padding: 12, marginBottom: 10 }}>
                    <input
                      placeholder="Title (e.g. SMM Package)"
                      value={propTitle}
                      onChange={e => setPropTitle(e.target.value)}
                      style={{ width: '100%', padding: '6px 10px', border: '1px solid #e2e8f0', borderRadius: 6, marginBottom: 8, fontSize: 13 }}
                    />
                    <div style={{ display: 'flex', gap: 8, marginBottom: 8 }}>
                      <input
                        type="number" min="0" placeholder="Amount"
                        value={propAmount}
                        onChange={e => setPropAmount(e.target.value)}
                        style={{ flex: 1, padding: '6px 10px', border: '1px solid #e2e8f0', borderRadius: 6, fontSize: 13 }}
                      />
                      <select value={propCurrency} onChange={e => setPropCurrency(e.target.value)}
                        style={{ padding: '6px 10px', border: '1px solid #e2e8f0', borderRadius: 6, fontSize: 13 }}>
                        <option value="UZS">UZS</option>
                        <option value="USD">USD</option>
                      </select>
                    </div>
                    <div style={{ marginBottom: 8 }}>
                      <label style={{ fontSize: 12, color: '#64748b', display: 'block', marginBottom: 4 }}>Valid until</label>
                      <input type="date" value={propValidUntil} onChange={e => setPropValidUntil(e.target.value)}
                        style={{ padding: '6px 10px', border: '1px solid #e2e8f0', borderRadius: 6, fontSize: 13, width: '100%' }} />
                    </div>
                    <button className="btn btn-primary" style={{ width: '100%' }} onClick={createProposal} disabled={savingProposal}>
                      {savingProposal ? 'Saving…' : 'Save Proposal'}
                    </button>
                  </div>
                )}

                {proposals.length === 0 ? (
                  <div style={{ fontSize: 13, color: '#94a3b8' }}>No proposals yet.</div>
                ) : (
                  proposals.map(p => {
                    const statusColors = { sent: '#6366f1', accepted: '#22c55e', rejected: '#ef4444', expired: '#94a3b8' };
                    const amtFmt = Number(p.amount).toLocaleString();
                    return (
                      <div key={p.id} style={{ border: '1px solid #e2e8f0', borderRadius: 8, padding: '10px 12px', marginBottom: 8 }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
                          <span style={{ fontWeight: 600, fontSize: 13 }}>{p.title}</span>
                          <span style={{ background: statusColors[p.status] || '#94a3b8', color: '#fff', borderRadius: 10, padding: '2px 8px', fontSize: 11, fontWeight: 600 }}>
                            {p.status}
                          </span>
                        </div>
                        <div style={{ fontSize: 13, color: '#64748b' }}>{amtFmt} {p.currency} · until {p.valid_until}</div>
                        <div style={{ fontSize: 12, color: '#94a3b8', marginTop: 2 }}>by {p.created_by || '—'}</div>
                        {p.status === 'sent' && (
                          <div style={{ display: 'flex', gap: 6, marginTop: 8 }}>
                            <button className="btn" style={{ fontSize: 12, padding: '3px 10px', color: '#22c55e', borderColor: '#22c55e' }}
                              onClick={() => updateProposalStatus(p.id, 'accepted')}>Accept</button>
                            <button className="btn" style={{ fontSize: 12, padding: '3px 10px', color: '#ef4444', borderColor: '#ef4444' }}
                              onClick={() => updateProposalStatus(p.id, 'rejected')}>Reject</button>
                          </div>
                        )}
                      </div>
                    );
                  })
                )}
              </div>
```

- [ ] **Step 5: Test in browser**

Open a lead panel → Proposals section appears with count. Click "+ Create" → form expands. Fill in title, amount, valid until → Save. Verify proposal appears in list with "sent" badge. Click "Accept" → badge turns green.

- [ ] **Step 6: Commit**

```bash
git add crm/index.html
git commit -m "feat: proposal create/view/accept/reject in LeadPanel"
```

---

## Task 5: CRM — Rejection Reasons from DB

**Files:**
- Modify: `crm/index.html` (LeadPanel + Settings component)

Replace the hardcoded `REJECTION_REASONS` array in LeadPanel with a fetch from the `rejection_reasons` table. Add a "Rejection Reasons" management card to Settings.

- [ ] **Step 1: Remove hardcoded REJECTION_REASONS from LeadPanel, load from DB**

Find line 804:
```js
    const REJECTION_REASONS = ['Budget', 'Wrong service', 'No response', 'Chose competitor', 'Not a fit', 'Other'];
```
Delete this line.

In `LeadPanel`, add state after the `teamMembers` state:
```jsx
      const [rejectionReasons, setRejectionReasons] = useState([]);
      React.useEffect(() => {
        supabase.from('rejection_reasons').select('label').order('sort_order').then(({ data }) => {
          setRejectionReasons((data || []).map(r => r.label));
        });
      }, []);
```

- [ ] **Step 2: Update the rejection reason `<select>` in LeadPanel JSX**

Find the select that uses `REJECTION_REASONS` (around line 1502–1504):
```jsx
                    {REJECTION_REASONS.map(r => <option key={r} value={r}>{r}</option>)}
```
Replace with:
```jsx
                    {rejectionReasons.map(r => <option key={r} value={r}>{r}</option>)}
```

- [ ] **Step 3: Add Rejection Reasons management to Settings**

Find the `Settings` component's JSX `return` block (around line 1773). After the Team Members card (`</div>` closing the second `.card`), add:

```jsx
          <div className="card" style={{ marginBottom: 16 }}>
            <h3 style={{ marginBottom: 12 }}>Rejection Reasons</h3>
            <RejectionReasonsManager showToast={showToast} />
          </div>
```

- [ ] **Step 4: Add `RejectionReasonsManager` component (before Settings function)**

Place this just above the `function Settings` line:

```jsx
    function RejectionReasonsManager({ showToast }) {
      const [reasons, setReasons] = useState([]);
      const [newLabel, setNewLabel] = useState('');

      const load = () => {
        supabase.from('rejection_reasons').select('id, label, sort_order').order('sort_order').then(({ data }) => {
          setReasons(data || []);
        });
      };
      React.useEffect(load, []);

      const add = async () => {
        const label = newLabel.trim();
        if (!label) { showToast('Label required', 'error'); return; }
        const maxOrder = reasons.length ? Math.max(...reasons.map(r => r.sort_order)) : 0;
        const { error } = await supabase.from('rejection_reasons').insert({ label, sort_order: maxOrder + 1 });
        if (error) { showToast(error.message, 'error'); return; }
        setNewLabel('');
        showToast('Reason added', 'success');
        load();
      };

      const remove = async (id) => {
        await supabase.from('rejection_reasons').delete().eq('id', id);
        showToast('Removed', 'success');
        load();
      };

      return (
        <div>
          {reasons.length === 0 ? (
            <div style={{ color: '#64748b', fontSize: 13, marginBottom: 12 }}>No reasons yet.</div>
          ) : (
            <div style={{ border: '1px solid #e2e8f0', borderRadius: 6, marginBottom: 12 }}>
              {reasons.map(r => (
                <div key={r.id} style={{ display: 'flex', alignItems: 'center', padding: '8px 12px', borderBottom: '1px solid #e2e8f0' }}>
                  <span style={{ flex: 1 }}>{r.label}</span>
                  <button onClick={() => remove(r.id)} style={{ background: 'none', border: 'none', color: '#ef4444', cursor: 'pointer', fontSize: 16 }}>×</button>
                </div>
              ))}
            </div>
          )}
          <div style={{ display: 'flex', gap: 8 }}>
            <input
              value={newLabel}
              onChange={e => setNewLabel(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && add()}
              placeholder="e.g. Price too high"
              style={{ flex: 1, padding: 8, border: '1px solid #e2e8f0', borderRadius: 6 }}
            />
            <button className="btn btn-primary" onClick={add}>Add</button>
          </div>
        </div>
      );
    }
```

- [ ] **Step 5: Test in browser**

Go to Settings → Rejection Reasons card shows 6 items from DB. Add a new one → appears. Delete one → removed. Open a lead panel, set status to "Lost" → rejection reason dropdown shows DB list.

- [ ] **Step 6: Commit**

```bash
git add crm/index.html
git commit -m "feat: rejection reasons from DB — LeadPanel dropdown + Settings management"
```

---

## Task 6: CRM — Kanban Revenue Totals

**Files:**
- Modify: `crm/index.html` (Kanban component, around line 1606)

Add revenue total (sum of `deal_value`) to each Kanban column header. The `deal_value` field is already fetched via `select('*')`.

- [ ] **Step 1: Add revenue formatting helper near the top of the script block (after `timeAgo`)**

Find the `timeAgo` function. After it, add:

```js
    function fmtRevenue(val, currency) {
      if (!val) return null;
      if (val >= 1000000) return `${(val / 1000000).toFixed(1)}M ${currency || 'UZS'}`;
      if (val >= 1000) return `${(val / 1000).toFixed(0)}K ${currency || 'UZS'}`;
      return `${val} ${currency || 'UZS'}`;
    }
```

- [ ] **Step 2: Compute revenue per column in Kanban render**

Inside the `Kanban` component's return JSX, in the `STATUSES.map(s => {...})` block, before the `return (...)`, compute:

```jsx
            const colRevenue = colLeads.reduce((sum, l) => sum + (l.deal_value || 0), 0);
            const colCurrency = colLeads.find(l => l.deal_value)?.deal_currency || 'UZS';
```

- [ ] **Step 3: Show revenue in Kanban column header**

Find the `kanban-col-header` div (around line 1670). Replace:

```jsx
                <div className="kanban-col-header">
                  <span className="title" style={{ color: STATUS_COLORS[s] }}>{STATUS_LABELS[s]}</span>
                  <span style={{ background: STATUS_COLORS[s], color: '#fff', padding: '2px 8px', borderRadius: 10, fontSize: 11, fontWeight: 600 }}>{colLeads.length}</span>
                </div>
```

With:

```jsx
                <div className="kanban-col-header">
                  <span className="title" style={{ color: STATUS_COLORS[s] }}>{STATUS_LABELS[s]}</span>
                  <span style={{ background: STATUS_COLORS[s], color: '#fff', padding: '2px 8px', borderRadius: 10, fontSize: 11, fontWeight: 600 }}>{colLeads.length}</span>
                </div>
                {colRevenue > 0 && (
                  <div style={{ fontSize: 11, color: '#64748b', marginTop: 2, paddingLeft: 2 }}>
                    💰 {fmtRevenue(colRevenue, colCurrency)}
                  </div>
                )}
```

- [ ] **Step 4: Test in browser**

Set a deal value on 2–3 leads, open Pipeline tab. Columns with deal values show "💰 5.0M UZS" style revenue totals below the count badge.

- [ ] **Step 5: Commit**

```bash
git add crm/index.html
git commit -m "feat: kanban column revenue totals"
```

---

## Task 7: CRM — Sources ROI Page

**Files:**
- Modify: `crm/index.html` (App component, sidebar nav, add Sources component)

Add a "Sources" tab to the sidebar. The Sources page shows a table: source name, lead count, conversion rate, converted deal value, and average deal.

- [ ] **Step 1: Add "Sources" to sidebar nav in App component**

Find the sidebar nav (around line 2112):
```jsx
              <a className={tab === 'pipeline' ? 'active' : ''} onClick={() => setTab('pipeline')}>🎯 Pipeline</a>
              <a className={tab === 'settings' ? 'active' : ''} onClick={() => setTab('settings')}>⚙️ Settings</a>
```
Replace with:
```jsx
              <a className={tab === 'pipeline' ? 'active' : ''} onClick={() => setTab('pipeline')}>🎯 Pipeline</a>
              <a className={tab === 'sources' ? 'active' : ''} onClick={() => setTab('sources')}>📡 Sources ROI</a>
              <a className={tab === 'settings' ? 'active' : ''} onClick={() => setTab('settings')}>⚙️ Settings</a>
```

- [ ] **Step 2: Mount Sources component in the tab switch area**

Find the tab render block (around line 2136):
```jsx
              {tab === 'pipeline' && <Kanban ... />}
              {tab === 'settings' && <Settings ... />}
```
Add:
```jsx
              {tab === 'sources' && <Sources showToast={showToast} refreshKey={refreshKey} />}
```

- [ ] **Step 3: Add `Sources` component (before the App function)**

Place the full component just before `function App()`:

```jsx
    function Sources({ showToast, refreshKey }) {
      const [rows, setRows] = useState([]);
      const [loading, setLoading] = useState(true);

      const load = useCallback(async () => {
        setLoading(true);
        try {
          const { data, error } = await supabase.from('leads')
            .select('source, status, deal_value, deal_currency');
          if (error) throw error;

          // Aggregate by source
          const map = {};
          (data || []).forEach(l => {
            const src = l.source || 'direct';
            if (!map[src]) map[src] = { source: src, count: 0, converted: 0, revenue: 0 };
            map[src].count++;
            if (l.status === 'converted') {
              map[src].converted++;
              map[src].revenue += l.deal_value || 0;
            }
          });

          const result = Object.values(map).sort((a, b) => b.count - a.count);
          setRows(result);
        } catch (e) {
          showToast('Failed to load sources: ' + e.message, 'error');
        } finally {
          setLoading(false);
        }
      }, [showToast]);

      useEffect(() => { load(); }, [load, refreshKey]);

      if (loading) return <div className="center-load"><div className="spinner" /></div>;

      const totalLeads = rows.reduce((s, r) => s + r.count, 0);
      const totalRevenue = rows.reduce((s, r) => s + r.revenue, 0);
      const totalConverted = rows.reduce((s, r) => s + r.converted, 0);

      return (
        <div className="content-area" style={{ padding: 24 }}>
          <h2 style={{ marginBottom: 16, fontSize: 18, fontWeight: 700 }}>Sources ROI</h2>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 16, marginBottom: 24 }}>
            {[
              { label: 'Total Leads', value: totalLeads },
              { label: 'Converted', value: totalConverted },
              { label: 'Total Revenue', value: fmtRevenue(totalRevenue, 'UZS') || '0 UZS' },
            ].map(s => (
              <div key={s.label} className="card" style={{ textAlign: 'center' }}>
                <div style={{ fontSize: 24, fontWeight: 700, color: '#3b82f6' }}>{s.value}</div>
                <div style={{ fontSize: 13, color: '#64748b', marginTop: 4 }}>{s.label}</div>
              </div>
            ))}
          </div>

          <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
            <table className="leads-table" style={{ width: '100%' }}>
              <thead>
                <tr>
                  <th style={{ textAlign: 'left', padding: '12px 16px' }}>Source</th>
                  <th style={{ textAlign: 'right', padding: '12px 16px' }}>Leads</th>
                  <th style={{ textAlign: 'right', padding: '12px 16px' }}>Converted</th>
                  <th style={{ textAlign: 'right', padding: '12px 16px' }}>Conv. Rate</th>
                  <th style={{ textAlign: 'right', padding: '12px 16px' }}>Revenue (UZS)</th>
                  <th style={{ textAlign: 'right', padding: '12px 16px' }}>Avg Deal</th>
                </tr>
              </thead>
              <tbody>
                {rows.map(r => {
                  const rate = r.count ? ((r.converted / r.count) * 100).toFixed(1) : '0.0';
                  const avg = r.converted ? fmtRevenue(r.revenue / r.converted, 'UZS') : '—';
                  return (
                    <tr key={r.source}>
                      <td style={{ padding: '10px 16px', fontWeight: 500 }}>{r.source}</td>
                      <td style={{ padding: '10px 16px', textAlign: 'right' }}>{r.count}</td>
                      <td style={{ padding: '10px 16px', textAlign: 'right' }}>{r.converted}</td>
                      <td style={{ padding: '10px 16px', textAlign: 'right' }}>
                        <span style={{ color: parseFloat(rate) > 10 ? '#22c55e' : '#64748b', fontWeight: 600 }}>
                          {rate}%
                        </span>
                      </td>
                      <td style={{ padding: '10px 16px', textAlign: 'right' }}>
                        {r.revenue > 0 ? fmtRevenue(r.revenue, 'UZS') : '—'}
                      </td>
                      <td style={{ padding: '10px 16px', textAlign: 'right', color: '#64748b' }}>{avg}</td>
                    </tr>
                  );
                })}
                {rows.length === 0 && (
                  <tr><td colSpan="6" style={{ textAlign: 'center', padding: 32, color: '#94a3b8' }}>No source data yet</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      );
    }
```

- [ ] **Step 4: Test in browser**

Click "📡 Sources ROI" in sidebar. Table appears with one row per source. Summary cards at top show totals. Sources with conversion rates above 10% show green.

- [ ] **Step 5: Commit**

```bash
git add crm/index.html
git commit -m "feat: Sources ROI page — conversion rate and revenue by source"
```

---

## Task 8: CRM — "Why We Lose" Bar Chart on Dashboard

**Files:**
- Modify: `crm/index.html` (Dashboard component)

Add a bar chart showing how many leads were lost per rejection reason. Uses Recharts (already loaded). Only rendered when there are lost leads with a rejection reason.

- [ ] **Step 1: Add `lostReasons` state to Dashboard**

Find the Dashboard state declarations (around line 918–925). Add:

```jsx
      const [lostReasons, setLostReasons] = useState([]);
```

- [ ] **Step 2: Compute lost reasons in Dashboard's `load()` function**

The `load()` function already fetches `leads`. After the `setScoreDist(bins)` call, add:

```jsx
          // Why we lose
          const lostMap = {};
          leads.filter(l => l.status === 'lost' && l.rejection_reason).forEach(l => {
            lostMap[l.rejection_reason] = (lostMap[l.rejection_reason] || 0) + 1;
          });
          setLostReasons(Object.entries(lostMap).map(([reason, count]) => ({ reason, count })).sort((a, b) => b.count - a.count));
```

- [ ] **Step 3: Add `rejection_reason` to the Dashboard leads select**

Find the leads select in Dashboard's `load()` (around line 930):
```jsx
          const { data: leads, error: le } = await supabase.from('leads').select('id, status, phone, created_at, lead_score, first_name, last_name, telegram_id, source, first_contact_at, last_activity_at');
```
Replace with:
```jsx
          const { data: leads, error: le } = await supabase.from('leads').select('id, status, phone, created_at, lead_score, first_name, last_name, telegram_id, source, first_contact_at, last_activity_at, rejection_reason');
```

- [ ] **Step 4: Add "Why We Lose" chart to Dashboard JSX**

In Dashboard's return JSX, find the chart grid section. After the Score Distribution chart card, add:

```jsx
            {lostReasons.length > 0 && (
              <div className="card">
                <h3 style={{ marginBottom: 16 }}>Why We Lose Leads</h3>
                <Recharts.BarChart width={340} height={220} data={lostReasons} layout="vertical">
                  <Recharts.CartesianGrid strokeDasharray="3 3" horizontal={false} />
                  <Recharts.XAxis type="number" allowDecimals={false} tick={{ fontSize: 12 }} />
                  <Recharts.YAxis type="category" dataKey="reason" width={120} tick={{ fontSize: 12 }} />
                  <Recharts.Tooltip />
                  <Recharts.Bar dataKey="count" fill="#ef4444" radius={[0, 4, 4, 0]} />
                </Recharts.BarChart>
              </div>
            )}
```

- [ ] **Step 5: Test in browser**

Mark 2–3 test leads as "Lost" with different rejection reasons. Open Dashboard — "Why We Lose Leads" bar chart appears. The chart is hidden when no lost leads exist.

- [ ] **Step 6: Commit**

```bash
git add crm/index.html
git commit -m "feat: why we lose bar chart on Dashboard"
```

---

## Task 9: Deploy to Vercel

**Files:**
- No code changes — deploy what's been built

- [ ] **Step 1: Deploy CRM**

```bash
cd /Users/yusufbek/Desktop/telegram-lead-bot/crm
npx vercel --prod --yes
```

Expected: deployment URL printed, e.g. `https://crm-mqsd.vercel.app`.

- [ ] **Step 2: Restart bot**

```bash
cd /Users/yusufbek/Desktop/telegram-lead-bot
pkill -f "bot.main"; python3 -m bot.main
```

- [ ] **Step 3: Send `/jobs` in Telegram**

Verify `check_proposal_expiry` appears in the job list.

- [ ] **Step 4: Smoke test CRM in browser**

- [ ] Open Sources ROI tab — table renders
- [ ] Open a lead, add deal value, save — persists on reload
- [ ] Open a lead, create a proposal — appears in list
- [ ] Open a lead marked "Lost", change rejection reason — dropdown has DB values
- [ ] Open Settings → Rejection Reasons — add/delete works
- [ ] Open Pipeline/Kanban — revenue totals appear on columns with deal values

---

## Self-Review

**Spec coverage:**
- ✅ `deal_value`/`deal_currency` on leads (Task 1, 3)
- ✅ `proposals` table with create/track/expire (Tasks 1, 2, 4)
- ✅ `rejection_reasons` table + DB-driven dropdown (Tasks 1, 5)
- ✅ `ad_campaigns` table foundation (Task 1)
- ✅ Bot proposal expiry job with 3-day warning (Task 2)
- ✅ Create Proposal form in LeadPanel (Task 4)
- ✅ Proposal history with accept/reject (Task 4)
- ✅ Settings: manage rejection reasons (Task 5)
- ✅ Kanban revenue totals per column (Task 6)
- ✅ Sources ROI page (Task 7)
- ✅ "Why we lose" bar chart (Task 8)

**Placeholder scan:** No TBDs, no stubs, all code is complete.

**Type consistency:**
- `fmtRevenue(val, currency)` used consistently in Tasks 6, 7
- `proposals` table columns (id, telegram_id, title, amount, currency, valid_until, status, created_by, created_at, updated_at) match between migration SQL and JS inserts/reads
- `rejection_reasons` table (id, label, sort_order) consistent between migration and RejectionReasonsManager
