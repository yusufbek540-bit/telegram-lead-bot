-- ============================================================
-- CRM DASHBOARD EXTENSION — Supabase Database Schema
-- Run this in your Supabase SQL Editor to extend the existing schema
-- Safe to run multiple times; uses IF NOT EXISTS and DO blocks
-- ============================================================

-- ============================================================
-- SECTION 1: ALTER EXISTING LEADS TABLE
-- Add CRM-specific columns (idempotent using DO $$ block)
-- ============================================================

DO $$
BEGIN
    -- Add assigned_to column if it doesn't exist
    IF NOT EXISTS(SELECT 1 FROM information_schema.columns WHERE table_name='leads' AND column_name='assigned_to') THEN
        ALTER TABLE leads ADD COLUMN assigned_to TEXT;
    END IF;

    -- Add rejection_reason column if it doesn't exist
    IF NOT EXISTS(SELECT 1 FROM information_schema.columns WHERE table_name='leads' AND column_name='rejection_reason') THEN
        ALTER TABLE leads ADD COLUMN rejection_reason TEXT;
    END IF;

    -- Add last_contacted_at column if it doesn't exist
    IF NOT EXISTS(SELECT 1 FROM information_schema.columns WHERE table_name='leads' AND column_name='last_contacted_at') THEN
        ALTER TABLE leads ADD COLUMN last_contacted_at TIMESTAMPTZ;
    END IF;

    -- Add next_followup_at column if it doesn't exist
    IF NOT EXISTS(SELECT 1 FROM information_schema.columns WHERE table_name='leads' AND column_name='next_followup_at') THEN
        ALTER TABLE leads ADD COLUMN next_followup_at TIMESTAMPTZ;
    END IF;
END $$;

-- ============================================================
-- SECTION 2: NEW TABLES
-- ============================================================

-- STATUS_HISTORY — Audit log of all status changes
CREATE TABLE IF NOT EXISTS status_history (
    id              BIGSERIAL PRIMARY KEY,
    telegram_id     BIGINT NOT NULL REFERENCES leads(telegram_id) ON DELETE CASCADE,
    old_status      TEXT,
    new_status      TEXT NOT NULL,
    changed_by      TEXT DEFAULT 'system',
    reason          TEXT,
    note            TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- COMMENTS — Team notes and collaboration on leads
CREATE TABLE IF NOT EXISTS comments (
    id              BIGSERIAL PRIMARY KEY,
    telegram_id     BIGINT NOT NULL REFERENCES leads(telegram_id) ON DELETE CASCADE,
    author          TEXT NOT NULL,
    content         TEXT NOT NULL,
    is_pinned       BOOLEAN DEFAULT false,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- SECTION 3: INDEXES
-- ============================================================

-- Indexes for status_history table
CREATE INDEX IF NOT EXISTS idx_status_history_telegram ON status_history(telegram_id, created_at DESC);

-- Indexes for comments table
CREATE INDEX IF NOT EXISTS idx_comments_telegram ON comments(telegram_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_comments_pinned ON comments(telegram_id, is_pinned);

-- Indexes for new leads columns
CREATE INDEX IF NOT EXISTS idx_leads_assigned ON leads(assigned_to);
CREATE INDEX IF NOT EXISTS idx_leads_followup ON leads(next_followup_at);

-- ============================================================
-- SECTION 4: VIEWS
-- ============================================================

-- PIPELINE_SUMMARY — Count of leads per status with metrics
CREATE OR REPLACE VIEW pipeline_summary AS
SELECT
    status,
    COUNT(*) AS lead_count,
    ROUND(AVG(lead_score)::NUMERIC, 2) AS avg_score,
    COUNT(CASE WHEN phone IS NOT NULL THEN 1 END) AS leads_with_phone
FROM leads
GROUP BY status
ORDER BY lead_count DESC;

-- ============================================================
-- SECTION 5: HELPER FUNCTIONS (OPTIONAL)
-- ============================================================

-- Function to log status changes automatically
CREATE OR REPLACE FUNCTION log_status_change()
RETURNS TRIGGER AS $$
BEGIN
    IF OLD.status IS DISTINCT FROM NEW.status THEN
        INSERT INTO status_history (telegram_id, old_status, new_status, changed_by, created_at)
        VALUES (NEW.telegram_id, OLD.status, NEW.status, 'system', NOW());
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger to automatically log status changes
DROP TRIGGER IF EXISTS leads_status_change_trigger ON leads;
CREATE TRIGGER leads_status_change_trigger
    AFTER UPDATE ON leads
    FOR EACH ROW
    EXECUTE FUNCTION log_status_change();

-- ============================================================
-- END OF CRM EXTENSION SCHEMA
-- ============================================================
