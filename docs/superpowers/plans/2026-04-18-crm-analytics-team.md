# CRM Analytics & Team Performance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add deal cycle time, repeat purchase metrics, YoY period comparison, AI campaign analysis, and a Team performance tab (with tasks) to the existing CRM dashboard.

**Architecture:** One SQL migration adds a `tasks` table and three analytics views (`v_deal_cycle`, `v_repeat_clients`, `v_team_metrics`). All frontend changes are in the single `crm/index.html` file — MetricsDashboard gets new KPI cards, a YoY toggle, and an AI panel; a new `TeamTab` component gets wired into the sidebar.

**Tech Stack:** React 18 (UMD/CDN), Supabase JS v2, Recharts 2.12, Babel standalone, Vercel serverless (`crm/api/ask.js` proxies to OpenAI gpt-4o-mini).

> **Note on testing:** The CRM has no JS test framework — it's a single HTML file with UMD React. Every task ends with a **manual verification** step in the browser instead of automated tests.

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `database/migrations/014_analytics_team.sql` | **Create** | `tasks` table + 3 analytics views + RLS |
| `crm/index.html` | **Modify** | All frontend changes (state, load, KPIs, TeamTab, sidebar) |

---

## Task 1: SQL Migration — tasks table + analytics views

**Files:**
- Create: `database/migrations/014_analytics_team.sql`

- [ ] **Step 1: Create the migration file**

```sql
-- Migration 014: Analytics views + Tasks table
-- Run in Supabase SQL Editor

-- ── 1. TASKS TABLE ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS tasks (
  id          BIGSERIAL PRIMARY KEY,
  telegram_id BIGINT REFERENCES leads(telegram_id) ON DELETE SET NULL,
  title       TEXT NOT NULL,
  description TEXT,
  assigned_to TEXT,
  due_date    DATE,
  status      TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'done')),
  created_by  TEXT,
  created_at  TIMESTAMPTZ DEFAULT NOW(),
  updated_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_tasks_assigned ON tasks(assigned_to);
CREATE INDEX IF NOT EXISTS idx_tasks_status   ON tasks(status);

ALTER TABLE tasks ENABLE ROW LEVEL SECURITY;
CREATE POLICY "anon can read tasks"   ON tasks FOR SELECT USING (true);
CREATE POLICY "anon can insert tasks" ON tasks FOR INSERT WITH CHECK (true);
CREATE POLICY "anon can update tasks" ON tasks FOR UPDATE USING (true);
CREATE POLICY "anon can delete tasks" ON tasks FOR DELETE USING (true);

-- ── 2. v_deal_cycle VIEW ────────────────────────────────────────
-- Avg days from lead creation to first conversion, grouped by month
CREATE OR REPLACE VIEW v_deal_cycle AS
SELECT
  TO_CHAR(DATE_TRUNC('month', l.created_at AT TIME ZONE 'Asia/Tashkent'), 'YYYY-MM') AS month,
  ROUND(AVG(
    EXTRACT(EPOCH FROM (sh.created_at - l.created_at)) / 86400
  )::numeric, 1) AS avg_days,
  COUNT(*) AS deal_count
FROM leads l
JOIN LATERAL (
  SELECT created_at
  FROM status_history
  WHERE telegram_id = l.telegram_id
    AND new_status = 'converted'
  ORDER BY created_at ASC
  LIMIT 1
) sh ON true
GROUP BY 1
ORDER BY 1 DESC;

-- ── 3. v_repeat_clients VIEW ────────────────────────────────────
-- Two counts: clients with 2+ revenue events (re-purchases)
-- and leads converted 2+ times (re-engaged after lost)
CREATE OR REPLACE VIEW v_repeat_clients AS
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

-- ── 4. v_team_metrics VIEW ─────────────────────────────────────
-- Per-member performance for the current week (Mon–Sun, Asia/Tashkent)
CREATE OR REPLACE VIEW v_team_metrics AS
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
  SELECT assigned_to AS member, COUNT(*) AS deals_created
  FROM leads, week_bounds
  WHERE created_at BETWEEN week_start AND week_end
    AND assigned_to IS NOT NULL
  GROUP BY assigned_to
),
task_stats AS (
  SELECT
    assigned_to AS member,
    COUNT(*) FILTER (WHERE status = 'done')                              AS tasks_done,
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
  WHERE status NOT IN ('converted', 'lost')
    AND assigned_to IS NOT NULL
  GROUP BY assigned_to
)
SELECT
  tm.name                              AS member,
  COALESCE(c.deals_created, 0)        AS deals_created,
  COALESCE(a.deals_advanced, 0)       AS deals_advanced,
  COALESCE(t.tasks_done, 0)           AS tasks_done,
  COALESCE(t.tasks_overdue, 0)        AS tasks_overdue,
  COALESCE(cs.avg_days_no_contact, 0) AS avg_days_no_contact
FROM team_members tm
LEFT JOIN advances    a  ON a.member  = tm.name
LEFT JOIN created     c  ON c.member  = tm.name
LEFT JOIN task_stats  t  ON t.member  = tm.name
LEFT JOIN contact_stats cs ON cs.member = tm.name;
```

- [ ] **Step 2: Run the migration in Supabase**

Go to Supabase dashboard → SQL Editor → paste and run the file above.

Expected: no errors. Tables and views created.

- [ ] **Step 3: Verify**

Run in SQL Editor:
```sql
SELECT * FROM tasks LIMIT 1;           -- should return 0 rows, no error
SELECT * FROM v_deal_cycle LIMIT 3;    -- should return rows (or 0 if no converted leads yet)
SELECT * FROM v_repeat_clients;         -- should return 1 row with numeric columns
SELECT * FROM v_team_metrics;           -- should return 1 row per team member
```

- [ ] **Step 4: Commit**

```bash
git add database/migrations/014_analytics_team.sql
git commit -m "feat: add tasks table and analytics views for deal cycle, repeat clients, team metrics"
```

---

## Task 2: MetricsDashboard — state, prevRange YoY, and extended load()

**Files:**
- Modify: `crm/index.html` (lines ~3881–3976)

- [ ] **Step 1: Add new state variables**

In `MetricsDashboard`, after the existing state declarations (around line 3902, after `opCosts` useState), add:

```jsx
const [cmpMode, setCmpMode] = useState('prev');   // 'prev' | 'yoy'
const [dealCycle, setDealCycle] = useState(null); // { avg_days, deal_count } for current period month
const [repeatClients, setRepeatClients] = useState(null); // { repurchase_count, reengaged_count, total_converted }
const [aiAnalysis, setAiAnalysis] = useState(null);       // { narrative, recommendations }
const [aiLoading, setAiLoading] = useState(false);
```

- [ ] **Step 2: Update prevRange memo to support YoY**

Replace the existing `prevRange` useMemo (lines ~3906–3913):

```jsx
const prevRange = useMemo(() => {
  const from = new Date(dateFrom);
  const to = new Date(dateTo);
  if (cmpMode === 'yoy') {
    const yoyFrom = new Date(from); yoyFrom.setFullYear(yoyFrom.getFullYear() - 1);
    const yoyTo = new Date(to); yoyTo.setFullYear(yoyTo.getFullYear() - 1);
    return { from: yoyFrom.toISOString().split('T')[0], to: yoyTo.toISOString().split('T')[0] };
  }
  const span = to - from;
  const prevTo = new Date(from.getTime() - 86400000);
  const prevFrom = new Date(prevTo.getTime() - span);
  return { from: prevFrom.toISOString().split('T')[0], to: prevTo.toISOString().split('T')[0] };
}, [dateFrom, dateTo, cmpMode]);
```

- [ ] **Step 3: Extend load() Promise.all**

In the `load()` function, find the `Promise.all([...])` call (line ~3939). It currently destructures 12 results. Extend it by appending 2 more queries and update the destructuring:

Change the destructuring line from:
```jsx
const [lRes, plRes, cRes, eRes, aRes, mcRes, mRes, evRes, shRes, clRes, revRes, prevRevRes] = await Promise.all([
```
To:
```jsx
const [lRes, plRes, cRes, eRes, aRes, mcRes, mRes, evRes, shRes, clRes, revRes, prevRevRes, dcRes, rcRes] = await Promise.all([
```

And after the last existing query (`supabase.from('revenue_events').select(...).lte(...)`), append:
```jsx
supabase.from('v_deal_cycle').select('*'),
supabase.from('v_repeat_clients').select('*').single(),
```

Then after `setPrevRevEvents(...)` (still inside the try block), add:
```jsx
const dcRow = (dcRes.data || []).find(r => r.month === adPeriod);
setDealCycle(dcRow || null);
setRepeatClients(rcRes.data || null);
```

- [ ] **Step 4: Manual verification**

Open the CRM → Metrics tab → open browser console. Confirm no errors and `dealCycle`/`repeatClients` are populated:
```js
// Should log an object with avg_days and deal_count, or null
// Should log an object with repurchase_count, reengaged_count, total_converted
```
(Temporarily add `console.log` to confirm, then remove.)

- [ ] **Step 5: Commit**

```bash
git add crm/index.html
git commit -m "feat: add dealCycle, repeatClients state and YoY prevRange to MetricsDashboard"
```

---

## Task 3: MetricsDashboard — Client Retention KPI section

**Files:**
- Modify: `crm/index.html` (lines ~4165–4192, kpiSections array)

- [ ] **Step 1: Add new KPI section to kpiSections**

Find `const kpiSections = [` (line ~4165). After the closing `]` of the last existing section (`Ad Efficiency`), before the closing `];`, append:

```jsx
{ title: 'Client Retention', icon: '\uD83D\uDD01', color: '#7C3AED', items: [
  {
    label: 'Avg Deal Cycle',
    value: dealCycle ? `${dealCycle.avg_days}d` : '\u2014',
    sub: dealCycle ? `${dealCycle.deal_count} deals` : 'no conversions yet',
    trend: null,
    help: 'Average days from lead created to first conversion this month.',
  },
  {
    label: 'Repeat Clients',
    value: repeatClients && repeatClients.total_converted > 0
      ? `${((repeatClients.repurchase_count / repeatClients.total_converted) * 100).toFixed(1)}%`
      : '\u2014',
    sub: repeatClients ? `${repeatClients.repurchase_count} re-purchases` : null,
    trend: null,
    help: 'Clients with 2+ revenue events as a % of all converted leads.',
  },
  {
    label: 'Re-engaged Leads',
    value: repeatClients ? String(repeatClients.reengaged_count) : '\u2014',
    sub: 'converted 2+ times',
    trend: null,
    help: 'Leads who were converted, lost, then converted again.',
  },
]},
```

- [ ] **Step 2: Manual verification**

Open CRM → Metrics tab. Scroll to the bottom of KPI cards. Confirm a new "Client Retention" section with 3 cards appears. If no conversions exist, all cards show "—".

- [ ] **Step 3: Commit**

```bash
git add crm/index.html
git commit -m "feat: add Client Retention KPI section (deal cycle, repeat clients, re-engaged)"
```

---

## Task 4: MetricsDashboard — YoY comparison toggle buttons

**Files:**
- Modify: `crm/index.html` (lines ~4294–4299, date picker area)

- [ ] **Step 1: Add toggle buttons after the date inputs**

Find the closing `</div>` of the date range row (line ~4299, after the `dateTo` input). Before that closing `</div>`, insert:

```jsx
<div style={{ display: 'flex', gap: 4, marginLeft: 8 }}>
  {[['vs prev', 'prev'], ['vs last year', 'yoy']].map(([lbl, mode]) => (
    <button key={mode} onClick={() => setCmpMode(mode)}
      style={{
        padding: '4px 10px', fontSize: 11.5, fontWeight: 600,
        borderRadius: 'var(--r)', cursor: 'pointer',
        background: cmpMode === mode ? 'var(--primary)' : 'var(--surface)',
        color: cmpMode === mode ? '#fff' : 'var(--text-2)',
        border: `1px solid ${cmpMode === mode ? 'var(--primary)' : 'var(--border)'}`,
      }}>
      {lbl}
    </button>
  ))}
</div>
```

- [ ] **Step 2: Manual verification**

Open CRM → Metrics tab. Confirm two small toggle buttons appear to the right of the date inputs: "vs prev" and "vs last year". Click "vs last year" — trend arrows on KPI cards should recalculate against the same period 1 year ago (visible change if you have historical data). Click "vs prev" — returns to default. Active button is highlighted in primary color.

- [ ] **Step 3: Commit**

```bash
git add crm/index.html
git commit -m "feat: add YoY comparison toggle to MetricsDashboard"
```

---

## Task 5: MetricsDashboard — AI Campaign Analysis panel

**Files:**
- Modify: `crm/index.html` (after Sources ROI table, before Activity Heatmap, ~line 4471)

- [ ] **Step 1: Add fetchAiAnalysis function**

In `MetricsDashboard`, after the `load` function definition and before `useEffect(() => { load(); }, [load])`, add:

```jsx
const fetchAiAnalysis = useCallback(async (channelRows) => {
  if (!channelRows || channelRows.length === 0) return;
  setAiLoading(true);
  setAiAnalysis(null);
  try {
    const channels = channelRows.map(r => ({
      key: r.src,
      spend: r.spend,
      leads: r.leads,
      converted: r.converted,
      cpl: r.cpl,
      cvr: r.leads > 0 ? parseFloat((r.converted / r.leads * 100).toFixed(1)) : 0,
      roas: r.roas,
    }));
    const body = {
      model: 'gpt-4o-mini',
      messages: [
        {
          role: 'system',
          content: 'You are a marketing analyst. Respond ONLY with valid JSON in the exact format requested.',
        },
        {
          role: 'user',
          content: `Analyze these ad campaigns for period ${adPeriod}:\n${JSON.stringify(channels, null, 2)}\n\nRespond with JSON: { "narrative": "2-3 sentence cross-channel summary comparing CPL, CVR, ROAS", "recommendations": ["action 1", "action 2", "action 3"] }`,
        },
      ],
      response_format: { type: 'json_object' },
    };
    const res = await fetch('/api/ask', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    const data = await res.json();
    const parsed = JSON.parse(data.choices[0].message.content);
    setAiAnalysis(parsed);
  } catch {
    setAiAnalysis({ narrative: 'Analysis unavailable.', recommendations: [] });
  } finally {
    setAiLoading(false);
  }
}, [adPeriod]);
```

- [ ] **Step 2: Trigger AI analysis after load**

Replace `useEffect(() => { load(); }, [load]);` with:

```jsx
useEffect(() => { load(); setAiAnalysis(null); }, [load]);
```

- [ ] **Step 3: Add AI panel JSX after the Sources ROI table closing div**

Find the closing `</div>` of the Sources ROI card (the one containing the table and summary footer, ~line 4471). After it (before `{/* Activity Heatmap */}`), insert:

```jsx
{/* AI Campaign Analysis */}
<div className="card" style={{ marginBottom: 20 }}>
  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 }}>
    <h3 style={{ margin: 0 }}>AI Campaign Analysis</h3>
    <button className="btn" onClick={() => fetchAiAnalysis(rows)}
      disabled={aiLoading || rows.length === 0}
      style={{ fontSize: 12.5, padding: '4px 12px' }}>
      {aiLoading ? 'Analyzing…' : 'Refresh Analysis'}
    </button>
  </div>
  {rows.length === 0 ? (
    <p style={{ color: 'var(--text-3)', fontSize: 13, margin: 0 }}>No campaign data for this period.</p>
  ) : aiLoading ? (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      {[120, 80, 60].map(w => (
        <div key={w} style={{ height: 14, width: `${w}%`, maxWidth: w * 8, background: 'var(--surface-alt)', borderRadius: 6, animation: 'pulse 1.5s infinite' }} />
      ))}
    </div>
  ) : aiAnalysis ? (
    <div>
      <p style={{ fontSize: 13.5, color: 'var(--text)', lineHeight: 1.6, marginBottom: 12 }}>{aiAnalysis.narrative}</p>
      {aiAnalysis.recommendations && aiAnalysis.recommendations.length > 0 && (
        <ul style={{ paddingLeft: 20, margin: 0 }}>
          {aiAnalysis.recommendations.map((r, i) => (
            <li key={i} style={{ fontSize: 13, color: 'var(--text-2)', marginBottom: 6 }}>{r}</li>
          ))}
        </ul>
      )}
    </div>
  ) : (
    <p style={{ fontSize: 13, color: 'var(--text-3)', margin: 0 }}>
      Click "Refresh Analysis" to generate AI insights for this period's campaigns.
    </p>
  )}
</div>
```

- [ ] **Step 4: Add pulse animation CSS**

In the `<style>` block (near the top of the HTML file), add:

```css
@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}
```

- [ ] **Step 5: Manual verification**

Open CRM → Metrics tab → scroll past Sources ROI table. Confirm "AI Campaign Analysis" card appears. Click "Refresh Analysis". Confirm loading skeleton appears, then narrative paragraph + 3 bullet recommendations appear. If no campaigns exist, confirm "No campaign data for this period." message shows.

- [ ] **Step 6: Commit**

```bash
git add crm/index.html
git commit -m "feat: add AI campaign analysis panel to MetricsDashboard"
```

---

## Task 6: TeamTab — scaffold component, sidebar nav, and routing

**Files:**
- Modify: `crm/index.html` (before `App` component ~line 4897, sidebar ~line 4987, routing ~line 5025)

- [ ] **Step 1: Add TeamTab skeleton before the App component**

Find `function App() {` (line ~4897). Immediately before it, insert the full `TeamTab` component scaffold:

```jsx
function TeamTab({ showToast, onOpenLead }) {
  const [subTab, setSubTab] = useState('performance');
  const [teamMetrics, setTeamMetrics] = useState([]);
  const [idleLeads, setIdleLeads] = useState([]);
  const [tasks, setTasks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [teamMembers, setTeamMembers] = useState([]);
  const [sortCol, setSortCol] = useState('deals_advanced');
  const [sortDir, setSortDir] = useState('desc');
  // Task form state
  const [taskTitle, setTaskTitle] = useState('');
  const [taskAssignee, setTaskAssignee] = useState('');
  const [taskDue, setTaskDue] = useState('');
  const [taskLead, setTaskLead] = useState('');
  const [taskSaving, setTaskSaving] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const threeDaysAgo = new Date(Date.now() - 3 * 86400000).toISOString();
      const [tmRes, metricsRes, idleRes, tasksRes] = await Promise.all([
        supabase.from('team_members').select('*').order('name'),
        supabase.from('v_team_metrics').select('*'),
        supabase.from('leads').select('telegram_id, name, username, assigned_to, status, last_activity_at, created_at')
          .lt('last_activity_at', threeDaysAgo)
          .not('status', 'in', '(converted,lost)')
          .order('last_activity_at', { ascending: true }),
        supabase.from('tasks').select('*, leads(name)').order('due_date', { ascending: true }),
      ]);
      setTeamMembers(tmRes.data || []);
      setTeamMetrics(metricsRes.data || []);
      setIdleLeads(idleRes.data || []);
      setTasks(tasksRes.data || []);
    } catch (e) {
      showToast('Failed to load team data: ' + e.message, 'error');
    } finally {
      setLoading(false);
    }
  }, [showToast]);

  useEffect(() => { load(); }, [load]);

  const SubTabBtn = ({ id, label }) => (
    <button onClick={() => setSubTab(id)} style={{
      padding: '6px 16px', fontSize: 13, fontWeight: 600, borderRadius: 20,
      border: '1px solid var(--border)', cursor: 'pointer',
      background: subTab === id ? 'var(--primary)' : 'var(--surface)',
      color: subTab === id ? '#fff' : 'var(--text-2)',
    }}>{label}</button>
  );

  return (
    <div style={{ maxWidth: 1100 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
        <h2 style={{ fontSize: 18, fontWeight: 700, margin: 0 }}>Team Performance</h2>
        <button className="btn" onClick={load} style={{ fontSize: 12.5 }}>Refresh</button>
      </div>
      <div style={{ display: 'flex', gap: 8, marginBottom: 20 }}>
        <SubTabBtn id="performance" label="Performance" />
        <SubTabBtn id="idle" label={`Idle Leads (${idleLeads.length})`} />
        <SubTabBtn id="tasks" label={`Tasks (${tasks.filter(t => t.status === 'open').length} open)`} />
      </div>
      {loading ? (
        <div style={{ textAlign: 'center', padding: 40, color: 'var(--text-3)' }}>Loading…</div>
      ) : (
        <>
          {subTab === 'performance' && <TeamPerformanceTab metrics={teamMetrics} sortCol={sortCol} sortDir={sortDir} setSortCol={setSortCol} setSortDir={setSortDir} />}
          {subTab === 'idle' && <TeamIdleLeadsTab leads={idleLeads} onOpenLead={onOpenLead} />}
          {subTab === 'tasks' && <TeamTasksTab tasks={tasks} teamMembers={teamMembers} taskTitle={taskTitle} setTaskTitle={setTaskTitle} taskAssignee={taskAssignee} setTaskAssignee={setTaskAssignee} taskDue={taskDue} setTaskDue={setTaskDue} taskLead={taskLead} setTaskLead={setTaskLead} taskSaving={taskSaving} setTaskSaving={setTaskSaving} showToast={showToast} reload={load} />}
        </>
      )}
    </div>
  );
}

function TeamPerformanceTab({ metrics, sortCol, sortDir, setSortCol, setSortDir }) {
  const sorted = [...metrics].sort((a, b) => {
    const av = a[sortCol] ?? 0;
    const bv = b[sortCol] ?? 0;
    return sortDir === 'asc' ? av - bv : bv - av;
  });
  const Th = ({ col, children }) => (
    <th onClick={() => { if (sortCol === col) setSortDir(d => d === 'asc' ? 'desc' : 'asc'); else { setSortCol(col); setSortDir('desc'); } }}
      style={{ cursor: 'pointer', userSelect: 'none', padding: '10px 12px', textAlign: 'right', background: 'var(--surface-alt)', fontWeight: 700, fontSize: 12, color: 'var(--text-2)', whiteSpace: 'nowrap' }}>
      {children} {sortCol === col ? (sortDir === 'desc' ? '▾' : '▴') : ''}
    </th>
  );
  if (metrics.length === 0) return <p style={{ color: 'var(--text-3)', fontSize: 13 }}>No team members yet. Add them in Settings.</p>;
  return (
    <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13.5 }}>
        <thead>
          <tr>
            <th style={{ padding: '10px 12px', textAlign: 'left', background: 'var(--surface-alt)', fontWeight: 700, fontSize: 12, color: 'var(--text-2)' }}>Member</th>
            <Th col="deals_created">Deals Created</Th>
            <Th col="deals_advanced">Advanced</Th>
            <Th col="tasks_done">Tasks Done</Th>
            <Th col="tasks_overdue">Overdue</Th>
            <Th col="avg_days_no_contact">Avg Days No Contact</Th>
          </tr>
        </thead>
        <tbody>
          {sorted.map(m => (
            <tr key={m.member} style={{ borderTop: '1px solid var(--border)' }}>
              <td style={{ padding: '10px 12px', fontWeight: 600 }}>{m.member}</td>
              <td style={{ padding: '10px 12px', textAlign: 'right' }}>{m.deals_created}</td>
              <td style={{ padding: '10px 12px', textAlign: 'right' }}>{m.deals_advanced}</td>
              <td style={{ padding: '10px 12px', textAlign: 'right', color: '#16A34A' }}>{m.tasks_done}</td>
              <td style={{ padding: '10px 12px', textAlign: 'right', color: m.tasks_overdue > 0 ? '#DC2626' : 'var(--text-3)' }}>{m.tasks_overdue}</td>
              <td style={{ padding: '10px 12px', textAlign: 'right', color: m.avg_days_no_contact > 7 ? '#DC2626' : m.avg_days_no_contact > 3 ? '#CA8A04' : 'var(--text)' }}>
                {m.avg_days_no_contact}d
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function TeamIdleLeadsTab({ leads, onOpenLead }) {
  if (leads.length === 0) return <p style={{ color: 'var(--text-3)', fontSize: 13 }}>No leads have been idle for more than 3 days.</p>;
  return (
    <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13.5 }}>
        <thead>
          <tr style={{ background: 'var(--surface-alt)' }}>
            <th style={{ padding: '10px 12px', textAlign: 'left', fontWeight: 700, fontSize: 12, color: 'var(--text-2)' }}>Lead</th>
            <th style={{ padding: '10px 12px', textAlign: 'left', fontWeight: 700, fontSize: 12, color: 'var(--text-2)' }}>Assigned To</th>
            <th style={{ padding: '10px 12px', textAlign: 'left', fontWeight: 700, fontSize: 12, color: 'var(--text-2)' }}>Status</th>
            <th style={{ padding: '10px 12px', textAlign: 'right', fontWeight: 700, fontSize: 12, color: 'var(--text-2)' }}>Days Idle</th>
          </tr>
        </thead>
        <tbody>
          {leads.map(l => {
            const lastActivity = l.last_activity_at || l.created_at;
            const daysIdle = Math.floor((Date.now() - new Date(lastActivity).getTime()) / 86400000);
            return (
              <tr key={l.telegram_id} onClick={() => onOpenLead(l)} style={{ borderTop: '1px solid var(--border)', cursor: 'pointer' }}
                onMouseEnter={e => e.currentTarget.style.background = 'var(--surface-alt)'}
                onMouseLeave={e => e.currentTarget.style.background = ''}>
                <td style={{ padding: '10px 12px', fontWeight: 500 }}>{l.name || l.username || `#${l.telegram_id}`}</td>
                <td style={{ padding: '10px 12px', color: 'var(--text-2)' }}>{l.assigned_to || '—'}</td>
                <td style={{ padding: '10px 12px' }}>
                  <span className="status-badge" style={{ background: STATUS_COLORS[l.status] || '#94a3b8' }}>{STATUS_LABELS[l.status] || l.status}</span>
                </td>
                <td style={{ padding: '10px 12px', textAlign: 'right', fontWeight: 700, color: daysIdle > 7 ? '#DC2626' : '#CA8A04' }}>{daysIdle}d</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function TeamTasksTab({ tasks, teamMembers, taskTitle, setTaskTitle, taskAssignee, setTaskAssignee, taskDue, setTaskDue, taskLead, setTaskLead, taskSaving, setTaskSaving, showToast, reload }) {
  const createTask = async () => {
    if (!taskTitle.trim()) { showToast('Title is required', 'error'); return; }
    setTaskSaving(true);
    try {
      const payload = {
        title: taskTitle.trim(),
        assigned_to: taskAssignee || null,
        due_date: taskDue || null,
        status: 'open',
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      };
      const { error } = await supabase.from('tasks').insert(payload);
      if (error) throw error;
      setTaskTitle(''); setTaskAssignee(''); setTaskDue(''); setTaskLead('');
      showToast('Task created', 'success');
      reload();
    } catch (e) {
      showToast('Error: ' + e.message, 'error');
    } finally {
      setTaskSaving(false);
    }
  };

  const markDone = async (id) => {
    await supabase.from('tasks').update({ status: 'done', updated_at: new Date().toISOString() }).eq('id', id);
    reload();
  };

  const deleteTask = async (id) => {
    if (!confirm('Delete this task?')) return;
    await supabase.from('tasks').delete().eq('id', id);
    reload();
  };

  const getTaskStatus = (t) => {
    if (t.status === 'done') return { label: 'Done', color: '#16A34A' };
    if (t.due_date && new Date(t.due_date) < new Date()) return { label: 'Overdue', color: '#DC2626' };
    return { label: 'Open', color: '#CA8A04' };
  };

  return (
    <div>
      {/* Create task form */}
      <div className="card" style={{ marginBottom: 16 }}>
        <h4 style={{ margin: '0 0 12px', fontSize: 13, fontWeight: 700, color: 'var(--text-2)' }}>New Task</h4>
        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'flex-end' }}>
          <div style={{ flex: '1 1 200px' }}>
            <label style={{ display: 'block', fontSize: 11, fontWeight: 600, color: 'var(--text-3)', marginBottom: 4, textTransform: 'uppercase' }}>Title *</label>
            <input value={taskTitle} onChange={e => setTaskTitle(e.target.value)} placeholder="Task title"
              style={{ width: '100%', padding: '8px 10px', border: '1px solid var(--border)', borderRadius: 'var(--r)', fontSize: 13, fontFamily: 'inherit', outline: 'none', boxSizing: 'border-box' }} />
          </div>
          <div style={{ flex: '0 1 160px' }}>
            <label style={{ display: 'block', fontSize: 11, fontWeight: 600, color: 'var(--text-3)', marginBottom: 4, textTransform: 'uppercase' }}>Assignee</label>
            <select value={taskAssignee} onChange={e => setTaskAssignee(e.target.value)}
              style={{ width: '100%', padding: '8px 10px', border: '1px solid var(--border)', borderRadius: 'var(--r)', fontSize: 13, fontFamily: 'inherit', outline: 'none', background: 'var(--surface)', boxSizing: 'border-box' }}>
              <option value="">Unassigned</option>
              {teamMembers.map(m => <option key={m.id} value={m.name}>{m.name}</option>)}
            </select>
          </div>
          <div style={{ flex: '0 1 140px' }}>
            <label style={{ display: 'block', fontSize: 11, fontWeight: 600, color: 'var(--text-3)', marginBottom: 4, textTransform: 'uppercase' }}>Due Date</label>
            <input type="date" value={taskDue} onChange={e => setTaskDue(e.target.value)}
              style={{ width: '100%', padding: '8px 10px', border: '1px solid var(--border)', borderRadius: 'var(--r)', fontSize: 13, fontFamily: 'inherit', outline: 'none', boxSizing: 'border-box' }} />
          </div>
          <button className="btn btn-primary" onClick={createTask} disabled={taskSaving}
            style={{ padding: '8px 20px', alignSelf: 'flex-end' }}>
            {taskSaving ? 'Saving…' : 'Add Task'}
          </button>
        </div>
      </div>

      {/* Task list */}
      {tasks.length === 0 ? (
        <p style={{ color: 'var(--text-3)', fontSize: 13 }}>No tasks yet. Create one above.</p>
      ) : (
        <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13.5 }}>
            <thead>
              <tr style={{ background: 'var(--surface-alt)' }}>
                <th style={{ padding: '10px 12px', textAlign: 'left', fontWeight: 700, fontSize: 12, color: 'var(--text-2)', width: 32 }}></th>
                <th style={{ padding: '10px 12px', textAlign: 'left', fontWeight: 700, fontSize: 12, color: 'var(--text-2)' }}>Task</th>
                <th style={{ padding: '10px 12px', textAlign: 'left', fontWeight: 700, fontSize: 12, color: 'var(--text-2)' }}>Assignee</th>
                <th style={{ padding: '10px 12px', textAlign: 'left', fontWeight: 700, fontSize: 12, color: 'var(--text-2)' }}>Due</th>
                <th style={{ padding: '10px 12px', textAlign: 'left', fontWeight: 700, fontSize: 12, color: 'var(--text-2)' }}>Status</th>
                <th style={{ width: 40 }}></th>
              </tr>
            </thead>
            <tbody>
              {tasks.map(t => {
                const st = getTaskStatus(t);
                return (
                  <tr key={t.id} style={{ borderTop: '1px solid var(--border)', opacity: t.status === 'done' ? 0.5 : 1 }}>
                    <td style={{ padding: '10px 12px' }}>
                      <input type="checkbox" checked={t.status === 'done'} onChange={() => t.status === 'open' && markDone(t.id)}
                        style={{ cursor: t.status === 'open' ? 'pointer' : 'default' }} />
                    </td>
                    <td style={{ padding: '10px 12px', fontWeight: 500, textDecoration: t.status === 'done' ? 'line-through' : 'none' }}>
                      {t.title}
                      {t.leads && <span style={{ fontSize: 11, color: 'var(--text-3)', marginLeft: 8 }}>→ {t.leads.name}</span>}
                    </td>
                    <td style={{ padding: '10px 12px', color: 'var(--text-2)' }}>{t.assigned_to || '—'}</td>
                    <td style={{ padding: '10px 12px', color: 'var(--text-2)', fontSize: 12 }}>{t.due_date || '—'}</td>
                    <td style={{ padding: '10px 12px' }}>
                      <span style={{ fontSize: 11, fontWeight: 700, color: st.color }}>{st.label}</span>
                    </td>
                    <td style={{ padding: '10px 12px', textAlign: 'center' }}>
                      <button onClick={() => deleteTask(t.id)} title="Delete"
                        style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-3)', padding: 4 }}>
                        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                          <polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/>
                          <path d="M10 11v6"/><path d="M14 11v6"/><path d="M9 6V4h6v2"/>
                        </svg>
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Add Team nav item to the sidebar**

Find the Campaigns nav item (line ~4983):
```jsx
<a title="Campaigns" className={tab === 'campaigns' ? 'active' : ''} onClick={() => setTab('campaigns')}>
```
After the closing `</a>` of the Campaigns nav item (before the Settings nav item ~line 4987), insert:

```jsx
<a title="Team" className={tab === 'team' ? 'active' : ''} onClick={() => setTab('team')}>
  <svg className="nav-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/>
    <circle cx="9" cy="7" r="4"/>
    <path d="M23 21v-2a4 4 0 0 0-3-3.87"/>
    <path d="M16 3.13a4 4 0 0 1 0 7.75"/>
    <line x1="19" y1="8" x2="19" y2="14"/>
    <line x1="22" y1="11" x2="16" y2="11"/>
  </svg>
  {!sidebarCollapsed && <span>Team</span>}
</a>
```

- [ ] **Step 3: Wire TeamTab into tab routing**

Find `{tab === 'campaigns' && <CampaignsTab showToast={showToast} />}` (line ~5025). After it, insert:

```jsx
{tab === 'team' && <TeamTab showToast={showToast} onOpenLead={setSelectedLead} />}
```

- [ ] **Step 4: Manual verification**

Open CRM. Confirm "Team" nav item appears in sidebar between Campaigns and Settings. Click it — confirm the Team Performance tab loads with 3 sub-tabs: "Performance", "Idle Leads (N)", "Tasks (N open)". Performance table shows team members. Sub-tabs switch correctly.

- [ ] **Step 5: Commit**

```bash
git add crm/index.html
git commit -m "feat: add TeamTab with Performance, Idle Leads, and Tasks sub-tabs"
```

---

## Self-Review Checklist

- [x] **SQL coverage:** `tasks` table ✓, `v_deal_cycle` ✓, `v_repeat_clients` ✓, `v_team_metrics` ✓
- [x] **Deal cycle KPI:** Implemented in Task 3, data fetched in Task 2
- [x] **Repeat client KPI:** Implemented in Task 3, data fetched in Task 2
- [x] **YoY toggle:** Implemented in Task 4 — `cmpMode` state added in Task 2
- [x] **AI campaign analysis panel:** Implemented in Task 5 — `fetchAiAnalysis` added, panel JSX added after Sources ROI
- [x] **Team nav + routing:** Task 6
- [x] **Performance table:** Task 6 (`TeamPerformanceTab` component)
- [x] **Idle leads list:** Task 6 (`TeamIdleLeadsTab` component)
- [x] **Tasks sub-tab (list, create, mark done, delete):** Task 6 (`TeamTasksTab` component)
- [x] **`STATUS_COLORS` and `STATUS_LABELS`** used in `TeamIdleLeadsTab` — these are already defined at the top of the JS section (line ~1138), accessible as module-level constants
- [x] **`rows` variable used in Task 5 AI panel** — `rows` is defined in the same `MetricsDashboard` render scope (line ~4147), available to the JSX below
- [x] **Type consistency:** `getTaskStatus` defined inside `TeamTasksTab` and called within the same component — no cross-component name drift
