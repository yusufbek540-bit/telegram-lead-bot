-- ============================================================
-- Phase 3 — Automation Migration (Smart Routing, Auto-Tagging, Sentiment)
-- Safe to re-run (all statements are idempotent)
-- Run in Supabase SQL Editor: https://supabase.com/dashboard
-- ============================================================

-- 1. TEAM MEMBERS UPGRADE
-- Guaranteeing core team membership assignment attributes
CREATE TABLE IF NOT EXISTS team_members (
    id            BIGSERIAL PRIMARY KEY,
    name          TEXT NOT NULL,
    telegram_id   TEXT NOT NULL UNIQUE,
    specialization JSONB DEFAULT '[]'::JSONB,
    is_active     BOOLEAN DEFAULT TRUE,
    created_at    TIMESTAMPTZ DEFAULT NOW()
);

-- Safely apply additions if simple manual table prevailed previously
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='team_members' AND column_name='specialization') THEN
        ALTER TABLE team_members ADD COLUMN specialization JSONB DEFAULT '[]'::JSONB;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='team_members' AND column_name='is_active') THEN
        ALTER TABLE team_members ADD COLUMN is_active BOOLEAN DEFAULT TRUE;
    END IF;
END $$;

-- 2. SMART LEAD ROUTING RULES
CREATE TABLE IF NOT EXISTS routing_rules (
    id                BIGSERIAL PRIMARY KEY,
    name              TEXT NOT NULL,
    conditions        JSONB DEFAULT '{}'::JSONB,
    assignee_strategy TEXT NOT NULL,
    priority          INT DEFAULT 0,
    is_active         BOOLEAN DEFAULT TRUE,
    created_at        TIMESTAMPTZ DEFAULT NOW()
);

-- 3. LEAD TAGS (AI behavioral mapping)
CREATE TABLE IF NOT EXISTS lead_tags (
    id           BIGSERIAL PRIMARY KEY,
    telegram_id  BIGINT NOT NULL REFERENCES leads(telegram_id) ON DELETE CASCADE,
    tag          TEXT NOT NULL,
    confidence   NUMERIC DEFAULT 100.0,
    source       TEXT DEFAULT 'manual', -- manual | ai | behavior
    created_at   TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(telegram_id, tag)
);
CREATE INDEX IF NOT EXISTS idx_lead_tags_telegram ON lead_tags(telegram_id);

-- 4. CONVERSATION SENTIMENT
ALTER TABLE leads ADD COLUMN IF NOT EXISTS sentiment TEXT; -- positive | neutral | negative
ALTER TABLE leads ADD COLUMN IF NOT EXISTS sentiment_updated_at TIMESTAMPTZ;
ALTER TABLE leads ADD COLUMN IF NOT EXISTS key_signals JSONB DEFAULT '[]'::JSONB;
