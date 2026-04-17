# CRM & Bot UI Refresh — Design Spec

**Date:** 2026-04-18  
**Scope:** Scheduler job status fix, CRM activity timeline, collapsible sidebar, logo, brand colors (CRM + TWA)

---

## 1. Scheduler Job Status Fix

**Problem:** Seven imported scheduler jobs never call `_record_job()`, so the CRM Bot Status panel shows them as "pending / never" indefinitely even when they are executing correctly. Only `run_followups` and `heartbeat` (defined inline in `scheduler_service.py`) update their status. Additionally `run_chat_relay` fires every 5 seconds, which is excessively aggressive.

**Fix:** In `bot/services/scheduler_service.py`, replace direct registration of each imported job with a thin local async wrapper that:
1. Calls the original imported function
2. Calls `_record_job(job_id)` on success or `_record_job(job_id, status="error", error=str(e))` on exception

Jobs to wrap: `check_followup_reminders`, `detect_stale_leads`, `check_proposal_expiry`, `run_auto_tagger`, `run_sentiment_analysis`, `check_scheduled_campaigns`, `run_chat_relay`.

**Additional change:** Slow `run_chat_relay` trigger from `seconds=5` → `seconds=30`.

**No changes to any service files** — only `scheduler_service.py` is modified.

---

## 2. Remove Settings Refresh Button

**Problem:** A `↻ Refresh` button was added to the Bot Status / Scheduler Jobs panel in Settings. The user did not request this. The `useEffect` already auto-refreshes every 30 seconds.

**Fix:** Revert the panel heading back to a plain `<h3>` and remove the `loadSettings` `useCallback`. Keep the auto-refresh `useEffect` but restore the anonymous `fetchJobs` function inside it.

**File:** `crm/index.html` — Settings tab, Bot Status card.

---

## 3. Activity Timeline — Fixed Height + Scrollable

**Problem:** The Activity Timeline in the lead detail panel can grow very long with many events, forcing the user to scroll the entire panel.

**Fix:** Wrap the `{events.map(...)}` block in a container div with:
- `max-height: 220px`
- `overflow-y: auto`
- `border: 1px solid var(--border)` and `border-radius: var(--r)` for visual containment

The section heading and "No events" empty state remain outside the scroll container.

**File:** `crm/index.html` — LeadDetail `Activity Timeline` panel section.

---

## 4. Collapsible Sidebar

**Behavior:**
- **Expanded** (default): 216px wide, shows icons + text labels, logo full-width
- **Collapsed**: 48px wide (icon rail only), text labels hidden, logo replaced by icon-only version
- Toggle button at the very bottom of the sidebar (‹ collapse / › expand)
- State persisted to `localStorage` key `crm_sidebar_collapsed`
- Smooth CSS `transition: width 0.2s ease` on the sidebar element
- Nav items: icon always visible, text fades out (`opacity: 0; width: 0; overflow: hidden`) when collapsed
- Hover tooltip on collapsed nav items showing the label (CSS `title` attribute is sufficient)
- Main content area: `flex: 1` naturally expands to fill remaining space — no JS needed

**Implementation:** Single `const [collapsed, setCollapsed] = React.useState(...)` at the top of the main `App` component, initialized from `localStorage`. Passed as a prop (or read from context) wherever the sidebar is rendered. The sidebar width is set inline: `style={{ width: collapsed ? 48 : 216 }}`.

**File:** `crm/index.html` — sidebar JSX + CSS `.sidebar` rule.

---

## 5. Logo — Use twa/logo.svg

**CRM sidebar:**
- The SVG content from `twa/logo.svg` is inlined directly into the sidebar logo area
- Expanded mode: SVG constrained to `height: 28px; width: auto` with `overflow: visible`
- Collapsed mode: show the same SVG at `height: 26px; width: auto` inside a `div` with `width: 36px; overflow: hidden` — the SVG renders at its natural proportional width (~80px) but is clipped at 36px, keeping the leftmost portion of the wordmark visible as a brand mark
- The SVG paths are white on the transparent background, matching the dark `#002347` sidebar

**TWA (`twa/index.html`):**
- Logo SVG inlined in the page header / hero section
- Sized appropriately for the hero context (~180px wide)

---

## 6. Brand Colors — CRM

Replace CSS design tokens in `crm/index.html` `:root` block:

| Token | Old value | New value |
|---|---|---|
| `--bg` | `#F7F8FA` | `#f6f4f0` |
| `--sidebar-bg` | `#0F172A` | `#002347` |
| `--sidebar-hi` | `#1E293B` | `#0a3a6e` (lighter navy hover) |
| `--primary` | `#4F46E5` | `#bf1a1a` |
| `--primary-hi` | `#4338CA` | `#991515` |
| `--primary-s` | `rgba(79,70,229,0.08)` | `rgba(191,26,26,0.08)` |
| `--text` | `#0F172A` | `#002347` |

All hardcoded `#4F46E5`, `#4338CA`, and `rgba(79, 70, 229…)` occurrences in inline styles throughout the file are replaced with the red equivalents.

The success/warning/danger colors (`--success`, `--warning`, `--danger`) remain unchanged — they are semantic status colors, not brand colors.

**File:** `crm/index.html` — `:root` block + all inline style occurrences.

---

## 7. TWA Full Refresh

**Files:** `twa/index.html`

**Color tokens** (update `:root` CSS variables):
- Primary/brand: `#002347` (navy) as primary dark
- Accent: `#bf1a1a` (red) for CTAs, highlights
- Background: `#f6f4f0` (off-white/cream) for page background
- All existing blue/indigo tones replaced with the navy/red palette

**Logo:** Inline `twa/logo.svg` SVG content into the page header. The logo uses white paths on transparent, so it works on dark (`#002347`) backgrounds.

**Typography:** Keep the existing font stack but align heading weights and colors to the brand — dark headings (`#002347`), red CTAs.

**Scope:** This is a CSS variable + logo swap, not a layout restructure. The existing TWA sections (portfolio, services, contact) keep their structure.

---

## Out of Scope

- No changes to bot handler logic
- No database schema changes
- No new scheduler jobs added or removed
- No layout restructure of TWA sections
- The `questionnaire-implementation-plan.md` file in the repo root (cleanup is a separate task)

---

## Files Changed

| File | Changes |
|---|---|
| `bot/services/scheduler_service.py` | Add 7 wrapper functions; slow `run_chat_relay` to 30s |
| `crm/index.html` | Remove refresh button; scrollable timeline; collapsible sidebar; inline logo SVG; brand color tokens + inline replacements |
| `twa/index.html` | Brand color tokens; inline logo SVG; typography alignment |
