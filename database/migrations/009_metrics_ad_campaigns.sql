-- Migration 009: Ad Campaigns spend tracking for Metrics dashboard
-- Run in Supabase SQL Editor

CREATE TABLE IF NOT EXISTS ad_campaigns (
  id          UUID        DEFAULT gen_random_uuid() PRIMARY KEY,
  campaign_key TEXT       NOT NULL,                    -- matches leads.source field exactly
  name        TEXT        NOT NULL,                    -- human-readable campaign name
  period      TEXT        NOT NULL,                    -- 'YYYY-MM' (month this spend covers)
  spend       NUMERIC(12, 2) DEFAULT 0,               -- ad spend in USD (or your currency)
  impressions INTEGER     DEFAULT 0,                   -- from Meta/Google Ads Manager
  clicks      INTEGER     DEFAULT 0,                   -- from Meta/Google Ads Manager
  notes       TEXT,
  created_at  TIMESTAMPTZ DEFAULT NOW(),
  updated_at  TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE (campaign_key, period)                        -- one row per campaign per month
);

-- Allow anon key to read/write (CRM uses anon key in browser)
ALTER TABLE ad_campaigns ENABLE ROW LEVEL SECURITY;
CREATE POLICY "anon can read ad_campaigns"   ON ad_campaigns FOR SELECT USING (true);
CREATE POLICY "anon can insert ad_campaigns" ON ad_campaigns FOR INSERT WITH CHECK (true);
CREATE POLICY "anon can update ad_campaigns" ON ad_campaigns FOR UPDATE USING (true);
CREATE POLICY "anon can delete ad_campaigns" ON ad_campaigns FOR DELETE USING (true);
