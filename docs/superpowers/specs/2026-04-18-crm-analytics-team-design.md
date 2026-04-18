# CRM Analytics & Team Performance — Design Spec
**Date:** 2026-04-18  
**Status:** Approved

---

## Overview

Extend the existing CRM dashboard (`crm/index.html`) with four new capabilities:

1. **Deal cycle time** — avg days from lead created to conversion
2. **Repeat purchases** — % clients who re-purchased + re-engaged lost leads
3. **Period comparison toggle** — this period vs last month / same period last year
4. **AI campaign analytics** — cross-channel narrative + recommendations
5. **Team performance tab** — per-member weekly metrics + tasks system

**Approach:** Supabase SQL views for aggregations + lightweight frontend. AI analytics via existing `crm/api/ask.js`. One new SQL migration (`014_analytics_team.sql`).

---

## Architecture

### New SQL migration: `database/migrations/014_analytics_team.sql`

Creates:
- `tasks` table
- `v_deal_cycle` view
- `v_repeat_clients` view
- `v_team_metrics` view

### Modified files:
- `crm/index.html` — MetricsDashboard additions + new TeamTab component + sidebar nav entry

---

## Section 1: Database Schema

### `tasks` table

```sql
CREATE TABLE tasks (
  id          BIGSERIAL PRIMARY KEY,
  telegram_id BIGINT REFERENCES leads(telegram_id) ON DELETE SET NULL,
  title       TEXT NOT NULL,
  description TEXT,
  assigned_to TEXT,                          -- matches team_members.name
  due_date    DATE,
  status      TEXT DEFAULT 'open'            -- 'open' | 'done'
              CHECK (status IN ('open', 'done')),
  created_by  TEXT,
  created_at  TIMESTAMPTZ DEFAULT NOW(),
  updated_at  TIMESTAMPTZ DEFAULT NOW()
);
```

- "Overdue" is computed at query time: `due_date < CURRENT_DATE AND status = 'open'`
- RLS: anon key can read/insert/update/delete (same pattern as other tables)

---

### `v_deal_cycle` view

Computes average days from lead creation to first conversion, grouped by month.

```sql
CREATE VIEW v_deal_cycle AS
SELECT
  TO_CHAR(DATE_TRUNC('month', l.created_at), 'YYYY-MM') AS month,
  ROUND(AVG(
    EXTRACT(EPOCH FROM (sh.created_at - l.created_at)) / 86400
  )::numeric, 1) AS avg_days,
  COUNT(*) AS deal_count
FROM leads l
JOIN LATERAL (
  SELECT created_at FROM status_history
  WHERE telegram_id = l.telegram_id AND new_status = 'converted'
  ORDER BY created_at ASC LIMIT 1
) sh ON true
GROUP BY 1
ORDER BY 1 DESC;
```

---

### `v_repeat_clients` view

Two metrics:
- **Re-purchases**: clients with 2+ revenue events
- **Re-engaged**: leads with 2+ 'converted' entries in status_history (returned after lost)

```sql
CREATE VIEW v_repeat_clients AS
SELECT
  (SELECT COUNT(*) FROM (
    SELECT telegram_id FROM revenue_events
    GROUP BY telegram_id HAVING COUNT(*) >= 2
  ) x) AS repurchase_count,
  (SELECT COUNT(*) FROM (
    SELECT telegram_id FROM status_history
    WHERE new_status = 'converted'
    GROUP BY telegram_id HAVING COUNT(*) >= 2
  ) x) AS reengaged_count,
  (SELECT COUNT(*) FROM leads WHERE status = 'converted') AS total_converted;
```

---

### `v_team_metrics` view

Per-member weekly performance. Week = Mon 00:00 to Sun 23:59 in Asia/Tashkent.

```sql
CREATE VIEW v_team_metrics AS
WITH week_bounds AS (
  SELECT
    DATE_TRUNC('week', NOW() AT TIME ZONE 'Asia/Tashkent')::timestamptz AS week_start,
    (DATE_TRUNC('week', NOW() AT TIME ZONE 'Asia/Tashkent') + INTERVAL '6 days 23:59:59')::timestamptz AS week_end
),
advances AS (
  SELECT changed_by AS member, COUNT(*) AS deals_advanced
  FROM status_history, week_bounds
  WHERE created_at BETWEEN week_start AND week_end
    AND changed_by IS NOT NULL
  GROUP BY changed_by
),
created AS (
  -- Leads assigned to this member that entered the pipeline this week
  SELECT assigned_to AS member, COUNT(*) AS deals_created
  FROM leads, week_bounds
  WHERE created_at BETWEEN week_start AND week_end
    AND assigned_to IS NOT NULL
  GROUP BY assigned_to
),
task_stats AS (
  SELECT
    assigned_to AS member,
    COUNT(*) FILTER (WHERE status = 'done') AS tasks_done,
    COUNT(*) FILTER (WHERE status = 'open' AND due_date < CURRENT_DATE) AS tasks_overdue
  FROM tasks
  WHERE assigned_to IS NOT NULL
  GROUP BY assigned_to
),
contact_stats AS (
  SELECT
    assigned_to AS member,
    ROUND(AVG(
      EXTRACT(EPOCH FROM (NOW() - COALESCE(last_activity_at, created_at))) / 86400
    )::numeric, 1) AS avg_days_no_contact
  FROM leads
  WHERE status NOT IN ('converted', 'lost') AND assigned_to IS NOT NULL
  GROUP BY assigned_to
)
SELECT
  tm.name AS member,
  COALESCE(c.deals_created, 0)       AS deals_created,
  COALESCE(a.deals_advanced, 0)      AS deals_advanced,
  COALESCE(t.tasks_done, 0)          AS tasks_done,
  COALESCE(t.tasks_overdue, 0)       AS tasks_overdue,
  COALESCE(cs.avg_days_no_contact, 0) AS avg_days_no_contact
FROM team_members tm
LEFT JOIN advances a      ON a.member = tm.name
LEFT JOIN created c       ON c.member = tm.name
LEFT JOIN task_stats t    ON t.member = tm.name
LEFT JOIN contact_stats cs ON cs.member = tm.name;
```

---

## Section 2: MetricsDashboard Changes (`crm/index.html`)

### 2a. New KPI Cards

Add to the existing KPI cards row (after CAC):

| Card | Value | Source |
|---|---|---|
| Avg Deal Cycle | `X days` | `v_deal_cycle` filtered to selected period month |
| Repeat Clients | `X%` | `v_repeat_clients.repurchase_count / total_converted` |
| Re-engaged | `N leads` | `v_repeat_clients.reengaged_count` |

Trend arrow on "Avg Deal Cycle" compares to previous period's `v_deal_cycle` month entry.

### 2b. YoY Toggle

New `cmpMode` state: `'prev' | 'yoy'` (default: `'prev'`).

When `'yoy'`, the existing `prevRange` memo shifts `dateFrom`/`dateTo` back exactly 365 days instead of one period-length. All existing `trendFn()` calls automatically use the updated `prevRange` — zero other changes needed.

Renders as two small toggle buttons next to the date pickers:
```
[vs prev period]  [vs last year]
```

### 2c. AI Campaign Analysis Panel

Position: below the Sources ROI table.

**Data sent to `ask.js`:**
```json
{
  "channels": [
    { "key": "meta_general", "name": "Meta", "spend": 500, "leads": 42, "converted": 8, "cpl": 11.9, "cvr": 19 },
    ...
  ],
  "period": "2026-04"
}
```

**Prompt template** (built in JS, sent as `message` field to `ask.js`):
```
You are a marketing analyst. Given ad campaign data for [period], write:
1. A 2-3 sentence narrative comparing channel performance (CPL, CVR, ROI).
2. Exactly 3 actionable budget recommendations.
Respond as JSON: { "narrative": "...", "recommendations": ["...", "...", "..."] }
```

**UI:** Card with title "AI Campaign Analysis", paragraph for narrative, 3 bullet recommendations. "Refresh" button triggers re-fetch. Loading skeleton while fetching. Error state shows "Analysis unavailable" without crashing.

**Caching:** `useState` — cached per session. Re-fetches on date range change or manual refresh.

---

## Section 3: Team Tab (new)

### Sidebar

New nav item "Team" added after "Metrics", before "Settings". Icon: 👥 (or SVG people icon matching existing style).

### `TeamTab` component

Two sub-tabs rendered as small pill tabs at the top of the content area:

#### Sub-tab A: Performance

Fetches `v_team_metrics` (single query, no date params — always current week).

Table columns: Member | Deals Created | Advanced | Tasks Done | Tasks Overdue | Avg Days No Contact

- All columns sortable (click header)
- Overdue count shown in red if > 0
- Avg Days No Contact shown in amber if > 3, red if > 7

#### Sub-tab B: Leads Without Action

Query: `leads` where `last_activity_at < NOW() - INTERVAL '3 days'` AND `status NOT IN ('converted', 'lost')`.

Columns: Lead name | Assigned To | Status badge | Days idle (computed)

- Sorted by days idle descending (worst first)
- Clicking a row fires `onOpenLead(lead)` — reuses existing lead detail panel

#### Sub-tab C: Tasks

Fetches all tasks ordered by `due_date ASC`.

**List view:** task title, assignee, due date, linked lead name (if any), status badge (Open / Done / Overdue).

**Create task form** (inline at top): title (required), assignee dropdown (from `team_members`), due date, optional lead search, submit button.

**Actions:** Mark done (checkbox), delete (trash icon with confirm).

No bot notifications for tasks — CRM-only in this iteration.

---

## Data Flow Summary

```
MetricsDashboard load():
  Promise.all([
    ...existing queries...,
    supabase.from('v_deal_cycle').select('*'),        -- new
    supabase.from('v_repeat_clients').select('*'),    -- new (single row)
  ])
  → after render, if campaign data exists:
    fetch('/api/ask', { message: builtPrompt })       -- AI analysis

TeamTab load():
  Promise.all([
    supabase.from('v_team_metrics').select('*'),
    supabase.from('leads').select(...).lt('last_activity_at', threeDaysAgo).not('status', 'in', '(converted,lost)'),
    supabase.from('tasks').select('*, leads(name)').order('due_date'),
  ])
```

---

## Out of Scope

- Bot notifications when tasks are assigned
- Task comments/threads
- Historical team metrics (week-over-week trend for team)
- Mobile-responsive Team tab (CRM is desktop-only currently)
