-- ============================================================
-- Phase 5 — Campaigns & Duplicate Detection
-- Safe to re-run (idempotent)
-- Run in Supabase SQL Editor: https://supabase.com/dashboard
-- ============================================================

-- Campaigns table
CREATE TABLE IF NOT EXISTS campaigns (
    id              BIGSERIAL PRIMARY KEY,
    name            TEXT NOT NULL,
    message_uz      TEXT NOT NULL DEFAULT '',
    message_ru      TEXT NOT NULL DEFAULT '',
    target_filters  JSONB NOT NULL DEFAULT '{}',
    scheduled_for   TIMESTAMPTZ,
    status          TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'scheduled', 'sending', 'sent', 'failed')),
    sent_count      INTEGER NOT NULL DEFAULT 0,
    failed_count    INTEGER NOT NULL DEFAULT 0,
    created_by      TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Campaign deliveries table
CREATE TABLE IF NOT EXISTS campaign_deliveries (
    id              BIGSERIAL PRIMARY KEY,
    campaign_id     BIGINT NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    telegram_id     BIGINT NOT NULL,
    sent_at         TIMESTAMPTZ,
    delivered       BOOLEAN DEFAULT NULL,
    failed_reason   TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_campaign_deliveries_campaign ON campaign_deliveries(campaign_id);
CREATE INDEX IF NOT EXISTS idx_campaign_deliveries_telegram ON campaign_deliveries(telegram_id);

-- Duplicate detection
ALTER TABLE leads ADD COLUMN IF NOT EXISTS duplicate_of BIGINT REFERENCES leads(telegram_id);

CREATE INDEX IF NOT EXISTS idx_leads_phone ON leads(phone) WHERE phone IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_leads_duplicate_of ON leads(duplicate_of) WHERE duplicate_of IS NOT NULL;

-- Updated_at trigger for campaigns
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_trigger WHERE tgname = 'campaigns_updated_at'
    ) THEN
        CREATE TRIGGER campaigns_updated_at
            BEFORE UPDATE ON campaigns
            FOR EACH ROW EXECUTE FUNCTION set_updated_at();
    END IF;
END $$;
