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
