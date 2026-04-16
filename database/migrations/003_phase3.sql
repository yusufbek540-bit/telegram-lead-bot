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
