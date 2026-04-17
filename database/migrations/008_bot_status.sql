-- ============================================================
-- Bot Status & Job Tracking
-- Safe to re-run (idempotent)
-- Run in Supabase SQL Editor: https://supabase.com/dashboard
-- ============================================================

-- Tracks last run time and status of each scheduler job.
-- The bot writes here; the CRM reads it to show system health.
CREATE TABLE IF NOT EXISTS job_status (
    job_id      TEXT PRIMARY KEY,
    last_run_at TIMESTAMPTZ,
    last_status TEXT DEFAULT 'ok',   -- 'ok' | 'error'
    last_error  TEXT,
    run_count   INTEGER DEFAULT 0,
    updated_at  TIMESTAMPTZ DEFAULT NOW()
);
