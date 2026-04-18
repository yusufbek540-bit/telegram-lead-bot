# CRM & Bot UI Refresh Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix scheduler job status reporting, clean up the Settings panel, make the activity timeline scrollable, add a collapsible sidebar with brand logo and colors to the CRM, and apply the brand palette to the TWA.

**Architecture:** All CRM changes are to the single-file `crm/index.html` (React + Babel in-browser, ~4980 lines). Bot changes are to `bot/services/scheduler_service.py` only — no service files touched. TWA changes are to `twa/index.html` only.

**Tech Stack:** Python/aiogram 3 + APScheduler (bot), React 18 + Babel standalone + Supabase JS v2 (CRM), vanilla HTML/CSS/JS (TWA).

---

## File Map

| File | Tasks |
|---|---|
| `bot/services/scheduler_service.py` | Task 1 |
| `crm/index.html` | Tasks 2, 3, 4, 5 (CRM logo), 6 |
| `twa/index.html` | Tasks 5 (TWA logo), 7 |

---

## Task 1: Scheduler Job Wrappers

**Files:**
- Modify: `bot/services/scheduler_service.py:191-255` (7 direct job registrations → wrapped)

### Context
Seven imported jobs (`check_followup_reminders`, `detect_stale_leads`, `check_proposal_expiry`, `run_auto_tagger`, `run_sentiment_analysis`, `check_scheduled_campaigns`, `run_chat_relay`) are registered directly in `create_scheduler()`. They never call `_record_job()`, so the CRM Bot Status panel shows them as "pending / never" forever. The fix is thin async wrapper functions that call the original then record status.

Additionally `run_chat_relay` fires every `seconds=5` — slow it to `seconds=30`.

No changes to any service file. Only `scheduler_service.py`.

- [ ] **Step 1: Add 7 wrapper functions** — insert them between the `heartbeat()` function (line 165) and the `create_scheduler()` function (line 170). Add this block:

```python
async def _wrap_check_followup_reminders(bot: Bot):
    try:
        await check_followup_reminders(bot)
        _record_job("check_followup_reminders")
    except Exception as e:
        logger.error(f"check_followup_reminders: {e}", exc_info=True)
        _record_job("check_followup_reminders", status="error", error=str(e)[:200])


async def _wrap_detect_stale_leads(bot: Bot):
    try:
        await detect_stale_leads(bot)
        _record_job("detect_stale_leads")
    except Exception as e:
        logger.error(f"detect_stale_leads: {e}", exc_info=True)
        _record_job("detect_stale_leads", status="error", error=str(e)[:200])


async def _wrap_check_proposal_expiry(bot: Bot):
    try:
        await check_proposal_expiry(bot)
        _record_job("check_proposal_expiry")
    except Exception as e:
        logger.error(f"check_proposal_expiry: {e}", exc_info=True)
        _record_job("check_proposal_expiry", status="error", error=str(e)[:200])


async def _wrap_run_auto_tagger(bot: Bot):
    try:
        await run_auto_tagger(bot)
        _record_job("run_auto_tagger")
    except Exception as e:
        logger.error(f"run_auto_tagger: {e}", exc_info=True)
        _record_job("run_auto_tagger", status="error", error=str(e)[:200])


async def _wrap_run_sentiment_analysis(bot: Bot):
    try:
        await run_sentiment_analysis(bot)
        _record_job("run_sentiment_analysis")
    except Exception as e:
        logger.error(f"run_sentiment_analysis: {e}", exc_info=True)
        _record_job("run_sentiment_analysis", status="error", error=str(e)[:200])


async def _wrap_check_scheduled_campaigns(bot: Bot):
    try:
        await check_scheduled_campaigns(bot)
        _record_job("check_scheduled_campaigns")
    except Exception as e:
        logger.error(f"check_scheduled_campaigns: {e}", exc_info=True)
        _record_job("check_scheduled_campaigns", status="error", error=str(e)[:200])


async def _wrap_run_chat_relay(bot: Bot):
    try:
        await run_chat_relay(bot)
        _record_job("run_chat_relay")
    except Exception as e:
        logger.error(f"run_chat_relay: {e}", exc_info=True)
        _record_job("run_chat_relay", status="error", error=str(e)[:200])
```

- [ ] **Step 2: Replace direct job registrations with wrappers** — in `create_scheduler()`, replace the 7 `scheduler.add_job(...)` calls that use the original imported functions with calls to the wrapper functions. Also change `run_chat_relay` interval from `seconds=5` to `seconds=30`.

Replace the block starting at line 191 (`scheduler.add_job(check_followup_reminders, ...`) through line 253 (`scheduler.add_job(run_chat_relay, ...`) with:

```python
    scheduler.add_job(
        _wrap_check_followup_reminders,
        trigger="interval",
        hours=config.JOB_INTERVALS["followup_check_hours"],
        args=[bot],
        id="check_followup_reminders",
        replace_existing=True,
    )

    scheduler.add_job(
        _wrap_detect_stale_leads,
        trigger="cron",
        hour=config.JOB_INTERVALS["stale_detection_hour"],
        minute=0,
        args=[bot],
        id="detect_stale_leads",
        replace_existing=True,
    )

    scheduler.add_job(
        _wrap_check_proposal_expiry,
        trigger="interval",
        hours=config.JOB_INTERVALS["proposal_expiry_hours"],
        args=[bot],
        id="check_proposal_expiry",
        replace_existing=True,
    )

    scheduler.add_job(
        _wrap_run_auto_tagger,
        trigger="interval",
        hours=config.JOB_INTERVALS.get("tagging_interval_hours", 1),
        args=[bot],
        id="run_auto_tagger",
        replace_existing=True,
    )

    scheduler.add_job(
        _wrap_run_sentiment_analysis,
        trigger="interval",
        hours=config.JOB_INTERVALS.get("sentiment_interval_hours", 2),
        args=[bot],
        id="run_sentiment_analysis",
        replace_existing=True,
    )

    scheduler.add_job(
        _wrap_check_scheduled_campaigns,
        trigger="interval",
        minutes=1,
        args=[bot],
        id="check_scheduled_campaigns",
        replace_existing=True,
    )

    scheduler.add_job(
        _wrap_run_chat_relay,
        trigger="interval",
        seconds=30,
        args=[bot],
        id="run_chat_relay",
        replace_existing=True,
    )
```

- [ ] **Step 3: Verify syntax**

```bash
cd /Users/yusufbek/Desktop/telegram-lead-bot
python3 -c "import bot.services.scheduler_service; print('OK')"
```

Expected: `OK` with no errors.

- [ ] **Step 4: Commit**

```bash
git add bot/services/scheduler_service.py
git commit -m "fix: wrap imported scheduler jobs to record status; slow chat_relay to 30s"
```

---

## Task 2: Remove Settings Refresh Button

**Files:**
- Modify: `crm/index.html:3399-3408` (loadSettings useCallback → inline fetchJobs)
- Modify: `crm/index.html:3545-3549` (card header — remove refresh button)

### Context
A `↻ Refresh` button was added to the Bot Status card (line 3548) that calls `loadSettings`, which was converted to `React.useCallback` (line 3399). The user did not request this button. The `useEffect` already auto-refreshes every 30 seconds. Revert both changes.

- [ ] **Step 1: Replace `loadSettings` useCallback + useEffect with a self-contained useEffect**

Replace lines 3399-3408:
```js
      const loadSettings = React.useCallback(async () => {
        const { data } = await supabase.from('job_status').select('*').order('job_id');
        if (data) setJobStatus(data);
      }, []);

      React.useEffect(() => {
        loadSettings();
        const interval = setInterval(loadSettings, 30000);
        return () => clearInterval(interval);
      }, [loadSettings]);
```

With:
```js
      React.useEffect(() => {
        const fetchJobs = async () => {
          const { data } = await supabase.from('job_status').select('*').order('job_id');
          if (data) setJobStatus(data);
        };
        fetchJobs();
        const interval = setInterval(fetchJobs, 30000);
        return () => clearInterval(interval);
      }, []);
```

- [ ] **Step 2: Remove refresh button from Bot Status card heading**

Replace lines 3545-3549:
```jsx
          <div className="card" style={{ marginBottom: 16 }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
              <h3 style={{ margin: 0 }}>Bot Status / Scheduler Jobs</h3>
              <button className="btn" style={{ fontSize: 12, padding: '4px 10px' }} onClick={loadSettings}>↻ Refresh</button>
            </div>
```

With:
```jsx
          <div className="card" style={{ marginBottom: 16 }}>
            <h3 style={{ marginBottom: 12 }}>Bot Status / Scheduler Jobs</h3>
```

- [ ] **Step 3: Verify in browser** — open `crm/index.html`, navigate to Settings. Confirm:
  - No Refresh button in the Bot Status card header
  - Card heading is a plain `<h3>`
  - No JS console errors

- [ ] **Step 4: Commit**

```bash
git add crm/index.html
git commit -m "fix: remove unwanted refresh button from Bot Status panel; restore anonymous fetchJobs"
```

---

## Task 3: Activity Timeline — Fixed Height + Scrollable

**Files:**
- Modify: `crm/index.html:2727-2739` (activity timeline section)

### Context
In the LeadDetail panel, `{events.map(...)}` renders unbounded. Wrap it in a scrollable container so long timelines don't force the whole panel to scroll. The section heading and empty state stay outside the container.

- [ ] **Step 1: Wrap the events list in a scrollable div**

Replace lines 2727-2739:
```jsx
            <div className="panel-section">
              <h3>Activity Timeline</h3>
              {events.length === 0 && <div className="empty">No events</div>}
              {events.map(e => (
                <div key={e.id} className="activity-item">
                  <span className="icon">
                    <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
                  </span>
                  <span style={{ fontSize: 12, color: 'var(--text-2)' }}>{e.event_type.replace(/_/g, ' ')}</span>
                  <span className="time">{timeAgo(e.created_at)}</span>
                </div>
              ))}
            </div>
```

With:
```jsx
            <div className="panel-section">
              <h3>Activity Timeline</h3>
              {events.length === 0 && <div className="empty">No events</div>}
              <div style={{ maxHeight: 220, overflowY: 'auto', border: '1px solid var(--border)', borderRadius: 'var(--r)' }}>
                {events.map(e => (
                  <div key={e.id} className="activity-item">
                    <span className="icon">
                      <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
                    </span>
                    <span style={{ fontSize: 12, color: 'var(--text-2)' }}>{e.event_type.replace(/_/g, ' ')}</span>
                    <span className="time">{timeAgo(e.created_at)}</span>
                  </div>
                ))}
              </div>
            </div>
```

- [ ] **Step 2: Verify in browser** — open a lead with multiple events. Confirm the timeline stays within 220px and scrolls.

- [ ] **Step 3: Commit**

```bash
git add crm/index.html
git commit -m "feat: make activity timeline fixed-height and scrollable"
```

---

## Task 4: Collapsible Sidebar

**Files:**
- Modify: `crm/index.html:64-83` (`.sidebar` + `.sidebar .logo` CSS)
- Modify: `crm/index.html:113-115` (`.nav a.active` — remove hardcoded rgba)
- Modify: `crm/index.html:1070-1076` (responsive media query — update to use JS state)
- Modify: `crm/index.html:4840-4849` (App state — add `sidebarCollapsed`)
- Modify: `crm/index.html:4876-4910` (sidebar JSX)

### Context
The sidebar needs a React-controlled collapse: 216px expanded (icon + label), 48px collapsed (icon-only rail). State persists to `localStorage`. Toggle button at the bottom. CSS transition for smooth animation. The existing responsive media query at line 1071 currently collapses to 52px; replace with the JS-driven approach (the inline style will override the CSS width).

- [ ] **Step 1: Update `.sidebar` CSS to add transition and remove fixed width** — the width will be set via inline style from React state. Replace lines 64-83:

```css
    .sidebar {
      width: 216px;
      background: var(--sidebar-bg);
      color: var(--sidebar-txt);
      display: flex;
      flex-direction: column;
      padding: 0;
      flex-shrink: 0;
    }

    .sidebar .logo {
      font-size: 16px;
      font-weight: 800;
      letter-spacing: -0.5px;
      padding: 22px 20px;
      border-bottom: 1px solid rgba(255,255,255,0.06);
      color: var(--sidebar-act);
    }

    .sidebar .logo span { color: var(--primary); }
```

With:
```css
    .sidebar {
      width: 216px;
      background: var(--sidebar-bg);
      color: var(--sidebar-txt);
      display: flex;
      flex-direction: column;
      padding: 0;
      flex-shrink: 0;
      transition: width 0.2s ease;
      overflow: hidden;
    }

    .sidebar .logo {
      padding: 18px 14px;
      border-bottom: 1px solid rgba(255,255,255,0.06);
      display: flex;
      align-items: center;
      overflow: hidden;
      flex-shrink: 0;
    }

    .sidebar-toggle {
      padding: 8px 6px;
      border-top: 1px solid rgba(255,255,255,0.06);
      cursor: pointer;
      color: rgba(148,163,184,0.6);
      font-size: 11px;
      display: flex;
      align-items: center;
      gap: 6px;
      background: none;
      border-left: none;
      border-right: none;
      border-bottom: none;
      width: 100%;
      white-space: nowrap;
    }

    .sidebar-toggle:hover { color: #94A3B8; }
```

- [ ] **Step 2: Update `.nav a.active` background** — at line 113 it still uses the old purple `rgba(79, 70, 229, 0.15)`. Replace:

```css
    .nav a.active {
      background: rgba(79, 70, 229, 0.15);
      color: #A5B4FC;
      font-weight: 600;
```

With:
```css
    .nav a.active {
      background: rgba(191, 26, 26, 0.15);
      color: #fca5a5;
      font-weight: 600;
```

- [ ] **Step 3: Update the responsive media query** — replace lines 1070-1076:

```css
    @media (max-width: 1024px) {
      .sidebar { width: 52px; }
      .sidebar .logo { padding: 16px 10px; font-size: 0; }
      .sidebar .logo::after { content: 'M'; font-size: 16px; font-weight: 800; color: var(--sidebar-act); }
      .nav a span:not(.nav-icon) { display: none; }
      .nav a { justify-content: center; padding: 10px; }
      .sidebar-footer { display: none; }
```

With:
```css
    @media (max-width: 1024px) {
      .sidebar-footer { display: none; }
```

- [ ] **Step 4: Add `sidebarCollapsed` state to App component** — after line 4848 (`const [showAI, setShowAI] = useState(false);`), add:

```js
      const [sidebarCollapsed, setSidebarCollapsed] = React.useState(
        () => localStorage.getItem('crm_sidebar_collapsed') === 'true'
      );

      const toggleSidebar = () => {
        setSidebarCollapsed(prev => {
          const next = !prev;
          localStorage.setItem('crm_sidebar_collapsed', String(next));
          return next;
        });
      };
```

- [ ] **Step 5: Rewrite sidebar JSX** — replace lines 4876-4910:

```jsx
          <div className="sidebar" style={{ width: sidebarCollapsed ? 48 : 216 }}>
            <div className="logo">
              {sidebarCollapsed ? (
                <div style={{ width: 36, overflow: 'hidden', flexShrink: 0 }}>
                  <svg height="26" viewBox="0 0 1024 338" xmlns="http://www.w3.org/2000/svg" style={{ display: 'block', width: 'auto', minWidth: 80, fillRule: 'evenodd', clipRule: 'evenodd', strokeLinejoin: 'round', strokeMiterlimit: 2 }}>
                    <g transform="matrix(1,0,0,1,0,-4125)"><g transform="matrix(1,0,0,0.330078,0,2877.231914)"><rect x="0" y="3780.22" width="1024" height="1024" style={{fill:'none'}}/><g transform="matrix(2.667712,0,0,2.943026,-432.539185,2932.975164)"><path d="M212.155,369.081L226.311,369.081L243.097,453.619L270.724,369.081L286.721,369.081L274.092,565.614L257.147,565.614L265.093,442.058L242.202,512.724L237.993,512.724L224.416,441.625L216.47,565.614L199.526,565.614L212.155,369.081Z" style={{fill:'white',fillRule:'nonzero'}}/></g><g transform="matrix(1,0,0,3.029586,0,2735.013372)"><path d="M498.568,602.141C490.444,607.149 481.363,611.18 471.326,614.235C460.564,617.511 448.678,619.148 435.67,619.148C421.538,619.148 408.646,616.856 396.995,612.27C385.343,607.684 375.353,601.343 367.023,593.248C358.694,585.153 352.26,575.537 347.721,564.4C343.182,553.263 340.913,541.143 340.913,528.041C340.913,520.367 341.965,512.365 344.071,504.036C346.177,495.707 349.359,487.518 353.617,479.469C357.875,471.421 363.21,463.747 369.62,456.447C376.031,449.147 383.518,442.736 392.081,437.215C400.645,431.693 410.331,427.295 421.14,424.019C431.95,420.743 443.859,419.106 456.867,419.106C471.092,419.106 484.007,421.375 495.612,425.914C507.217,430.453 517.184,436.77 525.513,444.866C533.843,452.961 540.277,462.577 544.816,473.714C549.355,484.851 551.624,496.97 551.624,510.073C551.624,517.747 550.571,525.748 548.466,534.078C546.36,542.407 543.155,550.619 538.85,558.714C536.28,563.546 534.048,567.49 531.303,571.436L547.595,588.958L514.726,619.519L498.568,602.141ZM501.175,538.365C501.385,537.875 501.589,537.382 501.789,536.885C505.065,528.743 506.702,520.18 506.702,511.196C506.702,503.896 505.369,497.134 502.702,490.911C500.034,484.687 496.314,479.259 491.541,474.626C486.768,469.994 481.036,466.367 474.345,463.747C467.653,461.126 460.283,459.816 452.235,459.816C442.408,459.816 433.424,461.618 425.281,465.221C417.139,468.824 410.144,473.714 404.295,479.891C398.445,486.067 393.906,493.227 390.678,501.369C387.449,509.511 385.834,518.074 385.834,527.059C385.834,534.265 387.168,541.003 389.835,547.273C392.503,553.544 396.223,558.995 400.996,563.628C405.769,568.26 411.501,571.887 418.192,574.507C424.884,577.128 432.254,578.438 440.302,578.438C450.035,578.438 458.973,576.636 467.115,573.033L467.525,572.85L462.191,533.13L501.175,538.365Z" style={{fill:'white'}}/><g transform="matrix(0.933333,0,0,0.933333,94.266667,225)"><circle cx="379" cy="315" r="15" style={{fill:'rgb(191,26,26)'}}/></g></g><g transform="matrix(2.667712,0,0,2.943026,-432.539185,2932.975164)"><path d="M398.964,570.528C394.544,570.528 390.781,569.323 387.677,566.915C384.572,564.506 381.985,561.399 379.915,557.594C377.845,553.788 376.231,549.453 375.074,544.588C373.916,539.723 373.074,534.858 372.548,529.993C372.021,525.127 371.741,520.479 371.706,516.047C371.671,511.616 371.758,507.858 371.969,504.776L388.597,504.776C388.422,507.377 388.413,510.243 388.571,513.374C388.729,516.505 389.211,519.467 390.018,522.261C390.825,525.055 392.053,527.391 393.702,529.27C395.351,531.149 397.596,532.088 400.437,532.088C403.49,532.088 405.954,531.245 407.831,529.559C409.708,527.873 411.155,525.802 412.172,523.345C413.19,520.888 413.874,518.239 414.224,515.397C414.575,512.555 414.751,509.93 414.751,507.521C414.751,504.631 414.461,502.03 413.882,499.718C413.304,497.406 412.47,495.31 411.383,493.432C410.295,491.553 408.953,489.819 407.357,488.229C405.761,486.64 403.946,485.074 401.911,483.533C399.28,481.51 396.587,479.197 393.833,476.596C391.079,473.995 388.589,470.623 386.361,466.481C384.133,462.338 382.3,457.232 380.862,451.162C379.424,445.093 378.704,437.579 378.704,428.619C378.704,425.247 378.862,421.297 379.178,416.769C379.494,412.241 380.064,407.593 380.888,402.824C381.713,398.055 382.844,393.359 384.282,388.734C385.721,384.11 387.58,379.967 389.86,376.306C392.141,372.646 394.877,369.707 398.069,367.491C401.262,365.276 405.033,364.168 409.383,364.168C414.821,364.168 419.267,365.854 422.723,369.225C426.178,372.597 428.845,377.149 430.722,382.882C432.598,388.614 433.782,395.213 434.274,402.679C434.765,410.146 434.747,417.925 434.221,426.018L417.803,426.018C417.908,424.284 417.917,422.164 417.829,419.659C417.741,417.155 417.373,414.746 416.724,412.434C416.075,410.122 415.031,408.147 413.593,406.509C412.155,404.871 410.12,404.052 407.489,404.052C404.682,404.052 402.49,404.847 400.911,406.437C399.332,408.026 398.148,409.929 397.359,412.145C396.57,414.361 396.079,416.576 395.886,418.792C395.693,421.008 395.596,422.79 395.596,424.139C395.596,426.837 395.886,429.269 396.464,431.437C397.043,433.605 397.929,435.58 399.122,437.362C400.315,439.144 401.823,440.806 403.647,442.347C405.472,443.889 407.647,445.478 410.173,447.116C413.26,449.043 416.136,451.452 418.803,454.342C421.469,457.232 423.775,460.845 425.722,465.18C427.669,469.515 429.195,474.693 430.301,480.715C431.406,486.736 431.958,493.841 431.958,502.03C431.958,506.751 431.739,511.712 431.3,516.914C430.862,522.117 430.125,527.271 429.09,532.377C428.055,537.483 426.705,542.324 425.038,546.9C423.372,551.476 421.32,555.523 418.882,559.039C416.443,562.555 413.575,565.349 410.278,567.421C406.98,569.492 403.209,570.528 398.964,570.528Z" style={{fill:'white',fillRule:'nonzero'}}/></g><g transform="matrix(2.667712,0,0,2.943026,-432.539185,2932.975164)"><path d="M450.902,369.081L479.897,369.081C484.984,369.081 489.544,370.936 493.579,374.645C497.613,378.354 501.042,383.604 503.866,390.396C506.69,397.188 508.848,405.401 510.339,415.035C511.83,424.669 512.575,435.459 512.575,447.405C512.575,455.401 512.225,463.903 511.523,472.911C510.821,481.919 509.707,490.782 508.181,499.501C506.655,508.22 504.708,516.577 502.34,524.573C499.972,532.57 497.113,539.602 493.763,545.672C490.413,551.741 486.554,556.582 482.186,560.195C477.818,563.808 472.898,565.614 467.425,565.614L438.273,565.614L450.902,369.081ZM468.478,525.007C472.933,525.007 476.854,523.032 480.239,519.082C483.624,515.132 486.448,509.882 488.711,503.33C490.974,496.779 492.675,489.241 493.816,480.715C494.956,472.189 495.526,463.349 495.526,454.197C495.526,447.357 495.184,441.191 494.5,435.7C493.816,430.209 492.754,425.536 491.316,421.683C489.878,417.829 488.036,414.866 485.791,412.795C483.545,410.724 480.862,409.688 477.739,409.688L464.952,409.688L457.585,525.007L468.478,525.007Z" style={{fill:'white',fillRule:'nonzero'}}/></g></g></g>
                  </svg>
                </div>
              ) : (
                <svg height="28" viewBox="0 0 1024 338" xmlns="http://www.w3.org/2000/svg" style={{ display: 'block', width: 'auto', fillRule: 'evenodd', clipRule: 'evenodd', strokeLinejoin: 'round', strokeMiterlimit: 2 }}>
                  <g transform="matrix(1,0,0,1,0,-4125)"><g transform="matrix(1,0,0,0.330078,0,2877.231914)"><rect x="0" y="3780.22" width="1024" height="1024" style={{fill:'none'}}/><g transform="matrix(2.667712,0,0,2.943026,-432.539185,2932.975164)"><path d="M212.155,369.081L226.311,369.081L243.097,453.619L270.724,369.081L286.721,369.081L274.092,565.614L257.147,565.614L265.093,442.058L242.202,512.724L237.993,512.724L224.416,441.625L216.47,565.614L199.526,565.614L212.155,369.081Z" style={{fill:'white',fillRule:'nonzero'}}/></g><g transform="matrix(1,0,0,3.029586,0,2735.013372)"><path d="M498.568,602.141C490.444,607.149 481.363,611.18 471.326,614.235C460.564,617.511 448.678,619.148 435.67,619.148C421.538,619.148 408.646,616.856 396.995,612.27C385.343,607.684 375.353,601.343 367.023,593.248C358.694,585.153 352.26,575.537 347.721,564.4C343.182,553.263 340.913,541.143 340.913,528.041C340.913,520.367 341.965,512.365 344.071,504.036C346.177,495.707 349.359,487.518 353.617,479.469C357.875,471.421 363.21,463.747 369.62,456.447C376.031,449.147 383.518,442.736 392.081,437.215C400.645,431.693 410.331,427.295 421.14,424.019C431.95,420.743 443.859,419.106 456.867,419.106C471.092,419.106 484.007,421.375 495.612,425.914C507.217,430.453 517.184,436.77 525.513,444.866C533.843,452.961 540.277,462.577 544.816,473.714C549.355,484.851 551.624,496.97 551.624,510.073C551.624,517.747 550.571,525.748 548.466,534.078C546.36,542.407 543.155,550.619 538.85,558.714C536.28,563.546 534.048,567.49 531.303,571.436L547.595,588.958L514.726,619.519L498.568,602.141ZM501.175,538.365C501.385,537.875 501.589,537.382 501.789,536.885C505.065,528.743 506.702,520.18 506.702,511.196C506.702,503.896 505.369,497.134 502.702,490.911C500.034,484.687 496.314,479.259 491.541,474.626C486.768,469.994 481.036,466.367 474.345,463.747C467.653,461.126 460.283,459.816 452.235,459.816C442.408,459.816 433.424,461.618 425.281,465.221C417.139,468.824 410.144,473.714 404.295,479.891C398.445,486.067 393.906,493.227 390.678,501.369C387.449,509.511 385.834,518.074 385.834,527.059C385.834,534.265 387.168,541.003 389.835,547.273C392.503,553.544 396.223,558.995 400.996,563.628C405.769,568.26 411.501,571.887 418.192,574.507C424.884,577.128 432.254,578.438 440.302,578.438C450.035,578.438 458.973,576.636 467.115,573.033L467.525,572.85L462.191,533.13L501.175,538.365Z" style={{fill:'white'}}/><g transform="matrix(0.933333,0,0,0.933333,94.266667,225)"><circle cx="379" cy="315" r="15" style={{fill:'rgb(191,26,26)'}}/></g></g><g transform="matrix(2.667712,0,0,2.943026,-432.539185,2932.975164)"><path d="M398.964,570.528C394.544,570.528 390.781,569.323 387.677,566.915C384.572,564.506 381.985,561.399 379.915,557.594C377.845,553.788 376.231,549.453 375.074,544.588C373.916,539.723 373.074,534.858 372.548,529.993C372.021,525.127 371.741,520.479 371.706,516.047C371.671,511.616 371.758,507.858 371.969,504.776L388.597,504.776C388.422,507.377 388.413,510.243 388.571,513.374C388.729,516.505 389.211,519.467 390.018,522.261C390.825,525.055 392.053,527.391 393.702,529.27C395.351,531.149 397.596,532.088 400.437,532.088C403.49,532.088 405.954,531.245 407.831,529.559C409.708,527.873 411.155,525.802 412.172,523.345C413.19,520.888 413.874,518.239 414.224,515.397C414.575,512.555 414.751,509.93 414.751,507.521C414.751,504.631 414.461,502.03 413.882,499.718C413.304,497.406 412.47,495.31 411.383,493.432C410.295,491.553 408.953,489.819 407.357,488.229C405.761,486.64 403.946,485.074 401.911,483.533C399.28,481.51 396.587,479.197 393.833,476.596C391.079,473.995 388.589,470.623 386.361,466.481C384.133,462.338 382.3,457.232 380.862,451.162C379.424,445.093 378.704,437.579 378.704,428.619C378.704,425.247 378.862,421.297 379.178,416.769C379.494,412.241 380.064,407.593 380.888,402.824C381.713,398.055 382.844,393.359 384.282,388.734C385.721,384.11 387.58,379.967 389.86,376.306C392.141,372.646 394.877,369.707 398.069,367.491C401.262,365.276 405.033,364.168 409.383,364.168C414.821,364.168 419.267,365.854 422.723,369.225C426.178,372.597 428.845,377.149 430.722,382.882C432.598,388.614 433.782,395.213 434.274,402.679C434.765,410.146 434.747,417.925 434.221,426.018L417.803,426.018C417.908,424.284 417.917,422.164 417.829,419.659C417.741,417.155 417.373,414.746 416.724,412.434C416.075,410.122 415.031,408.147 413.593,406.509C412.155,404.871 410.12,404.052 407.489,404.052C404.682,404.052 402.49,404.847 400.911,406.437C399.332,408.026 398.148,409.929 397.359,412.145C396.57,414.361 396.079,416.576 395.886,418.792C395.693,421.008 395.596,422.79 395.596,424.139C395.596,426.837 395.886,429.269 396.464,431.437C397.043,433.605 397.929,435.58 399.122,437.362C400.315,439.144 401.823,440.806 403.647,442.347C405.472,443.889 407.647,445.478 410.173,447.116C413.26,449.043 416.136,451.452 418.803,454.342C421.469,457.232 423.775,460.845 425.722,465.18C427.669,469.515 429.195,474.693 430.301,480.715C431.406,486.736 431.958,493.841 431.958,502.03C431.958,506.751 431.739,511.712 431.3,516.914C430.862,522.117 430.125,527.271 429.09,532.377C428.055,537.483 426.705,542.324 425.038,546.9C423.372,551.476 421.32,555.523 418.882,559.039C416.443,562.555 413.575,565.349 410.278,567.421C406.98,569.492 403.209,570.528 398.964,570.528Z" style={{fill:'white',fillRule:'nonzero'}}/></g><g transform="matrix(2.667712,0,0,2.943026,-432.539185,2932.975164)"><path d="M450.902,369.081L479.897,369.081C484.984,369.081 489.544,370.936 493.579,374.645C497.613,378.354 501.042,383.604 503.866,390.396C506.69,397.188 508.848,405.401 510.339,415.035C511.83,424.669 512.575,435.459 512.575,447.405C512.575,455.401 512.225,463.903 511.523,472.911C510.821,481.919 509.707,490.782 508.181,499.501C506.655,508.22 504.708,516.577 502.34,524.573C499.972,532.57 497.113,539.602 493.763,545.672C490.413,551.741 486.554,556.582 482.186,560.195C477.818,563.808 472.898,565.614 467.425,565.614L438.273,565.614L450.902,369.081ZM468.478,525.007C472.933,525.007 476.854,523.032 480.239,519.082C483.624,515.132 486.448,509.882 488.711,503.33C490.974,496.779 492.675,489.241 493.816,480.715C494.956,472.189 495.526,463.349 495.526,454.197C495.526,447.357 495.184,441.191 494.5,435.7C493.816,430.209 492.754,425.536 491.316,421.683C489.878,417.829 488.036,414.866 485.791,412.795C483.545,410.724 480.862,409.688 477.739,409.688L464.952,409.688L457.585,525.007L468.478,525.007Z" style={{fill:'white',fillRule:'nonzero'}}/></g></g></g>
                </svg>
              )}
            </div>
            <div className="nav">
              <a title="Dashboard" className={tab === 'dashboard' ? 'active' : ''} onClick={() => setTab('dashboard')}>
                <svg className="nav-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/></svg>
                {!sidebarCollapsed && <span>Dashboard</span>}
              </a>
              <a title="Leads" className={tab === 'leads' ? 'active' : ''} onClick={() => setTab('leads')}>
                <svg className="nav-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>
                {!sidebarCollapsed && <span>Leads</span>}
              </a>
              <a title="Pipeline" className={tab === 'pipeline' ? 'active' : ''} onClick={() => setTab('pipeline')}>
                <svg className="nav-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M22 12H2"/><path d="M5 12V4"/><path d="M9 12V8"/><path d="M13 12V10"/><path d="M17 12V6"/><path d="M21 12V2"/></svg>
                {!sidebarCollapsed && <span>Pipeline</span>}
              </a>
              <a title="Clients" className={tab === 'clients' ? 'active' : ''} onClick={() => setTab('clients')}>
                <svg className="nav-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>
                {!sidebarCollapsed && <span>Clients</span>}
              </a>
              <a title="Metrics" className={tab === 'metrics' ? 'active' : ''} onClick={() => setTab('metrics')}>
                <svg className="nav-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>
                {!sidebarCollapsed && <span>Metrics</span>}
              </a>
              <a title="Campaigns" className={tab === 'campaigns' ? 'active' : ''} onClick={() => setTab('campaigns')}>
                <svg className="nav-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/><path d="M19.07 4.93a10 10 0 0 1 0 14.14"/><path d="M15.54 8.46a5 5 0 0 1 0 7.07"/></svg>
                {!sidebarCollapsed && <span>Campaigns</span>}
              </a>
              <a title="Settings" className={tab === 'settings' ? 'active' : ''} onClick={() => setTab('settings')}>
                <svg className="nav-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>
                {!sidebarCollapsed && <span>Settings</span>}
              </a>
            </div>
            <button className="sidebar-toggle" onClick={toggleSidebar}>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                {sidebarCollapsed
                  ? <><polyline points="9 18 15 12 9 6"/></>
                  : <><polyline points="15 18 9 12 15 6"/></>
                }
              </svg>
              {!sidebarCollapsed && <span>Collapse</span>}
            </button>
          </div>
```

- [ ] **Step 6: Verify in browser** — open CRM. Confirm:
  - Sidebar animates between 216px and 48px on toggle
  - Icons always visible; text labels hidden when collapsed
  - Logo shows full SVG when expanded, clipped 36px when collapsed
  - Collapse state persists after page refresh (check `localStorage.getItem('crm_sidebar_collapsed')`)
  - Hover `title` tooltips show nav item names when collapsed

- [ ] **Step 7: Commit**

```bash
git add crm/index.html
git commit -m "feat: collapsible sidebar with logo SVG and localStorage persistence"
```

---

## Task 5: Brand Colors — CRM

**Files:**
- Modify: `crm/index.html:19-42` (`:root` CSS tokens)
- Modify: `crm/index.html:113` (`.nav a.active` hardcoded rgba — already done in Task 4 Step 2)
- Modify: `crm/index.html:648` (`.chat-assistant` border)
- Modify: `crm/index.html:1057` (`.ai-example-chip` border)
- Modify: `crm/index.html:1067` (`.ai-example-chip:hover`)
- Modify: `crm/index.html:1535` (inline style — Today header color)
- Modify: `crm/index.html:1547` (inline style — stat-card border)
- Modify: `crm/index.html:2526` (inline style — color)
- Modify: `crm/index.html:4046` (inline style — chart color)
- Modify: `crm/index.html:4113` (inline style — items color)

### Context
Update CSS tokens (`--bg`, `--sidebar-bg`, `--sidebar-hi`, `--primary`, `--primary-hi`, `--primary-s`, `--text`) to brand values. Then replace every hardcoded `#4F46E5`, `#4338CA`, and `rgba(79,70,229…)` occurrence in inline styles. Success/warning/danger colors are unchanged.

- [ ] **Step 1: Update `:root` CSS tokens** — replace lines 19-42:

```css
    :root {
      --bg:          #f6f4f0;
      --surface:     #FFFFFF;
      --surface-alt: #F1F3F7;
      --sidebar-bg:  #002347;
      --sidebar-hi:  #0a3a6e;
      --sidebar-txt: #94A3B8;
      --sidebar-act: #F8FAFC;
      --text:        #002347;
      --text-2:      #475569;
      --text-3:      #94A3B8;
      --border:      #E2E8F0;
      --border-hi:   #CBD5E1;
      --primary:     #bf1a1a;
      --primary-hi:  #991515;
      --primary-s:   rgba(191, 26, 26, 0.08);
      --success:     #16A34A;
      --warning:     #CA8A04;
      --danger:      #DC2626;
      --r:           8px;
      --r-lg:        12px;
      --shadow-sm:   0 1px 3px rgba(0,0,0,0.06), 0 1px 2px rgba(0,0,0,0.04);
      --shadow:      0 4px 12px rgba(0,0,0,0.08);
    }
```

- [ ] **Step 2: Replace hardcoded purple values** — make these targeted replacements:

At line 648 (`.chat-assistant` border):
```css
      border: 1px solid rgba(79,70,229,0.12);
```
→
```css
      border: 1px solid rgba(191,26,26,0.12);
```

At line 1057 (`.ai-example-chip` border):
```css
      border: 1px solid rgba(79,70,229,0.15);
```
→
```css
      border: 1px solid rgba(191,26,26,0.15);
```

At line 1067 (`.ai-example-chip:hover`):
```css
    .ai-example-chip:hover { background: rgba(79,70,229,0.14); }
```
→
```css
    .ai-example-chip:hover { background: rgba(191,26,26,0.14); }
```

At line 1535 (Today header inline style):
```jsx
                    <div style={{ fontWeight: 600, color: '#4F46E5', marginBottom: 7, fontSize: 12, textTransform: 'uppercase', letterSpacing: '0.05em' }}>Today ({priorities.todayFollowups.length})</div>
```
→
```jsx
                    <div style={{ fontWeight: 600, color: '#bf1a1a', marginBottom: 7, fontSize: 12, textTransform: 'uppercase', letterSpacing: '0.05em' }}>Today ({priorities.todayFollowups.length})</div>
```

At line 1547 (stat-card border):
```jsx
            <div className="stat-card" style={{ borderLeft: '3px solid #4F46E5' }}>
```
→
```jsx
            <div className="stat-card" style={{ borderLeft: '3px solid #bf1a1a' }}>
```

At line 2526 (inline color):
```jsx
                        <span style={{ fontWeight: 600, color: '#4F46E5' }}>
```
→
```jsx
                        <span style={{ fontWeight: 600, color: '#bf1a1a' }}>
```

At line 4046 (chart color):
```js
        { label: '/start', count: total, color: '#4F46E5' },
```
→
```js
        { label: '/start', count: total, color: '#bf1a1a' },
```

At line 4113 (items color):
```js
        { title: 'Lead Acquisition', icon: '\uD83D\uDCE5', color: '#4F46E5', items: [
```
→
```js
        { title: 'Lead Acquisition', icon: '\uD83D\uDCE5', color: '#bf1a1a', items: [
```

- [ ] **Step 3: Verify no remaining purple values** — run:

```bash
grep -n "#4F46E5\|#4338CA\|rgba(79,\s*70,\s*229" crm/index.html
```

Expected: only the now-updated lines from Step 1's `:root` block should be gone. Output should be empty.

- [ ] **Step 4: Verify in browser** — confirm sidebar is `#002347` navy, primary buttons/badges are `#bf1a1a` red, page background is `#f6f4f0` cream. No purple anywhere.

- [ ] **Step 5: Commit**

```bash
git add crm/index.html
git commit -m "feat: apply brand colors to CRM (navy #002347, red #bf1a1a, cream #f6f4f0)"
```

---

## Task 6: TWA Full Refresh

**Files:**
- Modify: `twa/index.html:11-28` (`:root` CSS tokens — dark→light brand palette)
- Modify: `twa/index.html:659-666` (header logo — img→inline SVG)

### Context
The TWA is currently dark-themed (`#07101C` background). Switch to the light brand palette: cream background, navy text, red accent. Also inline the logo SVG so it renders on the dark header if one exists, or scales correctly without an img request.

- [ ] **Step 1: Update `:root` CSS tokens** — replace lines 11-28:

```css
        :root {
            --bg:        #f6f4f0;
            --surface:   #ffffff;
            --surface-hi:#ede9e3;
            --text:      #002347;
            --dim:       rgba(0,35,71,0.60);
            --muted:     rgba(0,35,71,0.38);
            --faint:     rgba(0,35,71,0.07);
            --accent:    #bf1a1a;
            --accent-s:  rgba(191,26,26,0.10);
            --green:     #22C55E;
            --red-m:     #F87171;
            --border:    rgba(0,35,71,0.10);
            --border-hi: rgba(0,35,71,0.18);
            --r:         10px;
            --r-sm:      6px;
            --ease:      0.22s cubic-bezier(0.4, 0, 0.2, 1);
        }
```

- [ ] **Step 2: Replace logo `<img>` with inline SVG** — replace lines 659-666:

```html
<header class="header">
    <div class="logo">
        <img src="logo.svg" alt="MQSD"
             onerror="this.style.display='none'; document.getElementById('logo-fallback').style.display='block'">
        <div id="logo-fallback" class="logo-text" style="display:none;">
            MQ<span class="dot">.</span>SD
        </div>
    </div>
```

With:
```html
<header class="header">
    <div class="logo">
        <svg height="26" viewBox="0 0 1024 338" xmlns="http://www.w3.org/2000/svg" style="display:block;width:auto;fill-rule:evenodd;clip-rule:evenodd;stroke-linejoin:round;stroke-miterlimit:2;">
            <g transform="matrix(1,0,0,1,0,-4125)"><g transform="matrix(1,0,0,0.330078,0,2877.231914)"><rect x="0" y="3780.22" width="1024" height="1024" style="fill:none;"/><g transform="matrix(2.667712,0,0,2.943026,-432.539185,2932.975164)"><path d="M212.155,369.081L226.311,369.081L243.097,453.619L270.724,369.081L286.721,369.081L274.092,565.614L257.147,565.614L265.093,442.058L242.202,512.724L237.993,512.724L224.416,441.625L216.47,565.614L199.526,565.614L212.155,369.081Z" style="fill:#002347;fill-rule:nonzero;"/></g><g transform="matrix(1,0,0,3.029586,0,2735.013372)"><path d="M498.568,602.141C490.444,607.149 481.363,611.18 471.326,614.235C460.564,617.511 448.678,619.148 435.67,619.148C421.538,619.148 408.646,616.856 396.995,612.27C385.343,607.684 375.353,601.343 367.023,593.248C358.694,585.153 352.26,575.537 347.721,564.4C343.182,553.263 340.913,541.143 340.913,528.041C340.913,520.367 341.965,512.365 344.071,504.036C346.177,495.707 349.359,487.518 353.617,479.469C357.875,471.421 363.21,463.747 369.62,456.447C376.031,449.147 383.518,442.736 392.081,437.215C400.645,431.693 410.331,427.295 421.14,424.019C431.95,420.743 443.859,419.106 456.867,419.106C471.092,419.106 484.007,421.375 495.612,425.914C507.217,430.453 517.184,436.77 525.513,444.866C533.843,452.961 540.277,462.577 544.816,473.714C549.355,484.851 551.624,496.97 551.624,510.073C551.624,517.747 550.571,525.748 548.466,534.078C546.36,542.407 543.155,550.619 538.85,558.714C536.28,563.546 534.048,567.49 531.303,571.436L547.595,588.958L514.726,619.519L498.568,602.141ZM501.175,538.365C501.385,537.875 501.589,537.382 501.789,536.885C505.065,528.743 506.702,520.18 506.702,511.196C506.702,503.896 505.369,497.134 502.702,490.911C500.034,484.687 496.314,479.259 491.541,474.626C486.768,469.994 481.036,466.367 474.345,463.747C467.653,461.126 460.283,459.816 452.235,459.816C442.408,459.816 433.424,461.618 425.281,465.221C417.139,468.824 410.144,473.714 404.295,479.891C398.445,486.067 393.906,493.227 390.678,501.369C387.449,509.511 385.834,518.074 385.834,527.059C385.834,534.265 387.168,541.003 389.835,547.273C392.503,553.544 396.223,558.995 400.996,563.628C405.769,568.26 411.501,571.887 418.192,574.507C424.884,577.128 432.254,578.438 440.302,578.438C450.035,578.438 458.973,576.636 467.115,573.033L467.525,572.85L462.191,533.13L501.175,538.365Z" style="fill:#002347;"/><g transform="matrix(0.933333,0,0,0.933333,94.266667,225)"><circle cx="379" cy="315" r="15" style="fill:rgb(191,26,26);"/></g></g><g transform="matrix(2.667712,0,0,2.943026,-432.539185,2932.975164)"><path d="M398.964,570.528C394.544,570.528 390.781,569.323 387.677,566.915C384.572,564.506 381.985,561.399 379.915,557.594C377.845,553.788 376.231,549.453 375.074,544.588C373.916,539.723 373.074,534.858 372.548,529.993C372.021,525.127 371.741,520.479 371.706,516.047C371.671,511.616 371.758,507.858 371.969,504.776L388.597,504.776C388.422,507.377 388.413,510.243 388.571,513.374C388.729,516.505 389.211,519.467 390.018,522.261C390.825,525.055 392.053,527.391 393.702,529.27C395.351,531.149 397.596,532.088 400.437,532.088C403.49,532.088 405.954,531.245 407.831,529.559C409.708,527.873 411.155,525.802 412.172,523.345C413.19,520.888 413.874,518.239 414.224,515.397C414.575,512.555 414.751,509.93 414.751,507.521C414.751,504.631 414.461,502.03 413.882,499.718C413.304,497.406 412.47,495.31 411.383,493.432C410.295,491.553 408.953,489.819 407.357,488.229C405.761,486.64 403.946,485.074 401.911,483.533C399.28,481.51 396.587,479.197 393.833,476.596C391.079,473.995 388.589,470.623 386.361,466.481C384.133,462.338 382.3,457.232 380.862,451.162C379.424,445.093 378.704,437.579 378.704,428.619C378.704,425.247 378.862,421.297 379.178,416.769C379.494,412.241 380.064,407.593 380.888,402.824C381.713,398.055 382.844,393.359 384.282,388.734C385.721,384.11 387.58,379.967 389.86,376.306C392.141,372.646 394.877,369.707 398.069,367.491C401.262,365.276 405.033,364.168 409.383,364.168C414.821,364.168 419.267,365.854 422.723,369.225C426.178,372.597 428.845,377.149 430.722,382.882C432.598,388.614 433.782,395.213 434.274,402.679C434.765,410.146 434.747,417.925 434.221,426.018L417.803,426.018C417.908,424.284 417.917,422.164 417.829,419.659C417.741,417.155 417.373,414.746 416.724,412.434C416.075,410.122 415.031,408.147 413.593,406.509C412.155,404.871 410.12,404.052 407.489,404.052C404.682,404.052 402.49,404.847 400.911,406.437C399.332,408.026 398.148,409.929 397.359,412.145C396.57,414.361 396.079,416.576 395.886,418.792C395.693,421.008 395.596,422.79 395.596,424.139C395.596,426.837 395.886,429.269 396.464,431.437C397.043,433.605 397.929,435.58 399.122,437.362C400.315,439.144 401.823,440.806 403.647,442.347C405.472,443.889 407.647,445.478 410.173,447.116C413.26,449.043 416.136,451.452 418.803,454.342C421.469,457.232 423.775,460.845 425.722,465.18C427.669,469.515 429.195,474.693 430.301,480.715C431.406,486.736 431.958,493.841 431.958,502.03C431.958,506.751 431.739,511.712 431.3,516.914C430.862,522.117 430.125,527.271 429.09,532.377C428.055,537.483 426.705,542.324 425.038,546.9C423.372,551.476 421.32,555.523 418.882,559.039C416.443,562.555 413.575,565.349 410.278,567.421C406.98,569.492 403.209,570.528 398.964,570.528Z" style="fill:#002347;fill-rule:nonzero;"/></g><g transform="matrix(2.667712,0,0,2.943026,-432.539185,2932.975164)"><path d="M450.902,369.081L479.897,369.081C484.984,369.081 489.544,370.936 493.579,374.645C497.613,378.354 501.042,383.604 503.866,390.396C506.69,397.188 508.848,405.401 510.339,415.035C511.83,424.669 512.575,435.459 512.575,447.405C512.575,455.401 512.225,463.903 511.523,472.911C510.821,481.919 509.707,490.782 508.181,499.501C506.655,508.22 504.708,516.577 502.34,524.573C499.972,532.57 497.113,539.602 493.763,545.672C490.413,551.741 486.554,556.582 482.186,560.195C477.818,563.808 472.898,565.614 467.425,565.614L438.273,565.614L450.902,369.081ZM468.478,525.007C472.933,525.007 476.854,523.032 480.239,519.082C483.624,515.132 486.448,509.882 488.711,503.33C490.974,496.779 492.675,489.241 493.816,480.715C494.956,472.189 495.526,463.349 495.526,454.197C495.526,447.357 495.184,441.191 494.5,435.7C493.816,430.209 492.754,425.536 491.316,421.683C489.878,417.829 488.036,414.866 485.791,412.795C483.545,410.724 480.862,409.688 477.739,409.688L464.952,409.688L457.585,525.007L468.478,525.007Z" style="fill:#002347;fill-rule:nonzero;"/></g></g></g>
        </svg>
    </div>
```

**Note:** The SVG paths use `fill:#002347` (navy) instead of `fill:white` because the TWA background is now light (`#f6f4f0`). The red dot circle keeps `fill:rgb(191,26,26)`.

- [ ] **Step 3: Verify in browser** — open `twa/index.html` locally. Confirm:
  - Page background is cream (#f6f4f0)
  - Text is dark navy (#002347)
  - Logo renders correctly at 26px height
  - Accent buttons/CTAs are red (#bf1a1a)
  - No dark backgrounds visible (the old dark surfaces should now be white/light)

- [ ] **Step 4: Commit**

```bash
git add twa/index.html
git commit -m "feat: apply brand colors and inline logo SVG to TWA"
```

---

## Self-Review

**Spec coverage check:**

| Spec section | Covered by |
|---|---|
| 1. Scheduler job status fix | Task 1 |
| 2. Remove Settings refresh button | Task 2 |
| 3. Activity timeline fixed height + scrollable | Task 3 |
| 4. Collapsible sidebar | Task 4 |
| 5. Logo — twa/logo.svg inlined | Task 4 (CRM, both modes) + Task 6 (TWA) |
| 6. Brand colors CRM | Task 5 |
| 7. TWA full refresh | Task 6 |

**No placeholders found** — every step contains exact code.

**Type consistency** — `sidebarCollapsed` boolean used consistently in Task 4 Steps 4 and 5. `toggleSidebar` defined in Step 4, used in Step 5. `_record_job` signature matches the existing function at line 133 of `scheduler_service.py`.

**Note on Task ordering** — Tasks 4 (sidebar) and 5 (brand colors) both touch `crm/index.html`. The `.nav a.active` color change is addressed in Task 4 Step 2 (it uses the old purple rgba) so it is already updated before Task 5 runs. No conflict.
