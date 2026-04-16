-- ============================================================
-- TELEGRAM LEAD BOT — Supabase Database Schema
-- Run this in your Supabase SQL Editor (supabase.com → SQL)
-- ============================================================

-- 1. LEADS TABLE — Core contact info, auto-captured from Telegram
CREATE TABLE IF NOT EXISTS leads (
    id              BIGSERIAL PRIMARY KEY,
    telegram_id     BIGINT UNIQUE NOT NULL,
    first_name      TEXT,
    last_name       TEXT,
    username        TEXT,
    phone           TEXT,
    email           TEXT,
    language_code   TEXT DEFAULT 'uz',
    preferred_lang  TEXT DEFAULT 'uz',        -- 'uz' or 'ru', user can switch
    source          TEXT DEFAULT 'organic',    -- deep link param from Meta ad
    status          TEXT DEFAULT 'new',        -- new → contacted → qualified → converted → lost
    lead_score      INTEGER DEFAULT 0,
    notes           TEXT,                      -- manual notes from your team
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- 2. CONVERSATIONS TABLE — Full chat history (feeds AI context)
CREATE TABLE IF NOT EXISTS conversations (
    id              BIGSERIAL PRIMARY KEY,
    telegram_id     BIGINT NOT NULL REFERENCES leads(telegram_id) ON DELETE CASCADE,
    role            TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    message         TEXT NOT NULL,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- 3. EVENTS TABLE — Behavioral tracking (button clicks, TWA opens, etc.)
CREATE TABLE IF NOT EXISTS events (
    id              BIGSERIAL PRIMARY KEY,
    telegram_id     BIGINT NOT NULL REFERENCES leads(telegram_id) ON DELETE CASCADE,
    event_type      TEXT NOT NULL,             -- 'button_click', 'twa_open', 'phone_shared', 'ai_chat', 'callback_request'
    event_data      JSONB DEFAULT '{}',        -- e.g., {"button": "services", "section": "smm"}
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- 4. INDEXES — Speed up common queries
CREATE INDEX idx_leads_source ON leads(source);
CREATE INDEX idx_leads_status ON leads(status);
CREATE INDEX idx_leads_created ON leads(created_at DESC);
CREATE INDEX idx_conversations_telegram ON conversations(telegram_id, created_at DESC);
CREATE INDEX idx_events_telegram ON events(telegram_id, created_at DESC);
CREATE INDEX idx_events_type ON events(event_type);

-- 5. AUTO-UPDATE updated_at on leads
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER leads_updated_at
    BEFORE UPDATE ON leads
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at();

-- 6. USEFUL VIEWS — Quick analytics

-- Leads summary by source
CREATE OR REPLACE VIEW leads_by_source AS
SELECT
    source,
    COUNT(*) AS total_leads,
    COUNT(phone) AS with_phone,
    COUNT(CASE WHEN status = 'qualified' THEN 1 END) AS qualified,
    COUNT(CASE WHEN status = 'converted' THEN 1 END) AS converted,
    MIN(created_at) AS first_lead,
    MAX(created_at) AS latest_lead
FROM leads
GROUP BY source
ORDER BY total_leads DESC;

-- Daily lead count (last 30 days)
CREATE OR REPLACE VIEW daily_leads AS
SELECT
    DATE(created_at) AS date,
    COUNT(*) AS new_leads,
    COUNT(phone) AS with_phone
FROM leads
WHERE created_at > NOW() - INTERVAL '30 days'
GROUP BY DATE(created_at)
ORDER BY date DESC;

-- Active leads (messaged in last 48 hours)
CREATE OR REPLACE VIEW active_leads AS
SELECT DISTINCT l.*
FROM leads l
JOIN conversations c ON c.telegram_id = l.telegram_id
WHERE c.created_at > NOW() - INTERVAL '48 hours'
ORDER BY l.updated_at DESC;
